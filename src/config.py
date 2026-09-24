import os
from pathlib import Path
from dotenv import load_dotenv

# Base Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"
TEMP_DIR = PROJECT_ROOT / "temp"
CLIENT_SECRET_FILE = PROJECT_ROOT / "client_secret.json"
TOKEN_FILE = PROJECT_ROOT / "token.json"
ENV_FILE = PROJECT_ROOT / ".env"

# Ensure runtime directories exist
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# Load environment variables
load_dotenv(dotenv_path=ENV_FILE)

# API Keys and Secrets
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
FAL_KEY = os.getenv("FAL_KEY", "")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", "")

# -------------------------------------------------------------
# SHORTS VIDEO CONFIG (9:16 Vertical)
# -------------------------------------------------------------
SHORTS_WIDTH = 1080
SHORTS_HEIGHT = 1920
SHORTS_FPS = 30
SHORTS_MIN_DURATION_SECONDS = 45  # Never less than 45 seconds
SHORTS_TARGET_DURATION_SECONDS = 52
SHORTS_BITRATE = "12000k"

# -------------------------------------------------------------
# LONG-FORM DOCUMENTARY VIDEO CONFIG (16:9 Landscape)
# -------------------------------------------------------------
LONG_WIDTH = 1920
LONG_HEIGHT = 1080
LONG_FPS = 30
LONG_MIN_DURATION_MINUTES = 20  # Never less than 20 minutes
LONG_TARGET_MINUTES = 22
LONG_BITRATE = "10000k"

# General Encoding
VIDEO_CRF = 18
VIDEO_PRESET = "slow"

# Default Model Providers
DEFAULT_GEMINI_MODEL = "gemini-3.6-flash"
FALLBACK_GEMINI_MODEL = "gemini-2.0-flash"
BACKUP_GEMINI_MODEL = "gemini-1.5-flash"
DEFAULT_FAL_MODEL = "fal-ai/wan/v2.1/t2v-720p"
FALLBACK_FAL_MODEL = "fal-ai/kling-video/v1/standard/text-to-video"

# -------------------------------------------------------------
# CONSISTENT NARRATOR CHARACTER DEFINITION
# -------------------------------------------------------------
# Consistent visual identity for your channel's recurring host
NARRATOR_CHARACTER_NAME = "Dr. Julian Vance"
NARRATOR_CHARACTER_DESCRIPTION = (
    "A charismatic, sharp-featured 32-year-old male documentary host with short neat dark hair, "
    "wearing a sleek tailored dark charcoal tactical blazer, engaging intense gaze, expressive storytelling hand gestures. "
    "Positioned in the foreground narrating with conviction, while hyper-realistic cinematic visuals, "
    "holographic projections, and dramatic environment scenes unfold behind him."
)

# Text-To-Speech Studio Configuration
DEFAULT_TTS_VOICE = os.getenv("TTS_VOICE", "en-US-ChristopherNeural")

# YouTube Upload Configuration
YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube"
]
DEFAULT_PRIVACY_STATUS = os.getenv("YOUTUBE_PRIVACY_STATUS", "public")
YOUTUBE_CATEGORY_ID = "28"  # 28 = Science & Technology, 27 = Education

# Scheduler Defaults
DAILY_SHORTS_TIMES = ["10:00", "14:00", "22:00"]  # 10 AM, 2 PM, 10 PM
WEEKLY_LONG_DAY = "Sunday"                       # Every Sunday
WEEKLY_LONG_TIME = "12:00"                        # 12:00 PM Noon
