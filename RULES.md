# ResolveFlow — Rules

## Core Principle
ResolveFlow is a **layer on top of DaVinci Resolve**. It is NOT a standalone video editor.

## Rules
1. **Always use DaVinci Resolve's native APIs** — transcription, timeline creation, media pool, rendering. Never reinvent what Resolve already does.
2. **Transcription = Resolve's native transcription API** (`CreateSubtitlesFromAudio`). NOT Whisper. NOT any external service.
3. **AI can only arrange existing transcript text** — it cannot create new dialog, narration, or content that doesn't exist in the footage.
4. **The goal is rough cut assembly** — help the editor get a rough cut together fast using AI to suggest structure and arrangement from transcribed clips.
5. **Single HTML file UI** — no build step, no frameworks, vanilla JS, dark theme.
6. **Each project = a folder** — the DB lives in `.resolveflow/` inside the project folder.
7. **Resolve is always the final destination** — scripts get exported as timelines back into Resolve for finishing.
