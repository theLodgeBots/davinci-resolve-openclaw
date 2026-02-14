#!/usr/bin/env python3
"""Enhanced AI script generator with richer B-roll usage."""

import json
import os
import sys
from pathlib import Path
from script_engine import load_transcripts, load_manifest, build_context


ENHANCED_SCRIPT_PROMPT = """You are an expert video editor creating a professional product review using ALL available footage. Given the following media inventory with transcripts from a multi-camera shoot, create a visually rich edit plan for a polished PortalCam product review.

{context}

---

Create a JSON edit plan for a 4-6 minute video that MAXIMIZES visual variety by using extensive B-roll. 

**B-ROLL STRATEGY:**
- Use DJI drone clips for dynamic aerial shots, product overviews, and scene transitions
- Use Sony clips for different angles, cutaways, and reaction shots
- Fill V2 track continuously with B-roll - avoid long gaps
- Layer main interview/narration (V1) with complementary visuals (V2)
- Use the longest unused clips first to maximize content coverage

**SECTIONS TO CREATE:**
1. **Cold Open** (15-20s) — Dynamic drone footage + quick product tease
2. **Intro** (20-30s) — Host introduction + workspace overview  
3. **Product Overview** (45-60s) — What is PortalCam + comparisons + price discussion
4. **Setup & Demo** (60-90s) — Unboxing, setup process, first scan demonstration
5. **Processing Walkthrough** (45-60s) — Software workflow, processing steps
6. **Quality & Results** (60-75s) — Scan quality discussion + detailed result showcase
7. **Vermont Scan Highlight** (30-45s) — Best scan results, impressive details
8. **Final Thoughts** (30-40s) — Pros/cons, recommendation, closing thoughts

**CLIP SELECTION PRIORITIES:**
- Main narration: Choose best Sony clips with clear audio and good visuals
- B-roll: Prioritize unused DJI clips for aerial variety, then unused Sony clips for coverage
- Overlap B-roll with main clips - don't just use separate segments
- Use multiple B-roll clips per section for visual rhythm
- Choose clips based on relevance to section content

**UNUSED CLIPS TO PRIORITIZE:**
DJI B-roll (aerial/dynamic): DJI_20260121124501_0007_D.MP4 (111s), DJI_20260121120929_0001_D.MP4 (59s), DJI_20260121121406_0006_D.MP4 (23s), DJI_20260121121133_0004_D.MP4 (22s), DJI_20260121134237_0009_D.MP4 (16s), DJI_20260121121100_0003_D.MP4 (13s), DJI_20260121121031_0002_D.MP4 (6s)

Sony coverage: C0031.MP4 (195s), dji_audio-track.MP4 (117s), C0021.MP4 (36s), C0024.MP4 (31s), C0027.MP4 (23s), C0022.MP4 (17s), C0029.MP4 (2s)

Output ONLY valid JSON in this exact format:
{{
  "title": "PortalCam Complete Review - Professional 3D Scanner Test",
  "estimated_duration_seconds": 300,
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
          "note": "Specific reason for this clip selection and timing"
        }}
      ]
    }}
  ]
}}
"""


def generate_enhanced_edit_plan(manifest_path: str, transcripts_dir: str, output_path: str = None) -> dict:
    """Generate an enhanced edit plan with extensive B-roll usage."""
    import requests
    
    manifest = load_manifest(manifest_path)
    transcripts = load_transcripts(transcripts_dir)
    context = build_context(manifest, transcripts)
    
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: No OPENAI_API_KEY set")
        sys.exit(1)
    
    prompt = ENHANCED_SCRIPT_PROMPT.format(context=context)
    
    print("Generating ENHANCED edit plan with extensive B-roll...")
    print(f"  Context: {len(context)} chars, {len(transcripts)} clips with transcripts")
    print("  Strategy: Maximum visual variety with continuous B-roll coverage")
    
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": "gpt-4o",
            "messages": [
                {"role": "system", "content": "You are an expert video editor focused on creating visually engaging content with extensive B-roll usage. Output only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 6000,
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
        print(f"ERROR: Could not parse enhanced edit plan JSON: {e}")
        print(f"Raw content:\n{content[:1000]}")
        return None
    
    # Save the enhanced edit plan
    output_path = output_path or os.path.join(
        os.path.dirname(manifest_path), "edit_plan_enhanced.json"
    )
    with open(output_path, "w") as f:
        json.dump(edit_plan, f, indent=2)
    
    print(f"\nEnhanced edit plan saved to: {output_path}")
    print(f"  Title: {edit_plan.get('title', 'Untitled')}")
    print(f"  Sections: {len(edit_plan.get('sections', []))}")
    total_clips = sum(len(s.get("clips", [])) for s in edit_plan.get("sections", []))
    broll_clips = sum(1 for s in edit_plan.get("sections", []) for c in s.get("clips", []) if c.get("role") == "broll")
    print(f"  Total clip placements: {total_clips}")
    print(f"  B-roll clips: {broll_clips} ({broll_clips/total_clips*100:.1f}%)")
    print(f"  Estimated duration: {edit_plan.get('estimated_duration_seconds', '?')}s")
    
    return edit_plan


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python script_engine_enhanced.py <manifest.json> <transcripts_dir> [output.json]")
        sys.exit(1)
    
    manifest_path = sys.argv[1]
    transcripts_dir = sys.argv[2]
    output_path = sys.argv[3] if len(sys.argv) > 3 else None
    generate_enhanced_edit_plan(manifest_path, transcripts_dir, output_path)