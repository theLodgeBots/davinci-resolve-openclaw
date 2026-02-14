# DaVinci Resolve OpenClaw

AI-powered video editing pipeline using DaVinci Resolve Studio. A local alternative to Riverside/Descript — drop a folder of videos, get an edited project.

## What This Does

1. **Ingest** — Point at a project folder full of raw video clips (multi-camera, multi-source)
2. **Transcribe** — Whisper transcribes all audio tracks locally
3. **Analyze** — AI reviews transcripts + video metadata to build an edit plan
4. **Script** — Generates a structured script with cuts, B-roll placement, and sequencing
5. **Assemble** — Drives DaVinci Resolve Studio via its Python scripting API to build the timeline
6. **Review** — You review, tweak, and render

## Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌───────────────┐
│  Project Folder  │────▶│  Transcriber  │────▶│  Script Engine │
│  (raw clips)     │     │  (Whisper)    │     │  (LLM)         │
└─────────────────┘     └──────────────┘     └───────┬───────┘
                                                      │
                                                      ▼
                        ┌──────────────┐     ┌───────────────┐
                        │  DaVinci     │◀────│  Timeline      │
                        │  Resolve     │     │  Builder       │
                        │  Studio      │     │  (Python API)  │
                        └──────────────┘     └───────────────┘
```

## Components

### 1. `ingest/` — Media Scanner
- Scans project folder for video/audio files
- Extracts metadata (duration, resolution, codec, camera source)
- Detects multi-cam setups (DJI, Sony, etc.)
- Generates a manifest JSON

### 2. `transcribe/` — Audio Transcription
- Extracts audio from video files (ffmpeg)
- Transcribes via OpenAI Whisper API or local whisper.cpp
- Word-level timestamps for precise cuts
- Speaker diarization (future)

### 3. `script/` — AI Script Generator
- Takes transcripts + metadata as context
- LLM generates an edit decision list (EDL) with reasoning
- Identifies key moments, B-roll opportunities, dead air
- Outputs a structured JSON edit plan

### 4. `resolve/` — DaVinci Resolve Controller
- Python bridge to DaVinci Resolve Studio scripting API
- Creates projects, imports media, builds timelines
- Places clips, sets in/out points, manages tracks
- Audio sync, markers, and render job management

### 5. `mcp/` — MCP Server (Model Context Protocol)
- Exposes DaVinci Resolve operations as MCP tools
- Lets any AI agent control Resolve programmatically
- Tools: import_media, create_timeline, add_clip, set_marker, render, etc.

## Requirements

- macOS (DaVinci Resolve Studio)
- Python 3.10+
- DaVinci Resolve Studio 20+ (free version lacks scripting)
- ffmpeg
- OpenAI API key (for Whisper transcription)

## Test Data

`/Volumes/LaCie/VIDEO/nycap-portalcam/` — Multi-camera shoot:
- `dji/` — 15+ DJI drone clips (aerial, wide shots)
- `sony/` — 11 Sony camera clips + stills + audio tracks

## Quick Start

```bash
# 1. Make sure DaVinci Resolve Studio is running
# 2. Set environment
export RESOLVE_SCRIPT_API="/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting"
export RESOLVE_SCRIPT_LIB="/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so"
export PYTHONPATH="$PYTHONPATH:$RESOLVE_SCRIPT_API/Modules/"

# 3. Run the pipeline
python pipeline.py /Volumes/LaCie/VIDEO/nycap-portalcam/
```

## License

MIT
