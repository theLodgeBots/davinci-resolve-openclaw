# ResolveFlow

AI video script editor built on DaVinci Resolve Studio.

Think Descript — but using Resolve's native transcription, with AI-powered script generation and word-level editing.

## How It Works

1. **Open a folder** of video clips (local drive, external volume, NAS — anywhere)
2. **Transcribe** using DaVinci Resolve's native API (free, frame-accurate)
3. **Generate scripts** with AI — pick clips, set duration/style, let it arrange the edit
4. **Refine** iteratively — word-level cuts, AI chat for revisions
5. **Export to Resolve** — one click creates a timeline with your edit

All project data lives inside your video folder at `.resolveflow/` — move the drive to another machine and pick up where you left off.

## Requirements

- **Python 3.10+** (stdlib only, no pip packages)
- **DaVinci Resolve Studio** (free version doesn't expose scripting API)
- **ffmpeg** for speech trimming (`brew install ffmpeg` / `apt install ffmpeg`)
- **OpenAI API key** for AI script generation

## Quick Start

```bash
# Set your OpenAI key
export OPENAI_API_KEY="sk-..."

# Start the server (opens browser automatically)
python3 resolveflow.py /path/to/your/video/folder

# Or start without auto-opening browser
python3 resolveflow.py /path/to/your/video/folder --no-browser

# Or start without a folder (pick from the UI)
python3 resolveflow.py --no-browser
```

Server runs on `http://localhost:8080` — accessible from any device on your network.

## Project Structure

```
resolveflow.py          # Server + API + Resolve integration
resolveflow_db.py       # SQLite database layer
resolveflow_ui.html     # Single-file UI (no build step)
RULES.md                # Core project principles
```

## Data Layout

```
~/.resolveflow/             # App config (recents, preferences)
  recents.json

/your/video/folder/         # Your video project
  *.mp4, *.mov, ...         # Video clips
  .resolveflow/             # Project data (auto-created)
    project.db              # SQLite — clips, transcripts, scripts
    thumbnails/             # Clip thumbnails
```

Move the video folder (including `.resolveflow/`) to any machine with ResolveFlow installed — all transcripts, scripts, and edits travel with it.

## API

| Endpoint | Method | Description |
|---|---|---|
| `/api/clips` | GET | List all clips with metadata |
| `/api/scripts` | GET | List all scripts |
| `/api/script/:id` | GET | Get script with segments + transcript text |
| `/api/ai/auto-edit` | POST | Generate AI script |
| `/api/ai/refine/:id` | POST | Refine script with feedback |
| `/api/export/resolve/:id` | POST | Export script to Resolve timeline |
| `/api/project/open` | POST | Open a project folder |
| `/api/projects/recent` | GET | List recent projects |

## License

MIT
