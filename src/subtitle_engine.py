from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import ImageClip

from src import config
from src.utils import logger


class SubtitleEngine:
    """Extracts word-level timestamps with Whisper/Edge-TTS and creates animated subtitle overlays."""

    def __init__(self, whisper_model_size: str = "base"):
        self.whisper_model_size = whisper_model_size
        self._whisper_model = None

    def _get_whisper_model(self):
        if self._whisper_model is None:
            try:
                import whisper
                logger.info(f"[cyan]Loading OpenAI Whisper model ({self.whisper_model_size})...[/cyan]")
                self._whisper_model = whisper.load_model(self.whisper_model_size)
            except Exception as e:
                logger.warning(f"Could not load OpenAI Whisper: {e}")
                return None
        return self._whisper_model

    def extract_word_timestamps_whisper(self, audio_path: Path) -> List[Dict[str, Any]]:
        """
        Extract word-level timestamps from audio file using OpenAI Whisper.
        """
        model = self._get_whisper_model()
        if model is None:
            return []

        logger.info(f"[cyan]Transcribing audio with Whisper for word-level timestamps...[/cyan]")
        result = model.transcribe(str(audio_path), word_timestamps=True)
        
        words: List[Dict[str, Any]] = []
        for segment in result.get("segments", []):
            for word_info in segment.get("words", []):
                words.append({
                    "word": word_info.get("word", "").strip(),
                    "start": word_info.get("start", 0.0),
                    "end": word_info.get("end", 0.0),
                })
        logger.info(f"[green]✓ Whisper extracted {len(words)} word timestamps.[/green]")
        return words

    def group_words_into_phrases(
        self, words: List[Dict[str, Any]], words_per_phrase: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Group individual words into short 2-3 word high-impact phrase chunks.
        """
        if not words:
            return []

        phrases: List[Dict[str, Any]] = []
        for i in range(0, len(words), words_per_phrase):
            chunk = words[i:i + words_per_phrase]
            phrase_text = " ".join([w["word"] for w in chunk])
            start_time = chunk[0]["start"]
            end_time = chunk[-1]["end"]
            
            # Add a slight minimum display duration for readability
            if end_time - start_time < 0.35:
                end_time = start_time + 0.35

            phrases.append({
                "text": phrase_text.upper(),
                "start": start_time,
                "end": end_time,
                "words": chunk
            })
        return phrases

    def _get_font(self, font_size: int = 72) -> ImageFont.ImageFont:
        """Find a suitable bold font on Windows/Linux/Mac or default."""
        font_candidates = [
            "C:/Windows/Fonts/impact.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/seguibl.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ]
        for font_path in font_candidates:
            if Path(font_path).exists():
                try:
                    return ImageFont.truetype(font_path, font_size)
                except Exception:
                    pass
        return ImageFont.load_default()

    def render_subtitle_frame(
        self,
        text: str,
        video_width: int = config.VIDEO_WIDTH,
        video_height: int = config.VIDEO_HEIGHT,
        font_size: int = 86,
        highlight_color: str = "#FFE600",
        text_color: str = "#FFFFFF",
        stroke_color: str = "#000000",
        stroke_width: int = 10,
    ) -> np.ndarray:
        """
        Render a transparent RGBA image with punchy, high-contrast bordered text & drop shadow.
        """
        img = Image.new("RGBA", (video_width, video_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        font = self._get_font(font_size)

        # Measure text dimensions
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        # Position text in the high-retention center-bottom zone (Y = 65% of screen)
        x = (video_width - text_w) // 2
        y = int(video_height * 0.65)

        # 1. Draw Deep Drop Shadow for 3D Pop
        shadow_offset = 6
        draw.text(
            (x + shadow_offset, y + shadow_offset),
            text,
            font=font,
            fill="#000000B0",
            stroke_width=stroke_width + 2,
            stroke_fill="#000000B0",
        )

        # 2. Draw Heavy Outer Black Stroke
        draw.text(
            (x, y),
            text,
            font=font,
            fill=highlight_color if len(text.split()) <= 2 else text_color,
            stroke_width=stroke_width,
            stroke_fill=stroke_color,
        )

        return np.array(img)

    def create_subtitle_clips(
        self,
        word_timings: List[Dict[str, Any]],
        video_width: int = config.VIDEO_WIDTH,
        video_height: int = config.VIDEO_HEIGHT,
    ) -> List[ImageClip]:
        """
        Generate MoviePy ImageClip overlays for all subtitle phrases.
        """
        phrases = self.group_words_into_phrases(word_timings, words_per_phrase=3)
        clips: List[ImageClip] = []

        logger.info(f"[cyan]Rendering {len(phrases)} animated subtitle chunks...[/cyan]")

        for phrase in phrases:
            text = phrase["text"]
            start_t = phrase["start"]
            end_t = phrase["end"]
            duration = max(0.2, end_t - start_t)

            frame_rgba = self.render_subtitle_frame(
                text=text,
                video_width=video_width,
                video_height=video_height,
                font_size=82,
                highlight_color="#FFDE00",
                stroke_width=9
            )

            # Create MoviePy clip with alpha transparency
            rgb_frame = frame_rgba[:, :, :3]
            alpha_mask = frame_rgba[:, :, 3] / 255.0

            clip = ImageClip(rgb_frame, ismask=False, duration=duration)
            mask_clip = ImageClip(alpha_mask, ismask=True, duration=duration)
            clip = clip.set_mask(mask_clip).set_start(start_t).set_duration(duration)

            clips.append(clip)

        logger.info(f"[green]✓ Generated {len(clips)} subtitle overlays.[/green]")
        return clips
