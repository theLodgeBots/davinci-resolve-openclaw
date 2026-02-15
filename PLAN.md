# Development Plan

## Phase 1: Foundation ✅ COMPLETE
- [x] Create repo and project structure
- [x] Build `resolve_bridge.py` — test connection to running DaVinci Resolve
- [x] Build `ingest.py` — scan folder, extract metadata with ffprobe
- [x] Build `transcribe.py` — extract audio + Whisper transcription
- [x] Test with nycap-portalcam project (26 clips, 28.6 min)

## Phase 2: Script Engine ✅ COMPLETE + ENHANCED
- [x] Design edit plan JSON schema (clips, cuts, order, B-roll markers)
- [x] Build `script_engine.py` — LLM takes transcripts + metadata → edit plan
- [x] Build `script_engine_enhanced.py` — rich B-roll strategy with continuous coverage
- [x] Handle multi-camera selection logic (Sony main, DJI B-roll)
- [x] Support different edit styles (basic + enhanced versions)

## Phase 3: Timeline Builder ✅ COMPLETE
- [x] Build `timeline_builder.py` — reads edit plan, drives Resolve API
- [x] Create project, import media to pool
- [x] Build timeline with clips at correct in/out points
- [x] Multi-track layout (V1: main, V2: B-roll, A1: audio)
- [x] Add markers for review points (section markers)
- [x] Enhanced version: 16 clips with 50% B-roll coverage

## Current Status: 🎬 FULL WORKING PIPELINE
- **Original:** 7 sections, 10 clips, 4 minutes, 20% B-roll
- **Enhanced:** 8 sections, 16 clips, 5 minutes, 50% B-roll
- Both timelines successfully built in DaVinci Resolve "nycap-portalcam" project
- Uses 7 DJI drone clips for dynamic aerial footage

## Phase 4: OpenClaw Skill Integration ✅ COMPLETE
- [x] Created OpenClaw skill in `/skills/davinci-resolve/SKILL.md`
- [x] Built CLI wrapper `video_pipeline` with subcommands (pipeline, ingest, transcribe, script, timeline, analyze, status)
- [x] Integrated all tools: ingest, transcribe, script generation, timeline building, analysis
- [x] Added system status checking and error handling
- [x] Full pipeline command with dry-run support
- [x] Proper OpenClaw skill metadata and installation requirements

## Phase 5: Polish ✅ MOSTLY COMPLETE
- [x] **Speaker diarization** — Multi-person footage analysis with OpenAI Whisper
- [x] **Scene detection** — AI-powered shot classification (wide, close-up, B-roll)
- [x] **Color grading presets** — Camera-specific looks (Sony, DJI, Canon, iPhone, GoPro, Mixed)
- [x] **Auto-render and export** — Multiple render presets (4K, 1080p, social media, proxy)
- [x] **Enhanced pipeline** — Unified command with all Phase 5 features integrated
- [ ] Web UI for review (optional — low priority)
