import json
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from src import config
from src.utils import console, extract_json_from_text, logger, retry_with_backoff


@dataclass
class Scene:
    scene_id: int
    voiceover_segment: str
    visual_prompt: str
    estimated_duration_seconds: float = 6.0


@dataclass
class Chapter:
    chapter_title: str
    timestamp_start: str
    scenes: List[Scene]


@dataclass
class ShortScript:
    title: str
    description: str
    tags: List[str]
    voiceover_full_script: str
    scenes: List[Scene]

    def model_dump_json(self, indent: int = 2) -> str:
        return json.dumps(asdict(self), indent=indent)


@dataclass
class LongDocumentaryScript:
    title: str
    description: str
    tags: List[str]
    chapters: List[Chapter]
    voiceover_full_script: str
    all_scenes: List[Scene]

    def model_dump_json(self, indent: int = 2) -> str:
        return json.dumps(asdict(self), indent=indent)


SHORTS_SYSTEM_PROMPT = f"""You are a master YouTube Shorts scriptwriter and cinematic director creating viral, ultra-high-retention 45-60 SECOND videos.

CRITICAL DURATION RULE:
- Total video duration MUST BE BETWEEN 48 AND 58 SECONDS (never less than 45 seconds).
- Voiceover script length MUST be between 135 and 165 words spoken at clear documentary pacing.
- Include 8 to 10 distinct, cinematic scenes (5-6 seconds each).

NARRATOR & CHARACTER CONTINUITY:
- The video features our recurring channel host: {config.NARRATOR_CHARACTER_NAME}.
- Character visual: {config.NARRATOR_CHARACTER_DESCRIPTION}
- Visual Prompting Formula: For each scene, describe {config.NARRATOR_CHARACTER_NAME} in the foreground speaking directly to the camera, while a dramatic cinematic background visualization unfolds behind him (e.g. black holes, ancient war battles, Mariana trench depths, exploding stars).

SCRIPT RETENTION STRUCTURE:
1. THE HIGH-STAKES HOOK (0-4s): "Did you know that if you did THIS, THIS would instantly happen...?"
2. THE UNBELIEVABLE SCIENTIFIC/HISTORICAL MECHANIC (4-25s): Deep intriguing explanation.
3. THE SECOND MIND-BENDING REVELATION (25-45s): Escalation with connected shocking facts.
4. THE INFINITE LOOP & CTA (45-55s): Seamless sentence transition back to the opening hook.

Output STRICT JSON matching the schema."""


LONG_DOC_SYSTEM_PROMPT = f"""You are an elite documentary filmmaker and scriptwriter for prestigious 20+ MINUTE long-form YouTube documentaries (like Kurzgesagt, National Geographic, or Vox).

CRITICAL DURATION & DEPTH RULES:
- The documentary MUST be a comprehensive, gripping 20 to 25 minute deep-dive investigation.
- Total narration must span 2,800 to 3,500 spoken words across 6 to 8 immersive Chapters/Acts.
- Total scenes: 30 to 45 high-fidelity cinematic scenes.

NARRATOR & CHARACTER CONTINUITY:
- Channel host: {config.NARRATOR_CHARACTER_NAME} ({config.NARRATOR_CHARACTER_DESCRIPTION}).
- Alternates between the host speaking directly in studio/field environments and full cinematic landscape cutaways.

CHAPTER STRUCTURE:
- Act 1: The Initial Paradox & Mystery (00:00 - 03:30)
- Act 2: Historical Evidence & Ancient Warnings (03:30 - 07:00)
- Act 3: The Scientific Breakdown & Experiments (07:00 - 11:30)
- Act 4: Terrifying Discoveries & Secret Data (11:30 - 15:30)
- Act 5: Global Impact & What Happens Next (15:30 - 19:00)
- Act 6: The Ultimate Conclusion & Human Future (19:00 - 22:00)

Output STRICT JSON matching the LongDocumentaryScript schema."""


class ScriptWriter:
    """Handles script generation for both viral Shorts and 20+ minute documentaries."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or config.GEMINI_API_KEY
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is missing! Please configure GEMINI_API_KEY in .env.")

    def _call_gemini_api(self, system_prompt: str, user_prompt: str) -> str:
        """Direct REST call to Gemini with structured JSON using built-in urllib."""
        payload = json.dumps({
            "contents": [{"parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.75}
        }).encode("utf-8")

        models_to_try = [
            "gemini-3.8-flash",
            "gemini-3.5-flash-lite",
            "gemini-flash-latest",
            "gemini-3.1-flash-lite",
            "gemini-3.1-pro-preview",
            config.DEFAULT_GEMINI_MODEL,
        ]
        for model_name in models_to_try:
            endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.api_key}"
            req = urllib.request.Request(
                endpoint,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            try:
                with urllib.request.urlopen(req, timeout=45) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        candidates = data.get("candidates", [])
                        if candidates:
                            return candidates[0]["content"]["parts"][0]["text"]
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="ignore")
                logger.warning(f"Gemini API model {model_name} HTTP {e.code}: {err_body[:120]}")
            except Exception as e:
                logger.warning(f"Gemini API model {model_name} error: {e}")

        raise RuntimeError("Gemini API generation failed across all available models.")

    def generate_short_script(self, topic: str) -> ShortScript:
        """Generate a viral 48-58 second YouTube Short script with consistent character host."""
        logger.info(f"[cyan]Generating high-retention Short (>=45s) on:[/cyan] [bold]{topic}[/bold]")
        user_prompt = f"""Topic: "{topic}".
Create a full 48-58 second YouTube Short script (minimum 140 words, 8-10 scenes).
Features host: {config.NARRATOR_CHARACTER_NAME} in every scene's visual prompt.

Return valid JSON:
{{
  "title": "...",
  "description": "...",
  "tags": ["..."],
  "voiceover_full_script": "...",
  "scenes": [
    {{
      "scene_id": 1,
      "voiceover_segment": "...",
      "visual_prompt": "Cinematic vertical 9:16, 8k render: Dr. Julian Vance standing in foreground gesturing with intense focus, behind him a colossal glowing black hole bending spacetime with golden accretion disk, volumetric lighting, photorealistic Unreal Engine 5...",
      "estimated_duration_seconds": 6.0
    }}
  ]
}}"""
        raw_json = retry_with_backoff(lambda: self._call_gemini_api(SHORTS_SYSTEM_PROMPT, user_prompt), retries=3)
        data = extract_json_from_text(raw_json)

        scenes = [
            Scene(
                scene_id=s.get("scene_id", i + 1),
                voiceover_segment=s.get("voiceover_segment", ""),
                visual_prompt=s.get("visual_prompt", ""),
                estimated_duration_seconds=float(s.get("estimated_duration_seconds", 6.0))
            )
            for i, s in enumerate(data.get("scenes", []))
        ]

        script = ShortScript(
            title=data.get("title", f"{topic} #Shorts"),
            description=data.get("description", ""),
            tags=data.get("tags", ["Shorts", "Facts", "Documentary"]),
            voiceover_full_script=data.get("voiceover_full_script", ""),
            scenes=scenes
        )
        logger.info(f"[green]✓ Short script generated:[/green] \"{script.title}\" ({len(script.scenes)} scenes, {len(script.voiceover_full_script.split())} words)")
        return script

    def generate_long_documentary_script(self, topic: str) -> LongDocumentaryScript:
        """Generate a complete 20+ minute masterclass documentary script."""
        logger.info(f"[bold cyan]Generating 20+ Minute Long-Form Documentary script on:[/bold cyan] [bold]{topic}[/bold]")
        user_prompt = f"""Create a comprehensive 20 to 25 minute YouTube masterclass documentary on: "{topic}".
Host: {config.NARRATOR_CHARACTER_NAME}.

Return valid JSON with 6 to 8 deep chapters, full 3000+ word narration, and 30+ visual scenes:
{{
  "title": "...",
  "description": "...",
  "tags": ["..."],
  "voiceover_full_script": "...",
  "chapters": [
    {{
      "chapter_title": "Chapter 1: The Cosmic Anomaly",
      "timestamp_start": "00:00",
      "scenes": [
        {{
          "scene_id": 1,
          "voiceover_segment": "...",
          "visual_prompt": "Cinematic 16:9 widescreen 8k: Dr. Julian Vance walking through high-tech observatory...",
          "estimated_duration_seconds": 25.0
        }}
      ]
    }}
  ]
}}"""
        raw_json = retry_with_backoff(lambda: self._call_gemini_api(LONG_DOC_SYSTEM_PROMPT, user_prompt), retries=3)
        data = extract_json_from_text(raw_json)

        all_scenes: List[Scene] = []
        chapters: List[Chapter] = []
        scene_counter = 1

        for ch in data.get("chapters", []):
            ch_scenes = []
            for s in ch.get("scenes", []):
                scene_obj = Scene(
                    scene_id=scene_counter,
                    voiceover_segment=s.get("voiceover_segment", ""),
                    visual_prompt=s.get("visual_prompt", ""),
                    estimated_duration_seconds=float(s.get("estimated_duration_seconds", 25.0))
                )
                ch_scenes.append(scene_obj)
                all_scenes.append(scene_obj)
                scene_counter += 1
            chapters.append(Chapter(
                chapter_title=ch.get("chapter_title", "Chapter"),
                timestamp_start=ch.get("timestamp_start", "00:00"),
                scenes=ch_scenes
            ))

        # Build complete voiceover if split across scenes
        full_vo = data.get("voiceover_full_script", "")
        if not full_vo:
            full_vo = " ".join([s.voiceover_segment for s in all_scenes])

        doc = LongDocumentaryScript(
            title=data.get("title", f"The Untold Truth of {topic}"),
            description=data.get("description", ""),
            tags=data.get("tags", ["Documentary", "Science", "History", "DeepDive"]),
            chapters=chapters,
            voiceover_full_script=full_vo,
            all_scenes=all_scenes
        )
        logger.info(f"[green]✓ Long documentary script generated:[/green] \"{doc.title}\" ({len(doc.chapters)} chapters, {len(doc.all_scenes)} scenes, {len(doc.voiceover_full_script.split())} words)")
        return doc
