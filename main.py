import argparse
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src import config
from src.pipeline import YouTubeShortsPipeline, VIRAL_NICHE_PROMPTS
from src.scheduler import ShortsScheduler
from src.scriptwriter import ScriptWriter
from src.utils import console, logger, print_banner


def main():
    parser = argparse.ArgumentParser(
        description="Autonomous AI Agent for YouTube Shorts (>=45s) & Long Documentaries (>=20m)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Run continuously: 3 Shorts daily (10:00, 14:00, 22:00) + 1 Long Documentary weekly (Sunday).",
    )
    parser.add_argument(
        "--long-video",
        action="store_true",
        help="Generate and produce a single 20+ minute masterclass long-form documentary.",
    )
    parser.add_argument(
        "--topic",
        type=str,
        default=None,
        help="Topic for the video. If omitted, a high-retention fact topic is chosen automatically.",
    )
    parser.add_argument(
        "--privacy",
        type=str,
        choices=["public", "unlisted", "private"],
        default=config.DEFAULT_PRIVACY_STATUS,
        help="YouTube upload privacy status.",
    )
    parser.add_argument(
        "--no-upload",
        action="store_true",
        help="Skip YouTube uploading and only render the video locally in output/ directory.",
    )
    parser.add_argument(
        "--voice",
        type=str,
        default=config.DEFAULT_TTS_VOICE,
        help="Edge-TTS voice name.",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Clean temporary scene clips and intermediate audio after rendering.",
    )
    parser.add_argument(
        "--auth-youtube",
        action="store_true",
        help="Run YouTube OAuth 2.0 authentication flow to create or refresh token.json.",
    )
    parser.add_argument(
        "--set-channel-name",
        type=str,
        default=None,
        help="Update the name/branding of your authenticated YouTube channel.",
    )
    parser.add_argument(
        "--test-script",
        action="store_true",
        help="Test script generation without rendering video.",
    )

    args = parser.parse_args()

    # 1. Standalone YouTube OAuth Setup / Verification
    if args.auth_youtube:
        print_banner("YOUTUBE OAUTH 2.0 AUTHENTICATION SETUP")
        from src.youtube_uploader import YouTubeUploader
        uploader = YouTubeUploader()
        uploader.authenticate()
        logger.info("[bold green]✓ YouTube authentication verified and token.json is active![/bold green]")
        return

    # 2. Update YouTube Channel Name
    if args.set_channel_name:
        print_banner("UPDATING YOUTUBE CHANNEL NAME", f"New Name: {args.set_channel_name}")
        from src.youtube_uploader import YouTubeUploader
        uploader = YouTubeUploader()
        uploader.update_channel_info(new_title=args.set_channel_name)
        return

    # 3. Test Scriptwriting Only
    if args.test_script:
        writer = ScriptWriter()
        if args.long_video:
            topic = args.topic or "The Complete Uncensored Timeline of Ancient Earth"
            doc = writer.generate_long_documentary_script(topic)
            console.print_json(doc.model_dump_json())
        else:
            topic = args.topic or "Did you know that if you fell into a black hole, this time distortion would happen?"
            short = writer.generate_short_script(topic)
            console.print_json(short.model_dump_json())
        return

    # 4. Continuous Full Autonomous Schedule (3x Daily Shorts + 1x Weekly Long Video)
    if args.schedule:
        scheduler = ShortsScheduler(
            privacy_status=args.privacy,
            voice=args.voice,
        )
        scheduler.run_daily_schedule()
        return

    # 5. On-Demand 20+ Minute Long Documentary
    if args.long_video:
        from src.long_video_pipeline import LongVideoPipeline
        long_pipe = LongVideoPipeline(tts_voice=args.voice)
        long_pipe.run(
            topic=args.topic,
            upload=not args.no_upload,
            privacy_status=args.privacy,
            cleanup_temp=args.cleanup,
        )
        return

    # 6. On-Demand YouTube Short (>=45s)
    try:
        pipeline = YouTubeShortsPipeline(tts_voice=args.voice)
        pipeline.run(
            topic=args.topic,
            upload=not args.no_upload,
            privacy_status=args.privacy,
            cleanup_temp=args.cleanup,
        )
    except KeyboardInterrupt:
        logger.warning("\n[yellow]Pipeline interrupted by user.[/yellow]")
    except Exception as e:
        logger.exception(f"[bold red]Pipeline failed with error:[/bold red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
