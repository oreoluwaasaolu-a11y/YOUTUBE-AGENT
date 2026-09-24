import json
import random
import time
from pathlib import Path
from typing import Any, Dict, Optional

from src import config
from src.scriptwriter import ScriptWriter, ShortScript
from src.utils import clean_temp_dir, console, logger, print_banner

VIRAL_NICHE_PROMPTS = [
    # Space & Universe
    "Did you know that if you fell into a black hole, this terrifying time distortion would happen?",
    "Did you know that there is a giant diamond planet in space twice the size of Earth?",
    "Did you know that because space is completely silent, astronaut suits do this to prevent panic?",
    "Did you know what would happen to Earth if the Sun suddenly disappeared for 24 hours?",

    # Nature & Deep Oceans
    "Did you know that because of deep sea pressure, creatures at the bottom of the Mariana Trench evolved like this?",
    "Did you know that if all the world's ice melted overnight, this is what the planet would look like?",
    "Did you know about the deadly underwater lakes on the ocean floor that instantly kill anything that swims into them?",
    "Did you know that lightning actually strikes from the ground up under these rare atmospheric conditions?",

    # Animals & Biology
    "Did you know that if an octopus gets bored, it actually starts doing this bizarre behavior?",
    "Did you know why crows remember human faces for their entire lives and pass grudges to their children?",
    "Did you know that the immortal jellyfish can literally reverse its aging process whenever it gets injured?",
    "Did you know why cats purr when they are healing broken bones?",

    # Human Mind & Body
    "Did you know that if you stay awake for 72 hours, your brain starts doing this to survive?",
    "Did you know that because of the phantom vibration syndrome, your brain tricks you into feeling your phone vibrating?",
    "Did you know why your stomach produces a new layer of mucus every two weeks to prevent digesting itself?",

    # History, Wars & Ancient Empires
    "Did you know that because of a single misplaced message, an entire ancient army lost a battle in 15 minutes?",
    "Did you know why the Great Pyramid of Giza was originally covered in blinding white limestone that glowed like a jewel?",
    "Did you know the secret psychological warfare tactic used during the Cold War that involved fake map coordinates?",
    "Did you know why Rome built underground catacombs spanning hundreds of miles beneath the city?",

    # Countries & Culture
    "Did you know about the forbidden North Sentinel Island where outsiders are attacked on sight?",
    "Did you know why Japan has an entire ghost island called Hashima completely abandoned in the ocean?",
    "Did you know about the town in Norway where it is illegal to die because the permafrost won't decompose bodies?",
]


class YouTubeShortsPipeline:
    """Autonomous orchestrator for YouTube Shorts creation, rendering, and auto-publishing."""

    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        fal_key: Optional[str] = None,
        tts_voice: Optional[str] = None,
        use_whisper: bool = False,
    ):
        self.scriptwriter = ScriptWriter(api_key=gemini_api_key)
        self.tts_voice = tts_voice
        self.fal_key = fal_key
        self.use_whisper = use_whisper
        self._voice_generator = None
        self._visual_generator = None
        self._subtitle_engine = None
        self._video_editor = None
        self._youtube_uploader = None

    @property
    def voice_generator(self):
        if self._voice_generator is None:
            from src.voice_generator import VoiceGenerator
            self._voice_generator = VoiceGenerator(voice=self.tts_voice)
        return self._voice_generator

    @property
    def visual_generator(self):
        if self._visual_generator is None:
            from src.visual_generator import VisualGenerator
            self._visual_generator = VisualGenerator(api_key=self.fal_key)
        return self._visual_generator

    @property
    def subtitle_engine(self):
        if self._subtitle_engine is None:
            from src.subtitle_engine import SubtitleEngine
            self._subtitle_engine = SubtitleEngine()
        return self._subtitle_engine

    @property
    def video_editor(self):
        if self._video_editor is None:
            from src.video_editor import VideoEditor
            self._video_editor = VideoEditor()
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
        Execute the full autonomous pipeline.
        """
        start_time = time.time()
        
        # Pick topic if not provided
        selected_topic = topic or random.choice(VIRAL_NICHE_PROMPTS)
        
        print_banner(
            "🚀 AUTONOMOUS YOUTUBE SHORTS PIPELINE",
            f"Topic: {selected_topic}"
        )

        run_id = int(time.time())
        session_temp = config.TEMP_DIR / f"run_{run_id}"
        session_temp.mkdir(parents=True, exist_ok=True)

        # -------------------------------------------------------------
        # STEP 1: Script & Scene Prompt Generation (Gemini)
        # -------------------------------------------------------------
        logger.info("[bold yellow]► STEP 1/5: Generating Script and Visual Directives...[/bold yellow]")
        script: ShortScript = self.scriptwriter.generate_script(selected_topic)
        
        # Save script json
        script_file = session_temp / "script.json"
        with open(script_file, "w", encoding="utf-8") as f:
            f.write(script.model_dump_json(indent=2))

        # -------------------------------------------------------------
        # STEP 2: Neural Voice Narration (Edge-TTS)
        # -------------------------------------------------------------
        logger.info("[bold yellow]► STEP 2/5: Synthesizing Neural Voice Narration...[/bold yellow]")
        audio_file = session_temp / "narration.mp3"
        audio_path, word_timings = self.voice_generator.generate_narration(
            text=script.voiceover_full_script,
            output_path=audio_file
        )

        # Optional Whisper refinement
        if self.use_whisper:
            try:
                whisper_timings = self.subtitle_engine.extract_word_timestamps_whisper(audio_path)
                if whisper_timings:
                    word_timings = whisper_timings
            except Exception as e:
                logger.warning(f"Whisper fallback to Edge-TTS timings due to: {e}")

        # -------------------------------------------------------------
        # STEP 3: Video Clips Diffusion Generation (fal.ai)
        # -------------------------------------------------------------
        logger.info("[bold yellow]► STEP 3/5: Rendering Cinematic Diffusion Video Clips...[/bold yellow]")
        clips_dir = session_temp / "clips"
        scene_clip_paths = self.visual_generator.generate_all_scenes(
            scenes=script.scenes,
            output_dir=clips_dir
        )

        # -------------------------------------------------------------
        # STEP 4: Video Editing, Audio Alignment & Subtitle Burn-In
        # -------------------------------------------------------------
        logger.info("[bold yellow]► STEP 4/5: Assembling Master Short Video & Subtitles...[/bold yellow]")
        safe_title = "".join(c for c in script.title if c.isalnum() or c in (" ", "_", "-")).rstrip()
        safe_filename = f"{safe_title[:40].strip().replace(' ', '_')}_{run_id}.mp4"
        final_video_path = config.OUTPUT_DIR / safe_filename

        self.video_editor.assemble_and_render(
            scene_video_paths=scene_clip_paths,
            audio_path=audio_path,
            word_timings=word_timings,
            output_path=final_video_path,
            scenes=script.scenes
        )

        # -------------------------------------------------------------
        # STEP 5: Auto-Publish to YouTube Shorts (YouTube Data API v3)
        # -------------------------------------------------------------
        upload_result = None
        if upload:
            logger.info("[bold yellow]► STEP 5/5: Auto-Publishing to YouTube Shorts...[/bold yellow]")
            try:
                upload_result = self.youtube_uploader.upload_short(
                    video_path=final_video_path,
                    title=script.title,
                    description=f"{script.description}\n\n#Shorts #{script.tags[0] if script.tags else 'viral'}",
                    tags=script.tags,
                    privacy_status=privacy_status or config.DEFAULT_PRIVACY_STATUS
                )
            except Exception as e:
                logger.error(f"[red]YouTube upload failed: {e}[/red]")
                upload_result = {"error": str(e)}
        else:
            logger.info("[dim]Skipping YouTube upload (--no-upload flag specified).[/dim]")

        total_elapsed = time.time() - start_time

        # Save metadata summary
        result_summary = {
            "topic": selected_topic,
            "title": script.title,
            "description": script.description,
            "tags": script.tags,
            "voiceover": script.voiceover_full_script,
            "video_path": str(final_video_path),
            "upload": upload_result,
            "execution_time_seconds": round(total_elapsed, 2)
        }

        meta_file = config.OUTPUT_DIR / f"{final_video_path.stem}_meta.json"
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(result_summary, f, indent=2)

        if cleanup_temp:
            clean_temp_dir(session_temp)

        print_banner(
            "✨ PIPELINE EXECUTION FINISHED",
            f"Output File: {final_video_path.name}\nTotal Time: {total_elapsed:.1f}s"
        )

        return result_summary
