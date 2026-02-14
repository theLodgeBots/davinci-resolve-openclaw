#!/usr/bin/env python3
"""AI-powered script generator: takes transcripts + metadata → edit plan."""

import json
import os
import sys
from pathlib import Path


def load_transcripts(transcripts_dir: str) -> dict:
    """Load all transcripts from directory."""
    transcripts = {}
    for f in sorted(Path(transcripts_dir).glob("*.json")):
        with open(f) as fh:
            data = json.load(fh)
        transcripts[f.stem] = {
            "text": data.get("text", "").strip(),
            "segments": data.get("segments", []),
            "words": data.get("words", []),
        }
    return transcripts


def load_manifest(manifest_path: str) -> dict:
    """Load the project manifest."""
    with open(manifest_path) as f:
        return json.load(f)


def build_context(manifest: dict, transcripts: dict) -> str:
    """Build context string for the LLM."""
    lines = ["# Project Media Inventory\n"]
    
    for clip in manifest["clips"]:
        stem = Path(clip["filename"]).stem
        dur = clip.get("duration_seconds", 0)
        source = clip.get("source", "unknown")
        video = clip.get("video", {})
        res = f"{video.get('width', '?')}x{video.get('height', '?')}" if video else "N/A"
        
        lines.append(f"## {clip['filename']}")
        lines.append(f"- Source: {source}, Duration: {dur:.1f}s, Resolution: {res}")
        
        if stem in transcripts:
            text = transcripts[stem]["text"]
            if text and len(text) > 5:
                lines.append(f"- Transcript: {text}")
            else:
                lines.append("- Transcript: [no speech / ambient only]")
        else:
            lines.append("- Transcript: [not available]")
        lines.append("")
    
    return "\n".join(lines)


SCRIPT_PROMPT = """You are an expert video editor. Given the following media inventory with transcripts from a multi-camera shoot, create an edit plan for a polished product review/demo video.

{context}

---

Create a JSON edit plan. The video should be 3-5 minutes long, telling a coherent story about the PortalCam product.

Structure the video as:
1. **Cold Open** — Hook the viewer with something interesting (5-15 seconds)
2. **Intro** — Welcome, introduce the host and product
3. **Product Overview** — What is it, price point, comparison to alternatives
4. **Demo** — Scanning in action, processing walkthrough
5. **Quality Discussion** — Accuracy, build quality, scan results
6. **Vermont Scan Showcase** — Show off the impressive scan results
7. **Conclusion** — Final thoughts, recommendation

For each section, choose the BEST clips and specify exact in/out points using the transcript timestamps.
Prefer Sony clips for interview/talking head (higher quality), DJI for B-roll/overhead shots.
Skip false starts, "start over" moments, and behind-the-scenes chatter.
When multiple takes of the same content exist, pick the best one.

Output ONLY valid JSON in this exact format:
{{
  "title": "Video title",
  "estimated_duration_seconds": 240,
  "sections": [
    {{
      "name": "Section Name",
      "description": "What this section covers",
      "clips": [
        {{
          "filename": "exact_filename.MP4",
          "role": "main" | "broll",
          "start_seconds": 0.0,
          "end_seconds": 30.0,
          "track": "V1" | "V2",
          "note": "Why this clip/segment was chosen"
        }}
      ]
    }}
  ]
}}
"""


def generate_edit_plan(manifest_path: str, transcripts_dir: str, output_path: str = None) -> dict:
    """Use LLM to generate an edit plan from transcripts and metadata."""
    import requests
    
    manifest = load_manifest(manifest_path)
    transcripts = load_transcripts(transcripts_dir)
    context = build_context(manifest, transcripts)
    
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: No OPENAI_API_KEY set")
        sys.exit(1)
    
    prompt = SCRIPT_PROMPT.format(context=context)
    
    print("Generating edit plan with AI...")
    print(f"  Context: {len(context)} chars, {len(transcripts)} clips with transcripts")
    
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": "gpt-4o",
            "messages": [
                {"role": "system", "content": "You are an expert video editor. Output only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 4000,
        },
        timeout=120,
    )
    
    if response.status_code != 200:
        print(f"ERROR: API returned {response.status_code}: {response.text[:500]}")
        return None
    
    result = response.json()
    content = result["choices"][0]["message"]["content"]
    
    # Strip markdown code fences if present
    if content.startswith("```"):
        content = content.split("\n", 1)[1]
        if content.endswith("```"):
            content = content.rsplit("```", 1)[0]
    
    try:
        edit_plan = json.loads(content)
    except json.JSONDecodeError as e:
        print(f"ERROR: Could not parse edit plan JSON: {e}")
        print(f"Raw content:\n{content[:1000]}")
        return None
    
    # Save the edit plan
    output_path = output_path or os.path.join(
        os.path.dirname(manifest_path), "edit_plan.json"
    )
    with open(output_path, "w") as f:
        json.dump(edit_plan, f, indent=2)
    
    print(f"\nEdit plan saved to: {output_path}")
    print(f"  Title: {edit_plan.get('title', 'Untitled')}")
    print(f"  Sections: {len(edit_plan.get('sections', []))}")
    total_clips = sum(len(s.get("clips", [])) for s in edit_plan.get("sections", []))
    print(f"  Total clip placements: {total_clips}")
    print(f"  Estimated duration: {edit_plan.get('estimated_duration_seconds', '?')}s")
    
    return edit_plan


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python script_engine.py <manifest.json> <transcripts_dir> [output.json]")
        sys.exit(1)
    
    manifest_path = sys.argv[1]
    transcripts_dir = sys.argv[2]
    output_path = sys.argv[3] if len(sys.argv) > 3 else None
    generate_edit_plan(manifest_path, transcripts_dir, output_path)
