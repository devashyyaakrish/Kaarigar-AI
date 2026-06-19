# 🔧 Karigar AI — WhatsApp Demo

> AI-powered operating system for India's informal workforce — plumbers, electricians, masons, painters.

## The Problem

Informal workers don't lack **skill** — they lack **business intelligence**. They quote prices on gut feeling, can't predict demand, can't prove quality, and lose jobs because of **information asymmetry** that favors customers.

## The Solution

**Karigar AI** sits on top of WhatsApp — the tool every worker already uses — and provides both sides of a home-repair transaction an AI layer:

- 🧠 **Smart Pricing** — Base rate tables + AI calibration gives fair price ranges
- 👷 **Worker Matching** — Haversine distance + weighted scoring ranks top 3 workers
- 📉 **Decline Learning** — When workers decline jobs, the system learns their preferences automatically
- ✅ **Completion Verification** — Before/after photo comparison via AI vision
- 🌐 **Language Bridge** — Works in Hindi, English, and Hinglish seamlessly

## How AI Is Used

| Algorithm | What It Does | Uses AI? |
|---|---|---|
| Intent Detection | Routes every message to the right handler | ✅ Gemini |
| Voice Transcription | Converts Hindi/Hinglish voice notes to text | ✅ Gemini |
| Image Analysis | Identifies problem type, severity, materials needed | ✅ Gemini Vision |
| Price Estimation | Adjusts base rates for specific repair context | ✅ Gemini + hardcoded base |
| Worker Matching | Ranks workers by distance, skill, trust, availability | ❌ Pure math (Haversine) |
| Job Verification | Compares before/after photos to verify completion | ✅ Gemini Vision |
| Response Generation | Creates natural WhatsApp-style replies | ✅ Gemini |

## Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Set your Gemini API key
Edit `.env` and replace `your_api_key_here` with your key from [Google AI Studio](https://aistudio.google.com/apikey):
```
GEMINI_API_KEY=your_actual_key_here
```

### 3. Run the server
```bash
python app.py
```

### 4. Open the demo
Navigate to **http://localhost:5000** in Chrome/Edge.

## Demo Script (60 seconds)

1. **Customer pane** — Type "pipe leak under sink" or upload a photo
2. **Watch** — AI analyzes, shows price range + 3 ranked workers
3. **Pick** — Customer types "2" to select a worker
4. **Worker pane** — Worker sees Hindi/Hinglish job ping in real time
5. **Decline** — Worker types "nahi" → 5-option micro-survey → pick reason → job auto-reassigns
6. **Complete** — Worker uploads after-photo → AI verifies → rating prompt

## Tech Stack

- **Frontend:** HTML/CSS/JS — dual WhatsApp-style chat panes
- **Backend:** Python + Flask
- **AI:** Gemini 2.0 Flash (text, vision, audio)
- **Data:** Flat JSON files (no database needed)

## Project Structure

```
├── app.py                    # Flask server + flow logic
├── gemini_client.py          # Gemini API wrapper
├── algorithms/
│   ├── intent.py             # Intent detection
│   ├── voice.py              # Voice transcription
│   ├── image_analysis.py     # Photo analysis
│   ├── pricing.py            # Price estimation
│   ├── matching.py           # Worker matching (Haversine)
│   ├── verification.py       # Job verification
│   └── response_gen.py       # Response formatting
├── data/
│   ├── workers.json          # 10 mock workers
│   └── pricing_db.json       # Base price ranges
└── frontend/
    ├── index.html            # Dual-pane UI
    ├── style.css             # WhatsApp styling
    └── script.js             # Chat logic
```
