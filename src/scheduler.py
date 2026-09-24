import datetime
import time
from typing import List, Optional

from src import config
from src.pipeline import YouTubeShortsPipeline
from src.utils import console, logger, print_banner


class ShortsScheduler:
    """Automated scheduler for 3x daily Shorts (>=45s) and 1x weekly Long Documentaries (>=20m)."""

    def __init__(
        self,
        shorts_times: Optional[List[str]] = None,
        long_video_day: str = config.WEEKLY_LONG_DAY,
        long_video_time: str = config.WEEKLY_LONG_TIME,
        privacy_status: str = "public",
        voice: Optional[str] = None,
    ):
        self.shorts_times = shorts_times or config.DAILY_SHORTS_TIMES
        self.long_video_day = long_video_day
        self.long_video_time = long_video_time
        self.privacy_status = privacy_status
        self.voice = voice
        self.shorts_pipeline = YouTubeShortsPipeline(tts_voice=voice)
        self._long_pipeline = None
        self._last_executed_slot = None

    @property
    def long_pipeline(self):
        if self._long_pipeline is None:
            from src.long_video_pipeline import LongVideoPipeline
            self._long_pipeline = LongVideoPipeline(tts_voice=self.voice)
        return self._long_pipeline

    def run_daily_schedule(self) -> None:
        """
        Runs continuous scheduler loop for 3x daily Shorts and 1x weekly 20+ minute Documentary.
        """
        formatted_shorts = ", ".join(self.shorts_times)
        print_banner(
            "🕒 AUTONOMOUS YOUTUBE PRODUCTION AGENT ACTIVE",
            f"Daily Shorts (>=45s): {formatted_shorts}\nWeekly Long Video (>=20m): Every {self.long_video_day} at {self.long_video_time}\nHost: {config.NARRATOR_CHARACTER_NAME}\nPrivacy: {self.privacy_status}"
        )

        while True:
            now = datetime.datetime.now()
            current_day = now.strftime("%A")
            current_hm = now.strftime("%H:%M")
            date_slot_key = f"{now.strftime('%Y-%m-%d')}_{current_hm}"

            # 1. Check for Weekly 20+ Minute Long Documentary Slot
            if (
                current_day.lower() == self.long_video_day.lower()
                and current_hm == self.long_video_time
                and self._last_executed_slot != f"LONG_{date_slot_key}"
            ):
                logger.info(f"\n[bold magenta]🎬 Triggering Weekly 20+ Minute Long-Form Documentary![/bold magenta]")
                self._last_executed_slot = f"LONG_{date_slot_key}"
                try:
                    self.long_pipeline.run(
                        topic=None,
                        upload=True,
                        privacy_status=self.privacy_status,
                        cleanup_temp=True,
                    )
                except Exception as e:
                    logger.error(f"[red]Weekly documentary production error:[/red] {e}")

            # 2. Check for Daily 45-58s Shorts Slots
            elif current_hm in self.shorts_times and self._last_executed_slot != date_slot_key:
                logger.info(f"\n[bold green]⏰ Triggering Scheduled YouTube Short (>=45s) for {current_hm} slot![/bold green]")
                self._last_executed_slot = date_slot_key
                try:
                    self.shorts_pipeline.run(
                        topic=None,
                        upload=True,
                        privacy_status=self.privacy_status,
                        cleanup_temp=True,
                    )
                except Exception as e:
                    logger.error(f"[red]Scheduled Short production error:[/red] {e}")

            time.sleep(25)
