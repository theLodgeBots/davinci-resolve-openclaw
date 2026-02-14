# Development Plan

## Phase 1: Foundation (Current)
- [x] Create repo and project structure
- [ ] Build `resolve_bridge.py` — test connection to running DaVinci Resolve
- [ ] Build `ingest.py` — scan folder, extract metadata with ffprobe
- [ ] Build `transcribe.py` — extract audio + Whisper transcription
- [ ] Test with nycap-portalcam project

## Phase 2: Script Engine
- [ ] Design edit plan JSON schema (clips, cuts, order, B-roll markers)
- [ ] Build `script_engine.py` — LLM takes transcripts + metadata → edit plan
- [ ] Handle multi-camera selection logic
- [ ] Support different edit styles (documentary, vlog, highlight reel)

## Phase 3: Timeline Builder
- [ ] Build `timeline_builder.py` — reads edit plan, drives Resolve API
- [ ] Create project, import media to pool
- [ ] Build timeline with clips at correct in/out points
- [ ] Multi-track layout (V1: main, V2: B-roll, A1-A2: audio)
- [ ] Add markers for review points
- [ ] Audio sync between cameras

## Phase 4: MCP Server
- [ ] Build MCP server exposing Resolve operations as tools
- [ ] Tools: list_projects, create_project, import_media, create_timeline
- [ ] Tools: add_clip_to_timeline, set_in_out, add_marker, render
- [ ] Tools: get_transcript, analyze_clips
- [ ] Register with OpenClaw as a skill

## Phase 5: Polish
- [ ] Speaker diarization
- [ ] Scene detection / shot classification (wide, close-up, etc.)
- [ ] Color grading presets per camera type
- [ ] Auto-render and export
- [ ] Web UI for review (optional)
