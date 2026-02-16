#!/usr/bin/env python3
"""
🎬 DaVinci Resolve OpenClaw - Simplified Social Media Export
Export social media clips using existing timelines with different render settings.
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

def setup_render_preset(project, preset_name, preset_config):
    """Setup render settings for a specific social media format"""
    try:
        # Configure render settings based on preset
        render_settings = {}
        
        config = preset_config
        
        # Basic settings
        render_settings["TargetDir"] = str(Path.cwd() / "exports" / "social_media")
        render_settings["CustomName"] = preset_name  # Will be overridden per clip
        
        # Resolution - using the field names from working code
        render_settings["FormatWidth"] = str(config["resolution"]["width"])
        render_settings["FormatHeight"] = str(config["resolution"]["height"])
        
        print(f"✅ Configured render settings for: {preset_config['name']}")
        return render_settings
        
    except Exception as e:
        print(f"❌ Error setting up render preset {preset_name}: {e}")
        return None

def export_social_clip(resolve, timeline, clip_data, export_variant, presets):
    """Export a social media clip with specific timing and format"""
    try:
        project_manager = resolve.GetProjectManager()
        project = project_manager.GetCurrentProject()
        
        if not project or not timeline:
            print("❌ No project or timeline available")
            return False
        
        preset_name = export_variant["preset"]
        preset_config = presets["presets"][preset_name]
        
        # Set current timeline
        project.SetCurrentTimeline(timeline)
        
        # Setup render settings for this format
        render_settings = setup_render_preset(project, preset_name, preset_config)
        if not render_settings:
            return False
        
        # Set the timeline manually to the desired in/out points
        start_seconds = clip_data["start_seconds"]
        duration_seconds = clip_data["duration_seconds"]
        
        # Convert to frames (assuming 24fps for compatibility with existing system)
        fps = 24.0
        start_frame = int(start_seconds * fps)
        end_frame = int((start_seconds + duration_seconds) * fps)
        
        # Set mark in/out on the timeline itself
        timeline.SetStartFrame(start_frame)
        timeline.SetEndFrame(end_frame)
        
        # Generate output filename
        output_filename = f"{clip_data['clip_name']}_{preset_name}_{int(duration_seconds)}s"
        render_settings["CustomName"] = output_filename
        
        # Ensure output directory exists
        output_dir = Path(render_settings["TargetDir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Set format and codec (like the working example)
        project.SetCurrentRenderFormatAndCodec("mp4", "H264")
        
        # Apply render settings to the project
        success = project.SetRenderSettings(render_settings)
        if not success:
            print(f"❌ Failed to apply render settings for {output_filename}")
            return False
        
        # Add to render queue
        render_job_id = project.AddRenderJob()
        if not render_job_id:
            print(f"❌ Failed to add render job for {output_filename}")
            return False
        
        print(f"✅ Queued for render: {output_filename} ({start_seconds}s-{start_seconds+duration_seconds}s)")
        return True
        
    except Exception as e:
        print(f"❌ Error exporting clip: {e}")
        return False

def process_social_exports(analysis_folder):
    """Process all social media exports from analysis results"""
    print(f"🎬 DaVinci Resolve OpenClaw - Simplified Social Export")
    print(f"📁 Analysis Folder: {analysis_folder}")
    print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Load analysis data
    strategy, presets = load_analysis_data(analysis_folder)
    if not strategy or not presets:
        return False
    
    print(f"📊 Loaded export strategy: {len(strategy['exports'])} clips")
    print(f"🎨 Available presets: {len(presets['presets'])}")
    
    # Connect to DaVinci Resolve
    resolve = get_resolve_connection()
    if not resolve:
        return False
    
    project_manager = resolve.GetProjectManager()
    project = project_manager.GetCurrentProject()
    
    if not project:
        print("❌ No project loaded in DaVinci Resolve")
        return False
    
    print(f"✅ Connected to DaVinci Resolve")
    
    # Find the source timeline
    source_timeline_name = strategy["timeline_name"]
    source_timeline = None
    
    for i in range(project.GetTimelineCount()):
        timeline = project.GetTimelineByIndex(i + 1)
        if timeline and timeline.GetName() == source_timeline_name:
            source_timeline = timeline
            break
    
    if not source_timeline:
        print(f"❌ Source timeline '{source_timeline_name}' not found")
        return False
    
    print(f"✅ Found source timeline: {source_timeline_name}")
    
    # Process each clip
    successful_exports = 0
    total_exports = sum(len(clip["export_variants"]) for clip in strategy["exports"])
    
    for clip in strategy["exports"]:
        clip_name = clip["clip_name"]
        print(f"\n🎞️  Processing: {clip_name}")
        print(f"   Description: {clip['clip_description']}")
        print(f"   Duration: {clip['duration_seconds']}s ({clip['start_seconds']}s - {clip['start_seconds'] + clip['duration_seconds']}s)")
        
        for variant in clip["export_variants"]:
            if variant["preset"] not in presets["presets"]:
                print(f"   ❌ Preset not found: {variant['preset']}")
                continue
                
            preset_config = presets["presets"][variant["preset"]]
            print(f"   📱 Export variant: {preset_config['name']} ({variant['priority']} priority)")
            
            # Export the clip
            if export_social_clip(resolve, source_timeline, clip, variant, presets):
                successful_exports += 1
            else:
                print(f"   ❌ Failed to queue export")
    
    print("\n" + "=" * 60)
    print("📊 EXPORT SUMMARY")
    print(f"✅ Successfully queued: {successful_exports}/{total_exports}")
    print(f"📁 Output directory: exports/social_media/")
    print(f"⏰ Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if successful_exports > 0:
        print("\n🚀 NEXT STEPS:")
        print("1. Check DaVinci Resolve render queue")
        print("2. Start rendering: project.StartRendering()")
        print("3. Monitor render progress in DaVinci Resolve")
        print("4. Check exports/social_media/ for completed files")
    
    # Create summary file
    summary = {
        "export_run": {
            "timestamp": datetime.now().isoformat(),
            "analysis_folder": str(analysis_folder),
            "total_clips": len(strategy["exports"]),
            "total_exports": total_exports,
            "successful_exports": successful_exports,
            "success_rate": f"{(successful_exports/total_exports*100):.1f}%" if total_exports > 0 else "0%"
        }
    }
    
    summary_path = Path(analysis_folder) / "simplified_export_summary.json"
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"📄 Export summary saved: {summary_path}")
    return successful_exports == total_exports

def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        # Use most recent analysis folder
        social_clips_dir = Path("social_clips")
        if social_clips_dir.exists():
            folders = [f for f in social_clips_dir.iterdir() if f.is_dir()]
            if folders:
                analysis_folder = max(folders, key=lambda x: x.stat().st_mtime)
                print(f"🔍 Using most recent analysis: {analysis_folder}")
            else:
                print("❌ No analysis folders found in social_clips/")
                return False
        else:
            print("❌ social_clips directory not found")
            return False
    else:
        analysis_folder = Path(sys.argv[1])
        
    if not analysis_folder.exists():
        print(f"❌ Analysis folder not found: {analysis_folder}")
        return False
        
    return process_social_exports(analysis_folder)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)