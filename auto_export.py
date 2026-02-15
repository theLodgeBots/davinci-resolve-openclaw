#!/usr/bin/env python3
"""Auto-render and export for DaVinci Resolve timelines."""

import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, Optional, List

from resolve_bridge import get_resolve

# Render presets and settings
RENDER_PRESETS = {
    "youtube_4k": {
        "format": "mp4",
        "codec": "H264",
        "resolution": (3840, 2160),
        "quality": "High",
        "framerate": 30,
        "audio_codec": "AAC",
        "audio_bitrate": 320,
        "description": "High quality 4K for YouTube upload"
    },
    "youtube_1080p": {
        "format": "mp4", 
        "codec": "H264",
        "resolution": (1920, 1080),
        "quality": "High",
        "framerate": 30,
        "audio_codec": "AAC",
        "audio_bitrate": 192,
        "description": "Standard 1080p for YouTube upload"
    },
    "social_media": {
        "format": "mp4",
        "codec": "H264", 
        "resolution": (1080, 1920),  # Vertical for TikTok/Instagram
        "quality": "Medium",
        "framerate": 30,
        "audio_codec": "AAC",
        "audio_bitrate": 128,
        "description": "Vertical format for social media"
    },
    "proxy": {
        "format": "mp4",
        "codec": "H264",
        "resolution": (960, 540),
        "quality": "Low",
        "framerate": 24,
        "audio_codec": "AAC",
        "audio_bitrate": 128,
        "description": "Low res proxy for review"
    },
    "prores": {
        "format": "mov",
        "codec": "ProRes422HQ",
        "resolution": None,  # Use timeline resolution
        "quality": "High",
        "framerate": None,  # Use timeline framerate
        "audio_codec": "Linear PCM",
        "audio_bitrate": None,
        "description": "Professional ProRes for editing"
    }
}

def get_timeline_info(timeline) -> Dict:
    """Get information about the timeline for export settings."""
    try:
        info = {
            "name": timeline.GetName(),
            "duration": timeline.GetDuration(),
            "fps": timeline.GetSetting("timelineFrameRate"),
            "resolution": (
                int(timeline.GetSetting("timelineResolutionWidth")),
                int(timeline.GetSetting("timelineResolutionHeight"))
            ),
            "start_frame": timeline.GetStartFrame(),
            "end_frame": timeline.GetEndFrame()
        }
        return info
    except Exception as e:
        print(f"❌ Failed to get timeline info: {e}")
        return {}

def create_render_job(project, timeline, preset: str, output_path: str) -> Optional[str]:
    """Create a render job in DaVinci Resolve.
    
    Args:
        project: DaVinci Resolve project object
        timeline: Timeline object to render
        preset: Preset name from RENDER_PRESETS
        output_path: Directory to save rendered file
    
    Returns:
        Job ID if successful, None if failed
    """
    if preset not in RENDER_PRESETS:
        print(f"❌ Unknown preset: {preset}")
        return None
    
    render_settings = RENDER_PRESETS[preset]
    timeline_info = get_timeline_info(timeline)
    
    if not timeline_info:
        print("❌ Could not get timeline information")
        return None
    
    print(f"🎬 Creating render job for: {timeline_info['name']}")
    print(f"   Timeline: {timeline_info['resolution'][0]}x{timeline_info['resolution'][1]} @ {timeline_info['fps']}fps")
    print(f"   Duration: {timeline_info['duration']} frames")
    print(f"   Preset: {render_settings['description']}")
    
    try:
        # Set up render settings
        project.SetRenderSettings({
            # File format
            "SelectAllFrames": True,
            "TargetDir": output_path,
            "CustomName": f"{timeline_info['name']}_{preset}",
            
            # Video settings
            "VideoFormat": render_settings["format"],
            "VideoCodec": render_settings["codec"],
            "VideoQuality": render_settings["quality"],
            
            # Resolution - use timeline resolution if not specified
            "VideoResolution": render_settings["resolution"] or timeline_info["resolution"],
            "VideoFrameRate": render_settings["framerate"] or timeline_info["fps"],
            
            # Audio settings
            "AudioCodec": render_settings["audio_codec"],
            "AudioBitrate": render_settings.get("audio_bitrate", 192),
            
            # Range - render entire timeline
            "MarkIn": timeline_info["start_frame"],
            "MarkOut": timeline_info["end_frame"],
        })
        
        # Add timeline to render queue
        job_id = project.AddRenderJob()
        
        if job_id:
            print(f"✅ Render job created: {job_id}")
            return job_id
        else:
            print("❌ Failed to create render job")
            return None
            
    except Exception as e:
        print(f"❌ Failed to create render job: {e}")
        return None

def monitor_render_progress(project, job_id: str, timeout: int = 3600) -> Dict:
    """Monitor render job progress.
    
    Args:
        project: DaVinci Resolve project object  
        job_id: Render job ID to monitor
        timeout: Maximum time to wait in seconds
    
    Returns:
        Dict with render results
    """
    print(f"⏱️  Monitoring render job: {job_id}")
    print("   Progress: ", end="", flush=True)
    
    start_time = time.time()
    last_progress = -1
    
    while time.time() - start_time < timeout:
        try:
            # Get render job status
            jobs = project.GetRenderJobList()
            job_info = None
            
            for job in jobs:
                if job.get("JobId") == job_id:
                    job_info = job
                    break
            
            if not job_info:
                print(f"\n❌ Job {job_id} not found")
                return {"status": "error", "message": "Job not found"}
            
            status = job_info.get("RenderStatus", "Unknown")
            progress = job_info.get("CompletionPercentage", 0)
            
            # Update progress display
            if progress != last_progress:
                if last_progress >= 0:
                    print(f"\b\b\b\b{progress:3d}%", end="", flush=True)
                else:
                    print(f"{progress:3d}%", end="", flush=True)
                last_progress = progress
            
            # Check if complete
            if status.lower() in ["complete", "finished"]:
                print(f"\n✅ Render complete!")
                return {
                    "status": "complete",
                    "job_id": job_id,
                    "progress": progress,
                    "output_path": job_info.get("TargetDir", ""),
                    "filename": job_info.get("OutputFilename", "")
                }
            
            # Check if failed
            if status.lower() in ["failed", "error"]:
                print(f"\n❌ Render failed: {status}")
                return {
                    "status": "failed", 
                    "job_id": job_id,
                    "error": status
                }
            
            # Still rendering
            time.sleep(5)  # Check every 5 seconds
            
        except Exception as e:
            print(f"\n❌ Error monitoring render: {e}")
            return {"status": "error", "message": str(e)}
    
    print(f"\n⏰ Render timeout after {timeout} seconds")
    return {"status": "timeout", "job_id": job_id}

def render_timeline(project_name: str, timeline_name: str, preset: str = "youtube_1080p", 
                   output_dir: Optional[str] = None, wait: bool = True) -> Dict:
    """Render a specific timeline from a project.
    
    Args:
        project_name: Name of DaVinci Resolve project
        timeline_name: Name of timeline to render
        preset: Render preset to use
        output_dir: Output directory (default: ~/Downloads/DaVinci_Renders)
        wait: Whether to wait for render completion
    
    Returns:
        Dict with render results
    """
    resolve = get_resolve()
    if not resolve:
        return {"error": "Cannot connect to DaVinci Resolve"}
    
    project_manager = resolve.GetProjectManager()
    
    # Load project
    project = project_manager.LoadProject(project_name)
    if not project:
        return {"error": f"Project not found: {project_name}"}
    
    print(f"📁 Loaded project: {project_name}")
    
    # Find timeline
    timeline_count = project.GetTimelineCount()
    target_timeline = None
    
    for i in range(1, timeline_count + 1):
        timeline = project.GetTimelineByIndex(i)
        if timeline and timeline.GetName() == timeline_name:
            target_timeline = timeline
            break
    
    if not target_timeline:
        return {"error": f"Timeline not found: {timeline_name}"}
    
    print(f"🎬 Found timeline: {timeline_name}")
    
    # Set up output directory
    if not output_dir:
        output_dir = os.path.expanduser("~/Downloads/DaVinci_Renders")
    
    os.makedirs(output_dir, exist_ok=True)
    print(f"📂 Output directory: {output_dir}")
    
    # Create render job
    job_id = create_render_job(project, target_timeline, preset, output_dir)
    if not job_id:
        return {"error": "Failed to create render job"}
    
    # Start rendering
    print("🚀 Starting render...")
    success = project.StartRendering()
    
    if not success:
        return {"error": "Failed to start rendering"}
    
    if wait:
        # Monitor progress
        result = monitor_render_progress(project, job_id)
        return result
    else:
        return {"status": "started", "job_id": job_id}

def render_project_timelines(project_name: str, preset: str = "youtube_1080p", 
                           output_dir: Optional[str] = None) -> Dict:
    """Render all timelines in a project.
    
    Args:
        project_name: Name of DaVinci Resolve project
        preset: Render preset to use
        output_dir: Output directory
    
    Returns:
        Dict with render results for all timelines
    """
    resolve = get_resolve()
    if not resolve:
        return {"error": "Cannot connect to DaVinci Resolve"}
    
    project_manager = resolve.GetProjectManager()
    project = project_manager.LoadProject(project_name)
    
    if not project:
        return {"error": f"Project not found: {project_name}"}
    
    timeline_count = project.GetTimelineCount()
    if timeline_count == 0:
        return {"error": "No timelines found in project"}
    
    print(f"📁 Project: {project_name} ({timeline_count} timelines)")
    
    results = {
        "project_name": project_name,
        "preset": preset,
        "total_timelines": timeline_count,
        "rendered_timelines": 0,
        "failed_timelines": 0,
        "timelines": {}
    }
    
    # Set up output directory  
    if not output_dir:
        output_dir = os.path.expanduser(f"~/Downloads/DaVinci_Renders/{project_name}")
    
    os.makedirs(output_dir, exist_ok=True)
    
    for i in range(1, timeline_count + 1):
        timeline = project.GetTimelineByIndex(i)
        if not timeline:
            continue
            
        timeline_name = timeline.GetName()
        print(f"\n🎬 Rendering timeline {i}/{timeline_count}: {timeline_name}")
        
        result = render_timeline(project_name, timeline_name, preset, output_dir, wait=True)
        results["timelines"][timeline_name] = result
        
        if result.get("status") == "complete":
            results["rendered_timelines"] += 1
            print(f"✅ {timeline_name} rendered successfully")
        else:
            results["failed_timelines"] += 1
            print(f"❌ {timeline_name} render failed: {result.get('error', 'Unknown error')}")
    
    return results

def main():
    """Command line interface for auto export."""
    if len(sys.argv) < 3:
        print("Usage:")
        print("  python3 auto_export.py PROJECT_NAME TIMELINE_NAME [preset] [output_dir]")
        print("  python3 auto_export.py PROJECT_NAME --all [preset] [output_dir]")
        print()
        print("Available presets:")
        for name, settings in RENDER_PRESETS.items():
            print(f"  {name:15} - {settings['description']}")
        sys.exit(1)
    
    project_name = sys.argv[1]
    timeline_name = sys.argv[2]
    preset = sys.argv[3] if len(sys.argv) > 3 else "youtube_1080p"
    output_dir = sys.argv[4] if len(sys.argv) > 4 else None
    
    if preset not in RENDER_PRESETS:
        print(f"❌ Unknown preset: {preset}")
        print("Available presets:", ", ".join(RENDER_PRESETS.keys()))
        sys.exit(1)
    
    print("🎬 DaVinci Resolve Auto Export")
    print("=" * 40)
    
    try:
        if timeline_name == "--all":
            # Render all timelines
            result = render_project_timelines(project_name, preset, output_dir)
            
            print(f"\n📊 Export Summary:")
            print(f"   Project: {result['project_name']}")
            print(f"   Success: {result['rendered_timelines']}/{result['total_timelines']}")
            print(f"   Failed: {result['failed_timelines']}")
            
            if result['failed_timelines'] > 0:
                print(f"\n❌ Failed timelines:")
                for name, res in result['timelines'].items():
                    if res.get('status') != 'complete':
                        print(f"   {name}: {res.get('error', 'Unknown error')}")
        else:
            # Render single timeline
            result = render_timeline(project_name, timeline_name, preset, output_dir)
            
            if result.get("status") == "complete":
                print(f"\n🎉 Export complete!")
                print(f"   Output: {result.get('output_path', '')}/{result.get('filename', '')}")
            else:
                print(f"\n❌ Export failed: {result.get('error', 'Unknown error')}")
                sys.exit(1)
                
    except KeyboardInterrupt:
        print(f"\n⚠️  Export interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()