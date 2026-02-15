# Pipeline Plan: DaVinci Resolve Storyboard Tool

## Inspiration

**Descript**: Text-based video editing. Edit video by editing the transcript. Delete a sentence → the video cut disappears. Key features: filler word removal, AI clips, multicam, regenerate speech.

**Riverside**: Recording + AI editing. Magic Clips auto-finds highlights. Show notes. Captioning. Async recording.

**What we're building**: A local, AI-powered brainstorming/rough-cut tool that uses DaVinci Resolve as the engine. Think "Descript's transcript-based editing meets Trello's card-based planning" — but everything runs through Resolve.

---

## Architecture: Resolve Is The Engine

```
┌─────────────────────────────────────────────────────────┐
│                   DaVinci Resolve Studio                  │
│  ┌──────────┐  ┌───────────┐  ┌──────────┐  ┌────────┐ │
│  │ Media    │  │ Transcribe│  │ Timelines│  │ Render │ │
│  │ Pool     │  │ (built-in)│  │          │  │        │ │
│  │ (clips,  │  │ (timecode │  │ (rough   │  │ (final │ │
│  │  bins,   │  │  accurate,│  │  cuts,   │  │  export│ │
│  │  metadata│  │  speaker  │  │  finals) │  │  queue)│ │
│  │         )│  │  detect)  │  │          │  │        │ │
│  └────┬─────┘  └─────┬─────┘  └────┬─────┘  └───┬────┘ │
│       │              │              │             │      │
│       └──────────────┴──────────────┴─────────────┘      │
│                    Python Scripting API                    │
└───────────────────────────┬─────────────────────────────┘
                            │
                    ┌───────┴────────┐
                    │  Storyboard    │
                    │  Server        │
                    │  (Python)      │
                    └───────┬────────┘
                            │
                    ┌───────┴────────┐
                    │  Web Dashboard │
                    │  (Browser)     │
                    │  :8080         │
                    └────────────────┘
```

## Data Flow

### Phase 1: Ingest
```
Video folder → Import to Resolve Media Pool → Organize in bins
```
- User drops folder of raw clips
- Script imports into Resolve, creates bins by camera/source
- Resolve handles all media management

### Phase 2: Transcribe (Resolve-native)
```
Media Pool clips → Resolve AI Transcription → Subtitle items with timecodes
```
- Use `MediaPoolItem.TranscribeAudio()` or `Folder.TranscribeAudio()` for media pool transcription
- Use `Timeline.CreateSubtitlesFromAudio()` for timeline-based transcription
- Resolve gives us timecode-accurate subtitles (verified: 123 items on test timeline)
- Speaker detection available via UI (API TBD)
- **Transcripts live IN Resolve** — no external Whisper, no JSON files

### Phase 3: Brainstorm (Web UI)
```
Read from Resolve → Storyboard web app → Arrange rough cut → Push back to Resolve
```
The web dashboard reads everything from Resolve via the Python API:

**Source Panel (left):**
- All clips from media pool with thumbnails, duration, source camera
- Transcripts pulled from Resolve's subtitle data
- AI-generated summaries of each clip
- Scene type detection (intro, demo, pricing, B-roll, outtake)
- **Hooks panel**: AI finds the most compelling 5-15s moments
- Filter by scene type, camera, has-speech

**Storyboard (center):**
- Drag-and-drop arrangement of clips and title cards
- Each card shows transcript excerpt + duration
- **Transcript preview**: full readable script of the arrangement
- **Remove pauses toggle**: mark silent gaps for removal
- Title card brainstorming with editable text

**Project Settings (top):**
- Target length (30s, 1min, 2min, 5min, etc.)
- Video prompt / tone / what we want to convey
- AI can suggest arrangements based on these settings

### Phase 4: Build Timeline
```
Storyboard arrangement → Resolve timeline with precise timecodes
```
- "Build in Resolve" button creates a new timeline
- Clips placed with exact in/out points from transcript word timings
- Title cards inserted as Fusion Text+ generators
- B-roll placed on V2
- Markers added at section boundaries

### Phase 5: Finalize in Resolve
```
Rough cut timeline → Human review → Trim/Color/Audio → Render
```
- User opens timeline in Resolve
- Fine-tune cuts, adjust audio levels
- Color grading
- Render from Resolve's deliver page

---

## Key Design Decisions

### Resolve as source of truth, NOT flat files
- ❌ No more `/tmp/*.json`, `manifest.json`, `_transcripts/` folder
- ✅ Read clips from `MediaPool`
- ✅ Read transcripts from Resolve's subtitle/transcription data
- ✅ Write timelines back via `MediaPool.AppendToTimeline()`

### Storyboard state lives in a simple SQLite DB
- Arrangement order, title card text, notes, project settings
- Per-project, stored alongside the server
- Could also use Resolve's marker/metadata system

### Transcription strategy
- **Primary**: Resolve's built-in AI transcription (timecode-accurate)
- **Fallback**: Whisper API if Resolve transcription fails or isn't available
- Resolve transcription confirmed working: `CreateSubtitlesFromAudio()` → 123 subtitle items

### What we take from Descript
- Text-based editing concept (edit the transcript → edit the video)
- Filler word detection and removal
- "Remove pauses" as a toggle

### What we take from Riverside
- AI-powered "Magic Clips" → our "Find Hooks" feature
- Summary generation for clips
- Clean, card-based UI

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Dashboard HTML |
| `/api/status` | GET | Resolve connection status |
| `/api/clips` | GET | All clips from Resolve media pool + transcripts |
| `/api/transcribe` | POST | Trigger Resolve transcription on clips |
| `/api/state` | GET/POST | Storyboard arrangement state |
| `/api/find-hooks` | POST | AI-analyze transcripts for compelling moments |
| `/api/transcript-preview` | POST | Concatenated transcript for arrangement |
| `/api/ai-arrange` | POST | AI suggests arrangement based on settings |
| `/api/build-timeline` | POST | Push arrangement to Resolve as timeline |

---

## Tech Stack
- **Backend**: Python 3 + DaVinci Resolve Scripting API
- **Frontend**: Vanilla HTML/CSS/JS (single file, no build step)
- **Database**: SQLite for storyboard state
- **AI**: OpenAI API for summaries, hooks, arrangement suggestions
- **Transcription**: DaVinci Resolve built-in (primary), Whisper (fallback)

## Repo
- GitHub: https://github.com/theLodgeBots/davinci-resolve-openclaw
- Branch: `mcp-server`
