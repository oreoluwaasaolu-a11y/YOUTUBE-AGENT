# 🎬 Autonomous YouTube Shorts AI Creation Agent

An end-to-end autonomous agent that writes viral scripts, synthesizes neural voiceover, renders cinematic AI video diffusion clips, burns in dynamic TikTok/Shorts-style subtitles, and auto-publishes directly to YouTube Shorts.

---

## ⚡ Architecture & Tech Stack

```
                                  ┌────────────────────────┐
                                  │   User / Auto-Topic    │
                                  └───────────┬────────────┘
                                              │
                                              ▼
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│ 1. Scriptwriting & Scene Prompts (Google Gemini 2.5/3.8 Flash via google-genai)          │
│    - Viral retention hook (0-3s), storytelling payoff, and loop                          │
│    - 4-6 scenes with detailed visual diffusion prompts (vertical 9:16)                   │
└─────────────────────────────────────┬────────────────────────────────────────────────────┘
                                      │
                   ┌──────────────────┴──────────────────┐
                   ▼                                     ▼
┌──────────────────────────────────────┐ ┌────────────────────────────────────────────────┐
│ 2. Neural Voiceover (Edge-TTS)       │ │ 3. Visual Diffusion Video Generation (fal.ai)  │
│    - Studio-grade narration audio    │ │    - Wan 2.1 / Kling / Flux 9:16 vertical clips│
│    - Precise word-level timestamps   │ │    - Dynamic camera motion & cinematic lighting│
└──────────────────┬───────────────────┘ └───────────────────────┬────────────────────────┘
                   │                                             │
                   └──────────────────┬──────────────────────────┘
                                      ▼
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│ 4. Subtitle & Video Assembly Engine (OpenAI Whisper + MoviePy + Pillow)                 │
│    - Word-by-word highlighted subtitle overlays (burn-in)                                │
│    - Dynamic clip pacing synchronized to speech cadence                                  │
│    - Master 1080x1920 (9:16) 60/30fps MP4 export                                         │
└─────────────────────────────────────┬────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│ 5. Auto-Publishing (YouTube Data API v3)                                                 │
│    - Persistent OAuth 2.0 sessions (`token.json`)                                        │
│    - Resumable chunked upload with SEO title, tags, description & #Shorts                │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Setup & Installation

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Credentials in `.env`
Copy `.env.example` to `.env` (already created) and add your API keys:
```env
# Gemini API Key (from Google AI Studio: https://aistudio.google.com/)
GEMINI_API_KEY=your_gemini_api_key_here

# Fal.ai API Key (from https://fal.ai/dashboard/keys)
FAL_KEY=your_fal_key_here

# Default TTS Voice (Optional)
TTS_VOICE=en-US-ChristopherNeural

# YouTube upload default privacy (public, unlisted, private)
YOUTUBE_PRIVACY_STATUS=unlisted
```

### 3. Google OAuth 2.0 Credentials (`client_secret.json`)
Your `client_secret.json` is pre-configured in the project root. On first run, a browser tab will open for a one-time Google authorization. It will automatically save `token.json` so you never have to log in manually again.

---

## 🚀 Usage

### 1. Authenticate YouTube Once (Optional Pre-Flight)
```bash
python main.py --auth-youtube
```

### 2. Run Full Autonomous Pipeline (Auto Viral Topic)
```bash
python main.py
```

### 3. Run with a Custom Topic
```bash
python main.py --topic "The terrifying truth behind the Bloop sound in the deep ocean"
```

### 4. Render Video Locally Without Uploading
```bash
python main.py --topic "Mind-blowing time dilation facts" --no-upload
```

### 5. Test Only Gemini Script & Scene Prompts
```bash
python main.py --topic "Stoic secrets for mental resilience" --test-script
```

### 6. Public YouTube Upload with Custom Voice
```bash
python main.py --topic "Dark psychology tricks" --privacy public --voice en-US-GuyNeural
```

---

## 📁 Directory Structure

```
youtube agent/
├── client_secret.json      # OAuth 2.0 Client credentials
├── token.json              # Persistent YouTube OAuth token (auto-created)
├── .env                    # API keys (GEMINI_API_KEY, FAL_KEY)
├── requirements.txt        # Python package requirements
├── main.py                 # CLI interface
├── src/
│   ├── config.py           # Settings, models & resolution constants
│   ├── scriptwriter.py     # Gemini script & scene prompt generator
│   ├── visual_generator.py # fal.ai video diffusion generation
│   ├── voice_generator.py  # Edge-TTS neural audio synthesis & word timestamps
│   ├── subtitle_engine.py  # Word-level animated subtitle overlay renderer
│   ├── video_editor.py     # MoviePy vertical stitching & audio alignment
│   ├── youtube_uploader.py # YouTube Data API v3 OAuth & upload
│   ├── pipeline.py         # Autonomous orchestrator
│   └── utils.py            # Retries, JSON extraction, and console logging
├── output/                 # Master rendered YouTube Shorts (.mp4 + _meta.json)
└── temp/                   # Temporary scene clips and intermediate audio
```
