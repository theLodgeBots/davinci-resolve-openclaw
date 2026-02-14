#!/usr/bin/env python3
"""Scan a project folder, extract video metadata, build a manifest."""

import json
import os
import subprocess
import sys
from pathlib import Path

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".mxf", ".r3d", ".braw", ".arw"}
AUDIO_EXTENSIONS = {".wav", ".mp3", ".aac", ".flac", ".m4a"}
IGNORE_EXTENSIONS = {".lrf", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".ds_store"}


def ffprobe_metadata(filepath: str) -> dict:
    """Extract metadata from a media file using ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_format", "-show_streams",
                str(filepath)
            ],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return {"error": result.stderr.strip()}
        return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as e:
        return {"error": str(e)}


def scan_folder(folder_path: str) -> dict:
    """Scan a project folder and build a manifest of all media files."""
    folder = Path(folder_path)
    if not folder.exists():
        print(f"ERROR: Folder does not exist: {folder_path}")
        sys.exit(1)

    manifest = {
        "project_folder": str(folder),
        "sources": {},
        "clips": [],
        "total_duration_seconds": 0,
    }

    for root, dirs, files in os.walk(folder):
        # Skip hidden directories
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        
        rel_root = os.path.relpath(root, folder)
        source_name = rel_root if rel_root != "." else "root"

        for filename in sorted(files):
            if filename.startswith("."):
                continue
            
            ext = os.path.splitext(filename)[1].lower()
            if ext in IGNORE_EXTENSIONS:
                continue

            filepath = os.path.join(root, filename)
            file_size = os.path.getsize(filepath)

            clip = {
                "filename": filename,
                "path": filepath,
                "source": source_name,
                "extension": ext,
                "size_bytes": file_size,
                "size_mb": round(file_size / (1024 * 1024), 1),
            }

            if ext in VIDEO_EXTENSIONS or ext in AUDIO_EXTENSIONS:
                print(f"  Probing: {source_name}/{filename}...")
                probe = ffprobe_metadata(filepath)
                
                if "error" not in probe:
                    fmt = probe.get("format", {})
                    clip["duration_seconds"] = float(fmt.get("duration", 0))
                    clip["format_name"] = fmt.get("format_name", "")
                    
                    for stream in probe.get("streams", []):
                        if stream["codec_type"] == "video" and "video" not in clip:
                            clip["video"] = {
                                "codec": stream.get("codec_name"),
                                "width": stream.get("width"),
                                "height": stream.get("height"),
                                "fps": stream.get("r_frame_rate"),
                                "pix_fmt": stream.get("pix_fmt"),
                            }
                        elif stream["codec_type"] == "audio" and "audio" not in clip:
                            clip["audio"] = {
                                "codec": stream.get("codec_name"),
                                "sample_rate": stream.get("sample_rate"),
                                "channels": stream.get("channels"),
                            }
                    
                    manifest["total_duration_seconds"] += clip.get("duration_seconds", 0)
                else:
                    clip["probe_error"] = probe["error"]

            # Track sources
            if source_name not in manifest["sources"]:
                manifest["sources"][source_name] = {"clip_count": 0, "total_size_mb": 0}
            manifest["sources"][source_name]["clip_count"] += 1
            manifest["sources"][source_name]["total_size_mb"] += clip["size_mb"]

            manifest["clips"].append(clip)

    manifest["total_clips"] = len(manifest["clips"])
    manifest["total_duration_minutes"] = round(manifest["total_duration_seconds"] / 60, 1)

    return manifest


def save_manifest(manifest: dict, output_path: str):
    """Save manifest to JSON file."""
    with open(output_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nManifest saved to: {output_path}")
    print(f"  Clips: {manifest['total_clips']}")
    print(f"  Sources: {list(manifest['sources'].keys())}")
    print(f"  Total Duration: {manifest['total_duration_minutes']} minutes")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ingest.py <project_folder> [output.json]")
        sys.exit(1)
    
    folder = sys.argv[1]
    output = sys.argv[2] if len(sys.argv) > 2 else os.path.join(folder, "manifest.json")
    
    print(f"Scanning: {folder}")
    manifest = scan_folder(folder)
    save_manifest(manifest, output)
