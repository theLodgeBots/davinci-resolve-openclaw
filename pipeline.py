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

    # Step 3: Script (TODO)
    print("▶ STEP 3: Generating edit script...")
    print("  [Not yet implemented — coming in Phase 2]\n")

    # Step 4: Build timeline in Resolve (TODO)
    print("▶ STEP 4: Building DaVinci Resolve timeline...")
    print("  [Not yet implemented — coming in Phase 3]\n")

    print("═══════════════════════════════════════")
    print("  Pipeline complete (Phase 1)")
    print("═══════════════════════════════════════")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python pipeline.py <project_folder>")
        print("Example: python pipeline.py /Volumes/LaCie/VIDEO/nycap-portalcam/")
        sys.exit(1)
    
    run_pipeline(sys.argv[1])
