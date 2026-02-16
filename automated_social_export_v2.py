#!/usr/bin/env python3
"""
🎬 DaVinci Resolve OpenClaw - Automated Social Media Export V2
Modified to work without CreateTimeline API limitation.
Uses existing timelines and focuses on render job creation.

Usage:
    python3 automated_social_export_v2.py [analysis_folder]
"""

import sys
import json
import os
from pathlib import Path
import time
from datetime import datetime

def get_resolve_connection():
    """Connect to DaVinci Resolve API"""
    try:
        # Add DaVinci Resolve scripting modules to path
        dvr_modules_path = '/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules/'
        if dvr_modules_path not in sys.path:
            sys.path.append(dvr_modules_path)
        import DaVinciResolveScript as dvr_script
        resolve = dvr_script.scriptapp("Resolve")
        if not resolve:
            raise Exception("Could not connect to DaVinci Resolve")
        return resolve
    except Exception as e:
        print(f"❌ Failed to connect to DaVinci Resolve: {e}")
        print("Make sure DaVinci Resolve is running and scripting is enabled")
        return None

def load_analysis_data(analysis_folder):
    """Load export strategy and render presets from analysis folder"""
    strategy_path = Path(analysis_folder) / "export_strategy.json"
    presets_path = Path(analysis_folder) / "render_presets_used.json"
    
    if not strategy_path.exists():
        print(f"❌ Export strategy file not found: {strategy_path}")
        return None, None
        
    if not presets_path.exists():
        print(f"❌ Render presets file not found: {presets_path}")
        return None, None
    
    try:
        with open(strategy_path, 'r') as f:
            strategy = json.load(f)
        with open(presets_path, 'r') as f:
            presets = json.load(f)
        return strategy, presets
    except Exception as e:
        print(f"❌ Error loading analysis data: {e}")
        return None, None

def create_render_preset(resolve, preset_name, preset_config):
    """Create or update render settings based on preset configuration"""
    try:
        project_manager = resolve.GetProjectManager()
        project = project_manager.GetCurrentProject()
        
        # Base render settings template
        render_settings = {
            # Format settings
            "SelectAllFrames": 1,
            "SkipAlreadyRendered": 0,
            "FormatWidth": preset_config.get("width", 1920),
            "FormatHeight": preset_config.get("height", 1080),
            "FrameRate": preset_config.get("framerate", 30.0),
            
            # Quality settings  
            "PixelAspectRatio": 1.0,
            "VideoQuality": preset_config.get("quality", 80),
            
            # Output settings
            "TargetDir": "exports/social_media/",
            "CustomName": f"{preset_name}_export",
            
            # Codec settings (MP4/H.264 for social media)
            "VideoCodec": "H.264",
            "AudioCodec": "AAC",
            "AudioBitDepth": 16,
            "AudioSampleRate": 48000,
        }
        
        # Apply preset-specific overrides
        if "bitrate" in preset_config:
            render_settings["VideoBitrate"] = preset_config["bitrate"]
            
        return render_settings
        
    except Exception as e:
        print(f"❌ Error creating render preset {preset_name}: {e}")
        return None

def find_source_timeline(resolve, timeline_name):
    """Find the source timeline to use for exports"""
    try:
        project_manager = resolve.GetProjectManager()
        project = project_manager.GetCurrentProject()
        
        timeline_count = project.GetTimelineCount()
        
        # First try to find exact timeline name match
        for i in range(timeline_count):
            timeline = project.GetTimelineByIndex(i + 1)
            if timeline and timeline.GetName() == timeline_name:
                return timeline
                
        # If exact match not found, look for likely candidates
        candidates = []
        for i in range(timeline_count):
            timeline = project.GetTimelineByIndex(i + 1)
            if timeline:
                name = timeline.GetName()
                if any(keyword in name.lower() for keyword in ["ai edit", "portalcam", "complete", "main"]):
                    candidates.append((timeline, name))
                    
        if candidates:
            print(f"📍 Using timeline: '{candidates[0][1]}'")
            return candidates[0][0]
            
        # Fallback: use current timeline
        current_timeline = project.GetCurrentTimeline()
        if current_timeline:
            print(f"📍 Using current timeline: '{current_timeline.GetName()}'")
            return current_timeline
            
        print("❌ No suitable timeline found")
        return None
        
    except Exception as e:
        print(f"❌ Error finding source timeline: {e}")
        return None

def create_render_job(resolve, timeline, render_settings, clip_data, export_variant):
    """Create a render job for a specific social media clip"""
    try:
        project_manager = resolve.GetProjectManager()
        project = project_manager.GetCurrentProject()
        
        if not project or not timeline:
            print("❌ No project or timeline available")
            return False
            
        # Set the current timeline
        project.SetCurrentTimeline(timeline)
        
        # Calculate frame range based on clip timing
        fps = render_settings.get("FrameRate", 30.0)
        start_frame = int(clip_data["start_seconds"] * fps)
        end_frame = int((clip_data["start_seconds"] + clip_data["duration_seconds"]) * fps)
        
        # Update render settings for this specific clip
        output_filename = f"{clip_data['clip_name']}_{export_variant['preset']}_{int(clip_data['duration_seconds'])}s"
        render_settings["CustomName"] = output_filename
        
        # Set in/out points for the clip (if supported by API)
        # Note: Frame range setting might need adjustment based on API availability
        
        # Apply render settings to project
        success = project.SetRenderSettings(render_settings)
        if not success:
            print(f"   ⚠️  Could not set render settings, using project defaults")
        
        # Add to render queue
        render_job_id = project.AddRenderJob()
        if render_job_id:
            print(f"   ✅ Added to render queue: {output_filename} (Job ID: {render_job_id})")
            return True
        else:
            print(f"   ❌ Failed to add render job for {output_filename}")
            return False
            
    except Exception as e:
        print(f"   ❌ Error creating render job: {e}")
        return False

def main():
    if len(sys.argv) < 2:
        print("❌ Analysis folder not provided")
        print("Usage: python3 automated_social_export_v2.py [analysis_folder]")
        sys.exit(1)
    
    analysis_folder = Path(sys.argv[1])
    if not analysis_folder.exists():
        print(f"❌ Analysis folder not found: {analysis_folder}")
        sys.exit(1)
    
    print("🎬 DaVinci Resolve OpenClaw - Automated Social Export V2")
    print(f"📁 Analysis Folder: {analysis_folder}")
    print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Load analysis data
    strategy, presets = load_analysis_data(analysis_folder)
    if not strategy or not presets:
        sys.exit(1)
    
    print(f"📊 Loaded export strategy: {len(strategy['exports'])} clips")
    print(f"🎨 Available presets: {len(presets['presets'])}")
    
    # Connect to DaVinci Resolve
    resolve = get_resolve_connection()
    if not resolve:
        sys.exit(1)
    
    print("✅ Connected to DaVinci Resolve")
    
    # Find source timeline
    source_timeline = find_source_timeline(resolve, strategy["timeline_name"])
    if not source_timeline:
        print("❌ Could not find suitable source timeline")
        sys.exit(1)
    
    # Process each clip and export variant
    successful_exports = 0
    total_exports = 0
    
    for clip in strategy["exports"]:
        print(f"\n🎞️  Processing: {clip['clip_name']}")
        print(f"   Description: {clip.get('clip_description', 'No description')}")
        print(f"   Duration: {clip['duration_seconds']}s ({clip['start_seconds']}s - {clip['start_seconds'] + clip['duration_seconds']}s)")
        
        for variant in clip["export_variants"]:
            total_exports += 1
            preset_name = variant["preset"]
            
            if preset_name not in presets["presets"]:
                print(f"   ❌ Preset not found: {preset_name}")
                continue
                
            preset_config = presets["presets"][preset_name]
            print(f"   📱 Export variant: {preset_config['name']} ({variant['priority']} priority)")
            
            # Create render settings
            render_settings = create_render_preset(resolve, preset_name, preset_config)
            if not render_settings:
                continue
                
            print(f"   ✅ Configured render preset: {preset_name}")
            
            # Create render job
            if create_render_job(resolve, source_timeline, render_settings, clip, variant):
                successful_exports += 1
    
    print("\n" + "=" * 60)
    print("📊 EXPORT SUMMARY")
    print(f"✅ Successfully queued: {successful_exports}/{total_exports}")
    print(f"📁 Output directory: exports/social_media/")
    print(f"⏰ Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if successful_exports > 0:
        print("\n🚀 NEXT STEPS:")
        print("1. Check DaVinci Resolve render queue (Deliver page)")
        print("2. Review render jobs and start rendering:")
        print("   - Manual: Go to Deliver page > Start Render")
        print("   - API: Run project.StartRendering()")
        print("3. Monitor render progress in DaVinci Resolve")
        print("4. Check exports/social_media/ for completed files")
    
    # Create summary file
    summary = {
        "export_run_v2": {
            "timestamp": datetime.now().isoformat(),
            "analysis_folder": str(analysis_folder),
            "source_timeline": source_timeline.GetName() if source_timeline else None,
            "total_clips": len(strategy["exports"]),
            "total_exports": total_exports,
            "successful_exports": successful_exports,
            "success_rate": f"{(successful_exports/total_exports*100):.1f}%" if total_exports > 0 else "0%"
        }
    }
    
    summary_file = analysis_folder / "export_execution_summary_v2.json"
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"📄 Export summary saved: {summary_file}")
    
    if successful_exports > 0:
        return 0
    else:
        return 1

if __name__ == "__main__":
    sys.exit(main())