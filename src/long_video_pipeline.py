import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

from src import config
from src.scriptwriter import LongDocumentaryScript, ScriptWriter
from src.utils import clean_temp_dir, console, logger, print_banner
from src.voice_generator import VoiceGenerator


class LongVideoPipeline:
    """Autonomous pipeline for creating and publishing 20+ minute deep-dive YouTube documentaries."""

    LONG_TOPIC_IDEAS = [
        "The Complete History of the Universe: From Quantum Foam to the Heat Death",
        "The Lost Civilizations of Earth: Uncovering 10,000 Years of Forbidden Archaeology",
        "The Deep Ocean Abyss: Every Terrifying Creature and Mystery at the Bottom of Earth",
        "The Dark Psychology of Power: How Secret Societies and Empires Controlled History",
        "The Quantum Simulation Paradox: Is Our Entire Reality an Advanced Computer Code?",
        "The Greatest Unsolved Cosmic Mysteries That Baffle Modern Astrophysics",
    ]

    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        fal_key: Optional[str] = None,
        tts_voice: Optional[str] = None,
    ):
        self.scriptwriter = ScriptWriter(api_key=gemini_api_key)
        self.voice_generator = VoiceGenerator(voice=tts_voice)
        self.fal_key = fal_key
        self._visual_generator = None
        self._video_editor = None
        self._youtube_uploader = None

    @property
    def visual_generator(self):
        if self._visual_generator is None:
            from src.visual_generator import VisualGenerator
            self._visual_generator = VisualGenerator(api_key=self.fal_key)
        return self._visual_generator

    @property
    def video_editor(self):
        if self._video_editor is None:
            from src.video_editor import VideoEditor
            self._video_editor = VideoEditor(
                width=config.LONG_WIDTH,
                height=config.LONG_HEIGHT,
                fps=config.LONG_FPS,
            )
        return self._video_editor

    @property
    def youtube_uploader(self):
        if self._youtube_uploader is None:
            from src.youtube_uploader import YouTubeUploader
            self._youtube_uploader = YouTubeUploader()
        return self._youtube_uploader

    def run(
        self,
        topic: Optional[str] = None,
        upload: bool = True,
        privacy_status: Optional[str] = None,
        cleanup_temp: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute full 20+ minute documentary creation and upload pipeline.
        """
        import random
        selected_topic = topic or random.choice(self.LONG_TOPIC_IDEAS)
        start_time = time.time()

        print_banner(
            "🎬 AUTONOMOUS 20+ MINUTE DOCUMENTARY PRODUCTION",
            f"Topic: {selected_topic}\nHost: {config.NARRATOR_CHARACTER_NAME}"
        )

        run_id = int(time.time())
        session_temp = config.TEMP_DIR / f"long_doc_{run_id}"
        session_temp.mkdir(parents=True, exist_ok=True)

        # 1. Scriptwriting
        logger.info("[bold yellow]► STEP 1/5: Writing 20-Minute Master Documentary Script...[/bold yellow]")
        doc_script: LongDocumentaryScript = self.scriptwriter.generate_long_documentary_script(selected_topic)
        with open(session_temp / "documentary_script.json", "w", encoding="utf-8") as f:
            f.write(doc_script.model_dump_json(indent=2))

        # 2. Narration Synthesis
        logger.info("[bold yellow]► STEP 2/5: Synthesizing Full Documentary Narration Audio...[/bold yellow]")
        audio_file = session_temp / "full_narration.mp3"
        audio_path, word_timings = self.voice_generator.generate_narration(
            text=doc_script.voiceover_full_script,
            output_path=audio_file
        )

        # 3. Cinematic Visual Diffusion Generation
        logger.info(f"[bold yellow]► STEP 3/5: Rendering Cinematic Widescreen Scenes ({len(doc_script.all_scenes)} scenes)...[/bold yellow]")
        clips_dir = session_temp / "clips"
        scene_clip_paths = self.visual_generator.generate_all_scenes(
            scenes=doc_script.all_scenes,
            output_dir=clips_dir
        )

        # 4. Master 16:9 Documentary Editing & Chapter Timestamp Alignment
        logger.info("[bold yellow]► STEP 4/5: Assembling Master 16:9 Documentary Video...[/bold yellow]")
        safe_title = "".join(c for c in doc_script.title if c.isalnum() or c in (" ", "_", "-")).rstrip()
        safe_filename = f"DOC_{safe_title[:40].strip().replace(' ', '_')}_{run_id}.mp4"
        final_video_path = config.OUTPUT_DIR / safe_filename

        self.video_editor.assemble_and_render(
            scene_video_paths=scene_clip_paths,
            audio_path=audio_path,
            word_timings=word_timings,
            output_path=final_video_path,
            scenes=doc_script.all_scenes,
        )

        # 5. Build Description with Chapter Timestamps
        timestamp_block = "\n\nCHAPTERS:\n"
        for ch in doc_script.chapters:
            timestamp_block += f"{ch.timestamp_start} - {ch.chapter_title}\n"

        full_description = f"{doc_script.description}\n{timestamp_block}\n\nHost: {config.NARRATOR_CHARACTER_NAME}\n#Documentary #Science #History #DeepDive"

        # 6. YouTube Upload
        upload_result = None
        if upload:
            logger.info("[bold yellow]► STEP 5/5: Auto-Publishing Long Documentary to YouTube...[/bold yellow]")
            try:
                upload_result = self.youtube_uploader.upload_short(
                    video_path=final_video_path,
                    title=doc_script.title,
                    description=full_description,
                    tags=doc_script.tags,
                    privacy_status=privacy_status or config.DEFAULT_PRIVACY_STATUS,
                )
            except Exception as e:
                logger.error(f"[red]Long video upload failed:[/red] {e}")
                upload_result = {"error": str(e)}
        else:
            logger.info("[dim]Skipping YouTube upload (--no-upload specified).[/dim]")

        total_elapsed = time.time() - start_time
        summary = {
            "type": "long_documentary",
            "topic": selected_topic,
            "title": doc_script.title,
            "chapters": len(doc_script.chapters),
            "video_path": str(final_video_path),
            "upload": upload_result,
            "execution_time_minutes": round(total_elapsed / 60.0, 2)
        }

        with open(config.OUTPUT_DIR / f"{final_video_path.stem}_meta.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        if cleanup_temp:
            clean_temp_dir(session_temp)

        print_banner(
            "🎉 20+ MINUTE DOCUMENTARY COMPLETE!",
            f"File: {final_video_path.name}\nTotal Time: {total_elapsed / 60:.1f} minutes"
        )
        return summary
