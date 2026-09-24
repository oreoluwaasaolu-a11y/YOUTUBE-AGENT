import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional

from src import config
from src.scriptwriter import Scene
from src.utils import console, logger, retry_with_backoff


class VisualGenerator:
    """Multi-provider cinematic video generator supporting fal.ai and Replicate with automatic fallback."""

    def __init__(
        self,
        fal_key: Optional[str] = None,
        replicate_token: Optional[str] = None,
        preferred_provider: str = "fal",  # 'fal' or 'replicate'
    ):
        self.fal_key = fal_key or config.FAL_KEY or os.getenv("FAL_KEY", "")
        self.replicate_token = replicate_token or config.REPLICATE_API_TOKEN or os.getenv("REPLICATE_API_TOKEN", "")
        self.preferred_provider = preferred_provider

        if not self.fal_key and not self.replicate_token:
            raise ValueError(
                "Neither FAL_KEY nor REPLICATE_API_TOKEN is configured! Please provide at least one video provider key."
            )

    def _download_file(self, url: str, destination: Path) -> Path:
        """Download remote video URL to a local destination file using standard urllib."""
        destination.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=120) as response, open(destination, "wb") as out_file:
            while True:
                chunk = response.read(65536)
                if not chunk:
                    break
                out_file.write(chunk)
        return destination

    def _generate_with_fal(self, prompt: str, aspect_ratio: str = "9:16") -> str:
        """Generate video via fal.ai REST API."""
        if not self.fal_key:
            raise ValueError("FAL_KEY is not set.")

        logger.info(f"[cyan]Calling fal.ai Wan 2.1 Video Diffusion...[/cyan]")
        endpoint = f"https://queue.fal.run/{config.DEFAULT_FAL_MODEL}"
        payload = json.dumps({
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
        }).encode("utf-8")

        headers = {
            "Authorization": f"Key {self.fal_key}",
            "Content-Type": "application/json",
        }

        # 1. Enqueue Request
        req = urllib.request.Request(endpoint, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            request_id = data.get("request_id")
            status_url = data.get("status_url") or f"https://queue.fal.run/{config.DEFAULT_FAL_MODEL}/requests/{request_id}/status"
            response_url = data.get("response_url") or f"https://queue.fal.run/{config.DEFAULT_FAL_MODEL}/requests/{request_id}"

        # 2. Poll Status until completed
        logger.info(f"[cyan]fal.ai task queued (ID: {request_id[:12]}...). Rendering video...[/cyan]")
        for _ in range(120):  # max 6 minutes
            time.sleep(4)
            status_req = urllib.request.Request(status_url, headers={"Authorization": f"Key {self.fal_key}"})
            with urllib.request.urlopen(status_req, timeout=20) as s_resp:
                s_data = json.loads(s_resp.read().decode("utf-8"))
                status = s_data.get("status")
                if status == "COMPLETED":
                    break
                elif status in ["FAILED", "CANCELLED"]:
                    raise RuntimeError(f"fal.ai generation {status}: {s_data}")

        # 3. Retrieve Result URL
        res_req = urllib.request.Request(response_url, headers={"Authorization": f"Key {self.fal_key}"})
        with urllib.request.urlopen(res_req, timeout=20) as r_resp:
            r_data = json.loads(r_resp.read().decode("utf-8"))
            video_url = None
            if "video" in r_data and isinstance(r_data["video"], dict):
                video_url = r_data["video"].get("url")
            elif "video_url" in r_data:
                video_url = r_data.get("video_url")

            if not video_url:
                raise ValueError(f"Could not parse video URL from fal.ai response: {r_data}")
            return video_url

    def _generate_with_replicate(self, prompt: str, aspect_ratio: str = "9:16") -> str:
        """Generate video via Replicate REST API (Minimax Video-01 / Luma / Wan 2.1)."""
        if not self.replicate_token:
            raise ValueError("REPLICATE_API_TOKEN is not set.")

        logger.info(f"[magenta]Calling Replicate Minimax Video Diffusion fallback...[/magenta]")
        # Using minimax/video-01 or wan-video
        endpoint = "https://api.replicate.com/v1/models/minimax/video-01/predictions"
        payload = json.dumps({
            "input": {
                "prompt": prompt,
                "prompt_optimizer": True
            }
        }).encode("utf-8")

        headers = {
            "Authorization": f"Bearer {self.replicate_token}",
            "Content-Type": "application/json",
            "Prefer": "wait=5"
        }

        # 1. Start Prediction
        req = urllib.request.Request(endpoint, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            pred_id = data.get("id")
            get_url = data.get("urls", {}).get("get") or f"https://api.replicate.com/v1/predictions/{pred_id}"

        # 2. Poll Status
        logger.info(f"[magenta]Replicate task queued (ID: {pred_id[:12]}...). Rendering video...[/magenta]")
        for _ in range(150):  # max 7.5 minutes
            time.sleep(5)
            poll_req = urllib.request.Request(get_url, headers={"Authorization": f"Bearer {self.replicate_token}"})
            with urllib.request.urlopen(poll_req, timeout=20) as p_resp:
                p_data = json.loads(p_resp.read().decode("utf-8"))
                status = p_data.get("status")
                if status == "succeeded":
                    output = p_data.get("output")
                    if isinstance(output, list) and output:
                        return output[0]
                    elif isinstance(output, str):
                        return output
                    raise ValueError(f"Unexpected Replicate output format: {output}")
                elif status in ["failed", "canceled"]:
                    raise RuntimeError(f"Replicate generation {status}: {p_data.get('error')}")

        raise TimeoutError("Replicate video generation timed out.")

    def generate_scene_video(self, scene: Scene, output_path: Path, aspect_ratio: str = "9:16") -> Path:
        """
        Generate video clip for a scene with automatic provider fallback (fal.ai <-> Replicate).
        """
        if output_path.exists() and output_path.stat().st_size > 5000:
            logger.info(f"[green]✓ Scene {scene.scene_id} clip cached at {output_path.name}[/green]")
            return output_path

        logger.info(f"[cyan]Rendering Scene {scene.scene_id}:[/cyan] [dim]{scene.visual_prompt[:90]}...[/dim]")

        video_url = None
        # Try preferred provider first
        if self.preferred_provider == "fal" and self.fal_key:
            try:
                video_url = self._generate_with_fal(scene.visual_prompt, aspect_ratio=aspect_ratio)
            except Exception as e:
                logger.warning(f"[yellow]fal.ai generation encountered error: {e}. Switching to Replicate backup...[/yellow]")
                if self.replicate_token:
                    video_url = self._generate_with_replicate(scene.visual_prompt, aspect_ratio=aspect_ratio)
                else:
                    raise e
        elif self.replicate_token:
            try:
                video_url = self._generate_with_replicate(scene.visual_prompt, aspect_ratio=aspect_ratio)
            except Exception as e:
                logger.warning(f"[yellow]Replicate generation encountered error: {e}. Switching to fal.ai backup...[/yellow]")
                if self.fal_key:
                    video_url = self._generate_with_fal(scene.visual_prompt, aspect_ratio=aspect_ratio)
                else:
                    raise e

        if not video_url:
            raise RuntimeError(f"Failed to generate video for Scene {scene.scene_id} on all available providers.")

        logger.info(f"[cyan]Downloading rendered clip for Scene {scene.scene_id}...[/cyan]")
        saved_file = self._download_file(video_url, output_path)
        logger.info(f"[green]✓ Scene {scene.scene_id} saved:[/green] {saved_file.name}")
        return saved_file

    def generate_all_scenes(
        self, scenes: List[Scene], output_dir: Path, aspect_ratio: str = "9:16"
    ) -> List[Path]:
        """Generate all scene clips sequentially with automatic failover."""
        logger.info(f"[bold cyan]Starting video diffusion generation for {len(scenes)} scenes...[/bold cyan]")
        output_dir.mkdir(parents=True, exist_ok=True)
        clip_paths: List[Path] = []

        for scene in scenes:
            clip_file = output_dir / f"scene_{scene.scene_id:02d}.mp4"
            clip_path = self.generate_scene_video(scene, clip_file, aspect_ratio=aspect_ratio)
            clip_paths.append(clip_path)

        logger.info(f"[bold green]✓ All {len(scenes)} scene video clips successfully rendered![/bold green]")
        return clip_paths
