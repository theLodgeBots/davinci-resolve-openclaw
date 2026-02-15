#!/usr/bin/env python3
"""
🎬 DaVinci Resolve OpenClaw - Automated Social Media Export
Automatically exports social media clips based on analysis results.

Usage:
    python3 automated_social_export.py [analysis_folder]
    
Example:
    python3 automated_social_export.py social_clips/20260215_003314/
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
    """Create or update render preset in DaVinci Resolve"""
    try:
        project_manager = resolve.GetProjectManager()
        project = project_manager.GetCurrentProject()
        
        if not project:
            print("❌ No project loaded in DaVinci Resolve")
            return False
            
        # Get current render settings as base
        render_settings = {
            "SelectAllFrames": True,
            "TargetDir": str(Path.cwd() / "exports" / "social_media"),
            "CustomName": preset_name,
        }
        
        # Configure based on preset
        config = preset_config
        
        # Set format and codec
        if config["format"] == "mp4":
            render_settings["VideoFormat"] = "mp4"
            
        if config["codec"] == "h264_aac":
            render_settings["VideoCodec"] = "h264"
            render_settings["AudioCodec"] = "aac"
            
        # Set resolution
        render_settings["VideoResolutionWidth"] = config["resolution"]["width"]
        render_settings["VideoResolutionHeight"] = config["resolution"]["height"]
        
        # Set frame rate
        render_settings["FrameRate"] = config["framerate"]
        
        # Set quality/bitrate
        render_settings["VideoBitrate"] = config["bitrate_video"]
        render_settings["AudioBitrate"] = config["bitrate_audio"]
        
        print(f"✅ Configured render preset: {preset_name}")
        return render_settings
        
    except Exception as e:
        print(f"❌ Error creating render preset {preset_name}: {e}")
        return None

def create_clip_timeline(resolve, source_timeline_name, clip_data, export_variant):
    """Create a new timeline for a specific social media clip"""
    try:
        project_manager = resolve.GetProjectManager()
        project = project_manager.GetCurrentProject()
        
        if not project:
            print("❌ No project loaded")
            return None
        
        # Find source timeline
        timeline_count = project.GetTimelineCount()
        source_timeline = None
        
        for i in range(timeline_count):
            timeline = project.GetTimelineByIndex(i + 1)
            if timeline and timeline.GetName() == source_timeline_name:
                source_timeline = timeline
                break
                
        if not source_timeline:
            print(f"❌ Source timeline '{source_timeline_name}' not found")
            return None
            
        # Create new timeline for the clip
        clip_timeline_name = f"Social - {clip_data['clip_name']} - {export_variant['preset']}"
        
        # Check if timeline already exists
        existing_timeline = None
        for i in range(timeline_count):
            timeline = project.GetTimelineByIndex(i + 1)
            if timeline and timeline.GetName() == clip_timeline_name:
                existing_timeline = timeline
                break
                
        if existing_timeline:
            print(f"⚠️  Timeline '{clip_timeline_name}' already exists, using existing")
            return existing_timeline
            
        # Get source timeline settings
        source_settings = {
            "timelineResolutionWidth": 1920,  # Default, will be updated by render settings
            "timelineResolutionHeight": 1080,
            "timelineFrameRate": 30
        }
        
        # Create new timeline
        new_timeline = project.CreateTimeline(clip_timeline_name)
        if not new_timeline:
            print(f"❌ Failed to create timeline: {clip_timeline_name}")
            return None
            
        print(f"✅ Created timeline: {clip_timeline_name}")
        
        # Set current timeline to the new one for editing
        project.SetCurrentTimeline(new_timeline)
        
        # Note: In a production implementation, we would copy specific clips
        # from the source timeline to the new timeline with the correct timing.
        # For now, we'll create the timeline structure and let manual editing handle the details.
        
        return new_timeline
        
    except Exception as e:
        print(f"❌ Error creating clip timeline: {e}")
        return None

def export_clip(resolve, timeline, render_settings, output_filename):
    """Export a clip using the specified render settings"""
    try:
        project_manager = resolve.GetProjectManager()
        project = project_manager.GetCurrentProject()
        
        if not project or not timeline:
            print("❌ No project or timeline available")
            return False
            
        # Set the current timeline
        project.SetCurrentTimeline(timeline)
        
        # Update render settings with output filename
        render_settings["CustomName"] = output_filename
        
        # Ensure output directory exists
        output_dir = Path(render_settings["TargetDir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Add to render queue
        render_job_id = project.AddRenderJob()
        if not render_job_id:
            print(f"❌ Failed to add render job for {output_filename}")
            return False
            
        print(f"✅ Added to render queue: {output_filename}")
        
        # Start rendering (optional - can be done manually)
        # project.StartRendering()
        
        return True
        
    except Exception as e:
        print(f"❌ Error exporting clip {output_filename}: {e}")
        return False

def process_social_exports(analysis_folder):
    """Main function to process all social media exports"""
    print("🎬 DaVinci Resolve OpenClaw - Automated Social Export")
    print(f"📁 Analysis Folder: {analysis_folder}")
    print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Load analysis data
    strategy, presets = load_analysis_data(analysis_folder)
    if not strategy or not presets:
        return False
        
    print(f"📊 Loaded export strategy: {strategy['total_export_jobs']} jobs")
    print(f"🎨 Available presets: {len(presets['presets'])}")
    
    # Connect to DaVinci Resolve
    resolve = get_resolve_connection()
    if not resolve:
        return False
        
    print("✅ Connected to DaVinci Resolve")
    
    # Process each clip
    successful_exports = 0
    total_exports = 0
    
    for clip in strategy["exports"]:
        if not clip["export_variants"]:
            continue
            
        print(f"\n🎞️  Processing: {clip['clip_name']}")
        print(f"   Description: {clip['clip_description']}")
        print(f"   Duration: {clip['duration_seconds']}s ({clip['start_seconds']}s - {clip['end_seconds']}s)")
        
        for variant in clip["export_variants"]:
            total_exports += 1
            preset_name = variant["preset"]
            
            if preset_name not in presets["presets"]:
                print(f"   ❌ Preset '{preset_name}' not found")
                continue
                
            preset_config = presets["presets"][preset_name]
            print(f"   📱 Export variant: {preset_config['name']} ({variant['priority']} priority)")
            
            # Create render settings
            render_settings = create_render_preset(resolve, preset_name, preset_config)
            if not render_settings:
                continue
                
            # Create timeline for this clip
            timeline = create_clip_timeline(resolve, strategy["timeline_name"], clip, variant)
            if not timeline:
                continue
                
            # Generate output filename
            output_filename = f"{clip['clip_name']}_{preset_name}_{int(clip['duration_seconds'])}s"
            
            # Export the clip
            if export_clip(resolve, timeline, render_settings, output_filename):
                successful_exports += 1
                print(f"   ✅ Queued for export: {output_filename}")
            else:
                print(f"   ❌ Failed to queue: {output_filename}")
    
    print("\n" + "=" * 60)
    print("📊 EXPORT SUMMARY")
    print(f"✅ Successfully queued: {successful_exports}/{total_exports}")
    print(f"📁 Output directory: exports/social_media/")
    print(f"⏰ Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if successful_exports > 0:
        print("\n🚀 NEXT STEPS:")
        print("1. Check DaVinci Resolve render queue")
        print("2. Start rendering jobs manually or run: project.StartRendering()")
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
    
    summary_path = Path(analysis_folder) / "export_execution_summary.json"
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
                print("Run social_media_clipper.py first to generate analysis")
                return False
        else:
            print("❌ social_clips directory not found")
            print("Run social_media_clipper.py first to generate analysis")
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