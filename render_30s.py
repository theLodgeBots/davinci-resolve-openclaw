#!/usr/bin/env python3
"""Build and render a 30-second summary edit."""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from resolve_bridge import get_resolve, get_project_manager

RENDER_PATH = "/Users/thelodgestudio/.openclaw/workspace/davinci-resolve-openclaw/renders"


def build_30s_summary():
    resolve = get_resolve()
    if not resolve:
        print("ERROR: Cannot connect to Resolve")
        sys.exit(1)

    pm = get_project_manager(resolve)
    project = pm.LoadProject("nycap-portalcam")
    if not project:
        print("ERROR: Cannot load project")
        sys.exit(1)

    print(f"Project: {project.GetName()}")
    media_pool = project.GetMediaPool()
    root_folder = media_pool.GetRootFolder()

    # Collect all media pool items
    pool_items = {}
    def collect(folder):
        for clip in folder.GetClipList():
            pool_items[clip.GetName()] = clip
        for sub in folder.GetSubFolderList():
            collect(sub)
    collect(root_folder)
    print(f"Media pool: {len(pool_items)} items")

    # Delete existing 30s timeline
    timeline_name = "30s Summary"
    for i in range(1, project.GetTimelineCount() + 1):
        tl = project.GetTimelineByIndex(i)
        if tl and tl.GetName() == timeline_name:
            media_pool.DeleteTimelines([tl])
            break

    timeline = media_pool.CreateEmptyTimeline(timeline_name)
    project.SetCurrentTimeline(timeline)
    print(f"Created timeline: {timeline_name}")

    # 30-second summary cut plan (hand-picked from transcripts):
    # 1. C0026: "Hi I'm Ivan from New York Capture... about the new PortalCam" (2.7s - 9.4s) ~7s
    # 2. C0021: "PortalCam is really interesting because it works just so well... $5000" (0 - 8s) ~8s
    # 3. C0025: "centimeter not millimeter accuracy, capture a large space" (0 - 8s) ~8s  
    # 4. vermont_scan: "lovely scan... incredible detail" (5 - 12s) ~7s
    # Total: ~30s

    cuts = [
        # (filename, start_frame, end_frame) at ~24fps for Sony, ~30fps for DJI
        ("C0026.MP4",       66,   226),    # 2.7s-9.4s  @ 24fps = ~7s intro
        ("C0021.MP4",        0,   192),    # 0-8s       @ 24fps = 8s what it does
        ("C0025.MP4",        0,   192),    # 0-8s       @ 24fps = 8s accuracy
        ("vermont_scan.MP4", 120, 288),    # 5-12s      @ 24fps = 7s showcase
    ]

    for filename, sf, ef in cuts:
        item = pool_items.get(filename)
        if not item:
            print(f"  SKIP {filename}")
            continue
        result = media_pool.AppendToTimeline([{
            "mediaPoolItem": item,
            "startFrame": sf,
            "endFrame": ef,
        }])
        dur = ef - sf
        print(f"  + {filename} frames {sf}-{ef} ({dur} frames) → {'✓' if result else '✗'}")

    # Verify timeline
    print(f"\nTimeline: {timeline.GetName()}")
    print(f"  Tracks: V{timeline.GetTrackCount('video')} A{timeline.GetTrackCount('audio')}")
    items_on_track = timeline.GetItemListInTrack("video", 1)
    if items_on_track:
        print(f"  Clips on V1: {len(items_on_track)}")
        total_frames = timeline.GetEndFrame() - timeline.GetStartFrame()
        print(f"  Total frames: {total_frames}")

    # Set up render
    os.makedirs(RENDER_PATH, exist_ok=True)

    project.SetRenderSettings({
        "TargetDir": RENDER_PATH,
        "CustomName": "portalcam-30s-summary",
        "FormatWidth": "1920",
        "FormatHeight": "1080",
    })

    # Try to set format
    project.SetCurrentRenderFormatAndCodec("mp4", "H264")

    job_id = project.AddRenderJob()
    if not job_id:
        print("ERROR: Could not add render job")
        pm.SaveProject()
        return None

    print(f"\nRender job added: {job_id}")
    project.StartRendering(job_id)
    print("Rendering...")

    # Wait for render
    while project.IsRenderingInProgress():
        status = project.GetRenderJobStatus(job_id)
        pct = status.get("CompletionPercentage", 0)
        print(f"  {pct}%", end="\r")
        time.sleep(1)

    status = project.GetRenderJobStatus(job_id)
    print(f"\nRender complete: {status}")

    pm.SaveProject()

    # Find the rendered file
    rendered_file = os.path.join(RENDER_PATH, "portalcam-30s-summary.mp4")
    if os.path.exists(rendered_file):
        size_mb = os.path.getsize(rendered_file) / (1024*1024)
        print(f"Output: {rendered_file} ({size_mb:.1f} MB)")
        return rendered_file
    else:
        # Check for any new file in render dir
        for f in os.listdir(RENDER_PATH):
            fp = os.path.join(RENDER_PATH, f)
            print(f"  Found: {fp}")
            return fp

    return None


if __name__ == "__main__":
    result = build_30s_summary()
    if result:
        print(f"\n✓ Ready: {result}")
    else:
        print("\n✗ Render failed")
