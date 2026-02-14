#!/usr/bin/env python3
"""Build a DaVinci Resolve timeline from an edit plan."""

import json
import os
import sys
from pathlib import Path
from resolve_bridge import get_resolve, get_project_manager


def get_clip_fps(clip_info: dict) -> float:
    """Parse FPS from clip video metadata."""
    fps_str = clip_info.get("video", {}).get("fps", "24/1")
    if "/" in str(fps_str):
        num, den = fps_str.split("/")
        return float(num) / float(den)
    return float(fps_str)


def seconds_to_frames(seconds: float, fps: float = 24.0) -> int:
    """Convert seconds to frame count."""
    return int(round(seconds * fps))


def build_timeline_from_plan(edit_plan_path: str, manifest_path: str, project_name: str = None):
    """Build a DaVinci Resolve timeline from an edit plan JSON."""
    
    with open(edit_plan_path) as f:
        plan = json.load(f)
    with open(manifest_path) as f:
        manifest = json.load(f)
    
    project_name = project_name or plan.get("title", "AI Edit")
    
    # Build filename → manifest clip lookup
    clip_lookup = {}
    for clip in manifest["clips"]:
        clip_lookup[clip["filename"]] = clip
    
    # Connect to Resolve
    resolve = get_resolve()
    if not resolve:
        print("ERROR: Cannot connect to DaVinci Resolve")
        sys.exit(1)
    
    pm = get_project_manager(resolve)
    
    # Load existing project or create new
    project = pm.LoadProject("nycap-portalcam")
    if not project:
        project = pm.CreateProject(project_name)
    if not project:
        print(f"ERROR: Cannot create/load project")
        sys.exit(1)
    
    print(f"Project: {project.GetName()}")
    
    media_pool = project.GetMediaPool()
    root_folder = media_pool.GetRootFolder()
    
    # Build a map of filename → MediaPoolItem from existing pool
    pool_items = {}
    def collect_items(folder):
        for clip in folder.GetClipList():
            name = clip.GetName()
            pool_items[name] = clip
        for sub in folder.GetSubFolderList():
            collect_items(sub)
    collect_items(root_folder)
    print(f"Found {len(pool_items)} clips in media pool")
    
    # Create the AI-edited timeline
    timeline_name = f"AI Edit - {plan.get('title', 'Untitled')}"
    
    # Delete existing timeline with same name if any
    for i in range(1, project.GetTimelineCount() + 1):
        tl = project.GetTimelineByIndex(i)
        if tl and tl.GetName() == timeline_name:
            media_pool.DeleteTimelines([tl])
            break
    
    timeline = media_pool.CreateEmptyTimeline(timeline_name)
    if not timeline:
        print("ERROR: Could not create timeline")
        sys.exit(1)
    
    project.SetCurrentTimeline(timeline)
    print(f"Created timeline: {timeline_name}")
    
    # Add a second video track for B-roll
    timeline.AddTrack("video")
    print(f"  Video tracks: {timeline.GetTrackCount('video')}")
    print(f"  Audio tracks: {timeline.GetTrackCount('audio')}")
    
    # Process each section
    clip_placements = []
    for section in plan.get("sections", []):
        section_name = section.get("name", "Untitled")
        print(f"\n  Section: {section_name}")
        
        for clip_info in section.get("clips", []):
            filename = clip_info["filename"]
            start_sec = clip_info.get("start_seconds", 0)
            end_sec = clip_info.get("end_seconds", None)
            role = clip_info.get("role", "main")
            track = clip_info.get("track", "V1")
            note = clip_info.get("note", "")
            
            # Find the media pool item
            pool_item = pool_items.get(filename)
            if not pool_item:
                print(f"    SKIP {filename} — not in media pool")
                continue
            
            # Get FPS from manifest
            manifest_clip = clip_lookup.get(filename, {})
            fps = get_clip_fps(manifest_clip) if manifest_clip else 24.0
            
            # Calculate frames
            start_frame = seconds_to_frames(start_sec, fps)
            clip_duration = manifest_clip.get("duration_seconds", 0)
            end_frame = seconds_to_frames(end_sec if end_sec else clip_duration, fps)
            
            # Determine track index
            track_idx = 2 if (track == "V2" or role == "broll") else 1
            
            clip_placements.append({
                "mediaPoolItem": pool_item,
                "startFrame": start_frame,
                "endFrame": end_frame,
                "trackIndex": track_idx,
                "mediaType": 1 if track_idx == 2 else None,  # video only for B-roll
            })
            
            dur = (end_sec or clip_duration) - start_sec
            print(f"    + {filename} [{start_sec:.1f}s-{end_sec:.1f}s] ({dur:.1f}s) → Track {track_idx} | {note[:50]}")
    
    # Append clips to timeline
    print(f"\nAppending {len(clip_placements)} clips to timeline...")
    
    for placement in clip_placements:
        clip_info = {
            "mediaPoolItem": placement["mediaPoolItem"],
            "startFrame": placement["startFrame"],
            "endFrame": placement["endFrame"],
            "trackIndex": placement["trackIndex"],
        }
        if placement.get("mediaType"):
            clip_info["mediaType"] = placement["mediaType"]
        
        result = media_pool.AppendToTimeline([clip_info])
        if result:
            print(f"    ✓ appended")
        else:
            # Fallback: append without in/out points
            result = media_pool.AppendToTimeline([placement["mediaPoolItem"]])
            if result:
                print(f"    ✓ appended (full clip)")
            else:
                print(f"    ✗ failed")
    
    # Add section markers
    frame_offset = 0
    for section in plan.get("sections", []):
        name = section.get("name", "Section")
        timeline.AddMarker(frame_offset, "Blue", name, section.get("description", ""), 1)
        # Estimate section duration from clips
        section_dur = sum(
            (c.get("end_seconds", 0) - c.get("start_seconds", 0))
            for c in section.get("clips", [])
        )
        frame_offset += seconds_to_frames(section_dur, 24.0)
    
    # Save
    pm.SaveProject()
    
    print(f"\n═══════════════════════════════════════")
    print(f"  Timeline built: {timeline_name}")
    print(f"  Clips placed: {len(clip_placements)}")
    print(f"  Video tracks: {timeline.GetTrackCount('video')}")
    print(f"  Audio tracks: {timeline.GetTrackCount('audio')}")
    print(f"  Project saved!")
    print(f"═══════════════════════════════════════")
    
    return timeline


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python timeline_builder.py <edit_plan.json> <manifest.json> [project_name]")
        sys.exit(1)
    
    edit_plan_path = sys.argv[1]
    manifest_path = sys.argv[2]
    project_name = sys.argv[3] if len(sys.argv) > 3 else None
    build_timeline_from_plan(edit_plan_path, manifest_path, project_name)
