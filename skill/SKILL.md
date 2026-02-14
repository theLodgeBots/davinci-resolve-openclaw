---
name: davinci_resolve
description: AI video editing pipeline with DaVinci Resolve Studio integration. Ingest footage, transcribe audio, generate AI edit scripts, and build professional timelines.
homepage: https://github.com/theLodgeBots/davinci-resolve-openclaw
metadata:
  {
    "openclaw":
      {
        "emoji": "🎬",
        "requires": { "bins": ["python3", "ffprobe"], "apps": ["DaVinci Resolve"] },
        "install":
          [
            {
              "id": "requirements",
              "kind": "pip",
              "requirements": ["openai", "requests"],
              "label": "Install Python dependencies",
            },
          ],
      },
  }
---

# DaVinci Resolve Video Editing Pipeline 🎬

A complete AI-driven video editing pipeline that transforms raw footage into polished videos using DaVinci Resolve Studio.

**Pipeline Flow:** Raw footage → Metadata extraction → Audio transcription → AI script generation → DaVinci Resolve timeline

## Prerequisites

- **DaVinci Resolve Studio** (tested with v20.3.2) must be running
- **OpenAI API key** in environment (`OPENAI_API_KEY`)
- **Python 3.8+** with required packages
- **ffmpeg/ffprobe** for media analysis

## Core Tools

### 1. Ingest Footage
Scan a folder and extract metadata from video files using ffprobe.

```bash
cd /Users/thelodgestudio/.openclaw/workspace/davinci-resolve-openclaw
python3 ingest.py /path/to/footage/folder
```

**Output:** Creates `manifest.json` with clip metadata (duration, resolution, codecs, etc.)

### 2. Transcribe Audio
Extract audio tracks and generate transcripts using OpenAI Whisper API.

```bash
python3 transcribe.py /path/to/manifest.json
```

**Output:** Creates `_transcripts/` directory with individual transcript files

### 3. Generate Edit Script
Create AI-generated edit plans from transcripts and metadata.

```bash
# Basic edit (minimal B-roll)
python3 script_engine.py /path/to/manifest.json /path/to/_transcripts

# Enhanced edit (rich B-roll coverage)
python3 script_engine_enhanced.py /path/to/manifest.json /path/to/_transcripts
```

**Output:** Creates `edit_plan.json` or `edit_plan_enhanced.json` with structured edit instructions

### 4. Build Timeline
Create complete DaVinci Resolve timelines from edit plans.

```bash
python3 timeline_builder.py /path/to/edit_plan.json /path/to/manifest.json [project_name]
```

**Output:** Creates new project/timeline in DaVinci Resolve with proper clips, in/out points, and B-roll

### 5. Full Pipeline
Run the complete pipeline in one command.

```bash
python3 pipeline.py /path/to/footage/folder [--enhanced] [--project-name "Custom Name"]
```

## Analysis Tools

### Footage Usage Analysis
Analyze which clips are used vs available in an edit plan.

```bash
python3 analyze_usage.py /path/to/manifest.json /path/to/edit_plan.json
```

## Workflow Examples

### Product Review Edit
Transform multi-camera footage into a structured product review:

1. **Ingest:** `python3 ingest.py /Volumes/Drive/product-footage/`
2. **Transcribe:** `python3 transcribe.py /Volumes/Drive/product-footage/manifest.json`
3. **Enhanced Script:** `python3 script_engine_enhanced.py manifest.json _transcripts/`
4. **Build Timeline:** `python3 timeline_builder.py edit_plan_enhanced.json manifest.json "Product Review v1"`

**Result:** Professional timeline with continuous B-roll coverage, section markers, and multi-track layout

### Behind-the-Scenes Compilation
Create engaging compilations from raw footage:

1. Use **enhanced script engine** for maximum B-roll usage
2. Leverage unused clips analysis to find hidden gems
3. AI automatically selects diverse camera angles and moments

## Technical Features

- **Multi-camera support:** Sony, DJI, Canon, iPhone footage
- **Smart B-roll placement:** Continuous coverage without gaps
- **Section-based editing:** Logical story structure with markers
- **Unused clip detection:** Find overlooked footage for improvements
- **Professional timeline:** Proper track layout (V1: main, V2: B-roll, A1: audio)

## Success Stories

**nycap-portalcam Project:**
- 26 clips (28.6 minutes) → 5-minute enhanced edit
- 50% B-roll coverage with 7 different drone angles
- 8 story sections with seamless transitions
- Both timelines successfully built in DaVinci Resolve ✅

## Safety Notes

- **DaVinci Resolve must be running** before timeline operations
- **Save work frequently** — Resolve projects are created automatically
- **Test with small batches** first to verify setup
- **Backup footage** before running batch operations

## Troubleshooting

### Common Issues
1. **Resolve connection failed:** Ensure DaVinci Resolve Studio is running
2. **Transcription errors:** Check OpenAI API key and internet connection
3. **ffprobe not found:** Install ffmpeg via `brew install ffmpeg`
4. **Import errors:** Verify all Python dependencies are installed

### Path Resolution
All scripts use absolute paths. When relative paths are referenced in SKILL.md, resolve against the skill directory:
- Script location: `/Users/thelodgestudio/.openclaw/workspace/davinci-resolve-openclaw/`
- Always `cd` to script directory before execution

## Integration Tips

When calling these tools:
1. **Always change directory first:** `cd /Users/thelodgestudio/.openclaw/workspace/davinci-resolve-openclaw`
2. **Use full paths** for folder arguments
3. **Check prerequisites** before starting (DaVinci Resolve running, API key set)
4. **Monitor output** for errors and handle gracefully

This pipeline has been tested with real client footage and produces professional-quality timelines ready for final editing and export.