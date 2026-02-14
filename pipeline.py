#!/usr/bin/env python3
"""Main pipeline: ingest → transcribe → script → resolve."""

import json
import os
import sys
from pathlib import Path

from ingest import scan_folder, save_manifest
from transcribe import transcribe_project


def run_pipeline(project_folder: str):
    """Run the full editing pipeline on a project folder."""
    project_folder = os.path.abspath(project_folder)
    print(f"═══════════════════════════════════════")
    print(f"  DaVinci Resolve OpenClaw Pipeline")
    print(f"  Project: {project_folder}")
    print(f"═══════════════════════════════════════\n")

    # Step 1: Ingest
    print("▶ STEP 1: Ingesting media...")
    manifest_path = os.path.join(project_folder, "manifest.json")
    
    if os.path.exists(manifest_path):
        print(f"  Using existing manifest: {manifest_path}")
        with open(manifest_path) as f:
            manifest = json.load(f)
    else:
        manifest = scan_folder(project_folder)
        save_manifest(manifest, manifest_path)
    
    print(f"  Found {manifest['total_clips']} clips, {manifest['total_duration_minutes']} min total\n")

    # Step 2: Transcribe
    print("▶ STEP 2: Transcribing audio...")
    transcripts = transcribe_project(manifest_path)
    print(f"  Transcribed {len(transcripts)} clips\n")

    # Step 3: Generate edit script with AI
    print("▶ STEP 3: Generating edit script...")
    from script_engine import generate_edit_plan
    
    transcripts_dir = os.path.join(project_folder, "_transcripts")
    edit_plan_path = os.path.join(project_folder, "edit_plan.json")
    
    if os.path.exists(edit_plan_path):
        print(f"  Using existing edit plan: {edit_plan_path}")
        with open(edit_plan_path) as f:
            edit_plan = json.load(f)
    else:
        edit_plan = generate_edit_plan(manifest_path, transcripts_dir, edit_plan_path)
        if not edit_plan:
            print("  ERROR: Failed to generate edit plan")
            return
    
    sections = len(edit_plan.get("sections", []))
    total_clips = sum(len(s.get("clips", [])) for s in edit_plan.get("sections", []))
    print(f"  Generated plan: {sections} sections, {total_clips} clip placements\n")

    # Step 4: Build timeline in DaVinci Resolve
    print("▶ STEP 4: Building DaVinci Resolve timeline...")
    from timeline_builder import build_timeline_from_plan
    
    try:
        timeline = build_timeline_from_plan(edit_plan_path, manifest_path, edit_plan.get("title"))
        if timeline:
            print(f"  ✅ Timeline created successfully: {timeline.GetName()}")
        else:
            print("  ❌ Failed to create timeline")
    except Exception as e:
        print(f"  ❌ Error building timeline: {e}")
    
    print("═══════════════════════════════════════")
    print("  🎬 Full Pipeline Complete!")
    print(f"  Project: {os.path.basename(project_folder)}")
    print(f"  Clips: {manifest['total_clips']}")
    print(f"  Duration: {manifest['total_duration_minutes']} min")
    print(f"  Edit Plan: {edit_plan.get('title', 'Untitled')}")
    print("═══════════════════════════════════════")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python pipeline.py <project_folder>")
        print("Example: python pipeline.py /Volumes/LaCie/VIDEO/nycap-portalcam/")
        sys.exit(1)
    
    run_pipeline(sys.argv[1])
