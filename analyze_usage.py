#!/usr/bin/env python3
"""Analyze clip usage and suggest B-roll improvements."""

import json
import sys
from pathlib import Path


def analyze_clip_usage(manifest_path: str, edit_plan_path: str):
    """Analyze which clips are used vs available."""
    
    with open(manifest_path) as f:
        manifest = json.load(f)
    with open(edit_plan_path) as f:
        plan = json.load(f)
    
    # Get all available clips
    all_clips = {clip["filename"]: clip for clip in manifest["clips"]}
    
    # Get used clips
    used_clips = set()
    for section in plan.get("sections", []):
        for clip_info in section.get("clips", []):
            used_clips.add(clip_info["filename"])
    
    # Find unused clips
    unused_clips = []
    for filename, clip_data in all_clips.items():
        if filename not in used_clips:
            unused_clips.append({
                "filename": filename,
                "source": clip_data.get("source", "unknown"),
                "duration": clip_data.get("duration_seconds", 0),
                "resolution": f"{clip_data.get('video', {}).get('width', '?')}x{clip_data.get('video', {}).get('height', '?')}"
            })
    
    print(f"📊 Clip Usage Analysis")
    print(f"═══════════════════════")
    print(f"Total clips: {len(all_clips)}")
    print(f"Used clips: {len(used_clips)}")
    print(f"Unused clips: {len(unused_clips)}")
    print()
    
    print("🎬 Currently Used:")
    for section in plan.get("sections", []):
        print(f"  {section['name']}:")
        for clip_info in section.get("clips", []):
            role = clip_info.get("role", "main")
            track = clip_info.get("track", "V1")
            dur = clip_info.get("end_seconds", 0) - clip_info.get("start_seconds", 0)
            print(f"    • {clip_info['filename']} ({role}/{track}) — {dur:.1f}s")
    print()
    
    if unused_clips:
        print("🎥 Unused Clips (Potential B-roll):")
        dji_clips = [c for c in unused_clips if c["source"] == "dji"]
        sony_clips = [c for c in unused_clips if c["source"] == "sony"]
        
        if dji_clips:
            print("  DJI (Drone shots):")
            for clip in sorted(dji_clips, key=lambda x: x["duration"], reverse=True):
                print(f"    • {clip['filename']} — {clip['duration']:.1f}s ({clip['resolution']})")
        
        if sony_clips:
            print("  Sony (Camera shots):")
            for clip in sorted(sony_clips, key=lambda x: x["duration"], reverse=True):
                print(f"    • {clip['filename']} — {clip['duration']:.1f}s ({clip['resolution']})")
    
    print(f"\n💡 Recommendations:")
    print(f"  - {len([c for c in unused_clips if c['source'] == 'dji'])} DJI clips available for aerial B-roll")
    print(f"  - {len([c for c in unused_clips if c['source'] == 'sony'])} Sony clips for additional coverage")
    print(f"  - Consider using more clips on V2 track for visual variety")
    
    total_unused_duration = sum(c["duration"] for c in unused_clips)
    print(f"  - {total_unused_duration:.1f} minutes of unused footage available")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python analyze_usage.py <manifest.json> <edit_plan.json>")
        sys.exit(1)
    
    analyze_clip_usage(sys.argv[1], sys.argv[2])