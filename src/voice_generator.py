import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import edge_tts

from src import config
from src.utils import logger


class VoiceGenerator:
    """Generates neural text-to-speech audio and word-level timing metadata using Edge-TTS."""

    def __init__(self, voice: Optional[str] = None):
        self.voice = voice or config.DEFAULT_TTS_VOICE

    async def _synthesize_async(
        self, text: str, output_audio_path: Path
    ) -> Tuple[Path, List[Dict[str, Any]]]:
        """
        Synthesize audio using Edge-TTS and capture word boundaries.
        """
        communicate = edge_tts.Communicate(text=text, voice=self.voice)
        word_timings: List[Dict[str, Any]] = []

        with open(output_audio_path, "wb") as audio_file:
            async for chunk in communicate.stream():
                chunk_type = chunk.get("type")
                if chunk_type == "audio":
                    audio_file.write(chunk.get("data", b""))
                elif chunk_type == "WordBoundary":
                    # Offset & duration are in 100-nanosecond units (ticks, 10,000,000 per sec)
                    offset_sec = chunk.get("offset", 0) / 10_000_000.0
                    duration_sec = chunk.get("duration", 0) / 10_000_000.0
                    word_text = chunk.get("text", "")
                    word_timings.append({
                        "word": word_text,
                        "start": offset_sec,
                        "end": offset_sec + duration_sec
                    })

        return output_audio_path, word_timings

    def generate_narration(
        self, text: str, output_path: Path
    ) -> Tuple[Path, List[Dict[str, Any]]]:
        """
        Synchronous wrapper to generate narration audio and word boundary timestamps.
        """
        logger.info(f"[cyan]Generating neural voice narration with voice:[/cyan] [bold]{self.voice}[/bold]")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        audio_file, timings = asyncio.run(self._synthesize_async(text, output_path))
        logger.info(f"[green]✓ Audio narration generated:[/green] {audio_file.name} ({len(timings)} words mapped)")
        return audio_file, timings
