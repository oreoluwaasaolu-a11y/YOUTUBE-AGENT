from pathlib import Path
from typing import List, Optional
from moviepy.editor import (
    AudioFileClip,
    CompositeVideoClip,
    VideoFileClip,
    concatenate_videoclips,
    vfx,
)

from src import config
from src.scriptwriter import Scene
from src.subtitle_engine import SubtitleEngine
from src.utils import logger


class VideoEditor:
    """Handles video resizing, pacing synchronization, subtitle compositing, and final rendering."""

    def __init__(
        self,
        width: int = config.VIDEO_WIDTH,
        height: int = config.VIDEO_HEIGHT,
        fps: int = config.VIDEO_FPS,
    ):
        self.width = width
        self.height = height
        self.fps = fps
        self.subtitle_engine = SubtitleEngine()

    def _normalize_clip_to_vertical(self, clip: VideoFileClip) -> VideoFileClip:
        """
        Crop/resize any video clip into standard 1080x1920 9:16 vertical video.
        """
        w, h = clip.size
        target_ratio = self.width / self.height  # 9/16 = 0.5625
        current_ratio = w / h

        if abs(current_ratio - target_ratio) > 0.02:
            # Clip aspect ratio differs, crop to target ratio from center
            if current_ratio > target_ratio:
                # Clip is wider than 9:16, crop width
                new_w = int(h * target_ratio)
                x_center = w // 2
                clip = clip.crop(
                    x1=x_center - new_w // 2,
                    y1=0,
                    x2=x_center + new_w // 2,
                    y2=h
                )
            else:
                # Clip is taller than 9:16, crop height
                new_h = int(w / target_ratio)
                y_center = h // 2
                clip = clip.crop(
                    x1=0,
                    y1=y_center - new_h // 2,
                    x2=w,
                    y2=y_center + new_h // 2
                )

        # Resize to exact dimensions
        return clip.resize((self.width, self.height))

    def assemble_and_render(
        self,
        scene_video_paths: List[Path],
        audio_path: Path,
        word_timings: List[dict],
        output_path: Path,
        scenes: Optional[List[Scene]] = None,
    ) -> Path:
        """
        Stitch scene clips, align duration with narration, burn in subtitles, and export master MP4.
        """
        logger.info(f"[cyan]Assembling video from {len(scene_video_paths)} clips and audio...[/cyan]")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        audio_clip = AudioFileClip(str(audio_path))
        total_audio_duration = audio_clip.duration
        logger.info(f"[cyan]Total narration duration:[/cyan] [bold]{total_audio_duration:.2f}s[/bold]")

        # Determine duration allocated per scene clip
        num_scenes = len(scene_video_paths)
        clip_durations = []
        if scenes and len(scenes) == num_scenes:
            # Proportionally distribute audio duration according to scene estimations
            total_est = sum(s.estimated_duration_seconds for s in scenes)
            if total_est > 0:
                clip_durations = [
                    (s.estimated_duration_seconds / total_est) * total_audio_duration
                    for s in scenes
                ]
        if not clip_durations:
            # Equal duration distribution
            per_clip = total_audio_duration / max(1, num_scenes)
            clip_durations = [per_clip] * num_scenes

        prepared_clips: List[VideoFileClip] = []
        for i, (video_path, target_duration) in enumerate(zip(scene_video_paths, clip_durations)):
            raw_clip = VideoFileClip(str(video_path))
            norm_clip = self._normalize_clip_to_vertical(raw_clip)

            # Adjust clip length to target duration
            if norm_clip.duration < target_duration:
                # Loop clip if shorter than needed
                loops_needed = int(target_duration // norm_clip.duration) + 1
                norm_clip = vfx.loop(norm_clip, n=loops_needed).subclip(0, target_duration)
            else:
                # Trim clip to target duration
                norm_clip = norm_clip.subclip(0, target_duration)

            prepared_clips.append(norm_clip)

        # Concatenate all visual clips sequentially
        base_video = concatenate_videoclips(prepared_clips, method="compose")
        base_video = base_video.set_duration(total_audio_duration)

        # Create animated subtitle overlay clips
        subtitle_clips = self.subtitle_engine.create_subtitle_clips(
            word_timings=word_timings,
            video_width=self.width,
            video_height=self.height,
        )

        # Composite video layers
        layers = [base_video] + subtitle_clips
        final_video = CompositeVideoClip(layers, size=(self.width, self.height))
        final_video = final_video.set_audio(audio_clip).set_duration(total_audio_duration)

        # Render output MP4 with high-bitrate and lossless clarity
        logger.info(f"[bold cyan]Rendering high-fidelity YouTube Short to {output_path.name}...[/bold cyan]")
        final_video.write_videofile(
            str(output_path),
            fps=self.fps,
            codec="libx264",
            audio_codec="aac",
            audio_bitrate="192k",
            preset=config.VIDEO_PRESET,
            bitrate=config.VIDEO_BITRATE,
            ffmpeg_params=["-crf", str(config.VIDEO_CRF), "-pix_fmt", "yuv420p"],
            threads=4,
            logger="bar"
        )

        # Cleanup clips in memory
        for c in prepared_clips:
            c.close()
        audio_clip.close()
        final_video.close()

        logger.info(f"[green]✓ Final video successfully exported:[/green] {output_path}")
        return output_path
