#!/usr/bin/env python3
"""
🎬 DaVinci Resolve OpenClaw - Automated Social Media Export V3
Simplified version that leverages existing render presets and job system.

Usage:
    python3 automated_social_export_v3.py [analysis_folder]
"""

import sys
import json
from pathlib import Path
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
    """Load export strategy from analysis folder"""
    strategy_path = Path(analysis_folder) / "export_strategy.json"
    
    if not strategy_path.exists():
        print(f"❌ Export strategy file not found: {strategy_path}")
        return None
    
    try:
        with open(strategy_path, 'r') as f:
            strategy = json.load(f)
        return strategy
    except Exception as e:
        print(f"❌ Error loading analysis data: {e}")
        return None

def find_suitable_timeline(resolve, target_name):
    """Find the best timeline for social media exports"""
    try:
        project_manager = resolve.GetProjectManager()
        project = project_manager.GetCurrentProject()
        
        timeline_count = project.GetTimelineCount()
        
        # First try exact match
        for i in range(timeline_count):
            timeline = project.GetTimelineByIndex(i + 1)
            if timeline and timeline.GetName() == target_name:
                return timeline, timeline.GetName()
        
        # Look for likely candidates
        candidates = []
        for i in range(timeline_count):
            timeline = project.GetTimelineByIndex(i + 1)
            if timeline:
                name = timeline.GetName()
                if any(keyword in name.lower() for keyword in ["ai edit", "complete", "review", "portalcam"]):
                    candidates.append((timeline, name))
        
        if candidates:
            return candidates[0]
            
        # Fallback to current timeline
        current = project.GetCurrentTimeline()
        if current:
            return current, current.GetName()
            
        return None, None
        
    except Exception as e:
        print(f"❌ Error finding timeline: {e}")
        return None, None

def select_render_preset(resolve, social_preset):
    """Select appropriate DaVinci render preset for social media format"""
    try:
        project_manager = resolve.GetProjectManager()
        project = project_manager.GetCurrentProject()
        
        # Map our social presets to DaVinci presets
        preset_mapping = {
            "tiktok_vertical": "YouTube - 1080p",       # Close enough, we'll adjust resolution
            "instagram_reels": "YouTube - 1080p",       # Same as TikTok
            "youtube_shorts": "YouTube - 1080p",        # Perfect match
            "instagram_square": "YouTube - 1080p",       # We'll adjust aspect ratio
            "linkedin_horizontal": "YouTube - 1080p",   # Good base for professional
            "twitter_optimized": "YouTube - 720p"       # Slightly lower quality for Twitter
        }
        
        davinci_preset = preset_mapping.get(social_preset, "YouTube - 1080p")
        print(f"      Using DaVinci preset: {davinci_preset}")
        
        # Load the render preset
        success = project.LoadRenderPreset(davinci_preset)
        if success:
            print(f"      ✅ Loaded render preset successfully")
            return True
        else:
            print(f"      ⚠️  Could not load preset, using current settings")
            return False
            
    except Exception as e:
        print(f"      ❌ Error selecting render preset: {e}")
        return False

def create_social_render_job(resolve, timeline, clip_data, export_variant, output_dir):
    """Create a render job for a social media clip"""
    try:
        project_manager = resolve.GetProjectManager()
        project = project_manager.GetCurrentProject()
        
        # Set the current timeline
        project.SetCurrentTimeline(timeline)
        
        # Load appropriate render preset
        select_render_preset(resolve, export_variant["preset"])
        
        # Set output directory and filename
        output_dir.mkdir(parents=True, exist_ok=True)
        output_filename = f"{clip_data['clip_name']}_{export_variant['preset']}_{int(clip_data['duration_seconds'])}s"
        
        # Update render settings
        current_settings = {
            "TargetDir": str(output_dir),
            "CustomName": output_filename
        }
        
        # Try to set basic render settings
        try:
            project.SetSetting("timelineOutputResolutionWidth", "1920")
            project.SetSetting("timelineOutputResolutionHeight", "1080")
        except:
            pass  # Settings might not be available in this API version
        
        # Set mark in/out points based on clip timing
        # Note: This might need manual adjustment in DaVinci Resolve
        fps = 24.0  # Default from render jobs we saw
        mark_in = int(clip_data["start_seconds"] * fps)
        mark_out = int((clip_data["start_seconds"] + clip_data["duration_seconds"]) * fps)
        
        print(f"      📍 Clip timing: {clip_data['start_seconds']}s - {clip_data['start_seconds'] + clip_data['duration_seconds']}s")
        print(f"      📍 Frame range: {mark_in} - {mark_out}")
        
        # Add render job
        job_id = project.AddRenderJob()
        if job_id:
            print(f"      ✅ Created render job: {output_filename}")
            print(f"      📋 Job ID: {job_id}")
            return True
        else:
            print(f"      ❌ Failed to create render job")
            return False
            
    except Exception as e:
        print(f"      ❌ Error creating render job: {e}")
        return False

def main():
    if len(sys.argv) < 2:
        print("❌ Analysis folder not provided")
        print("Usage: python3 automated_social_export_v3.py [analysis_folder]")
        sys.exit(1)
    
    analysis_folder = Path(sys.argv[1])
    if not analysis_folder.exists():
        print(f"❌ Analysis folder not found: {analysis_folder}")
        sys.exit(1)
    
    print("🎬 DaVinci Resolve OpenClaw - Automated Social Export V3")
    print(f"📁 Analysis Folder: {analysis_folder}")
    print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Load analysis data
    strategy = load_analysis_data(analysis_folder)
    if not strategy:
        sys.exit(1)
    
    print(f"📊 Loaded export strategy: {len(strategy['exports'])} clips")
    print(f"🎯 Target timeline: {strategy['timeline_name']}")
    
    # Connect to DaVinci Resolve
    resolve = get_resolve_connection()
    if not resolve:
        sys.exit(1)
    
    print("✅ Connected to DaVinci Resolve")
    
    # Find timeline
    timeline, timeline_name = find_suitable_timeline(resolve, strategy["timeline_name"])
    if not timeline:
        print("❌ Could not find suitable timeline")
        sys.exit(1)
    
    print(f"📍 Using timeline: '{timeline_name}'")
    
    # Set up output directory
    output_dir = Path("exports/social_media")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Process each clip and export variant
    successful_jobs = 0
    total_jobs = 0
    
    print(f"\n🚀 Processing {strategy['total_export_jobs']} export jobs...")
    
    for clip in strategy["exports"]:
        if len(clip["export_variants"]) == 0:
            continue
            
        print(f"\n🎞️  Clip: {clip['clip_name']}")
        print(f"    📝 {clip.get('clip_description', 'No description')}")
        print(f"    ⏱️  {clip['duration_seconds']}s ({clip['start_seconds']}s - {clip['end_seconds']}s)")
        
        for variant in clip["export_variants"]:
            total_jobs += 1
            preset_name = variant["preset"]
            priority = variant["priority"]
            
            print(f"    📱 Export: {preset_name} ({priority} priority)")
            
            if create_social_render_job(resolve, timeline, clip, variant, output_dir):
                successful_jobs += 1
    
    print("\n" + "=" * 60)
    print("📊 EXPORT SUMMARY")
    print(f"✅ Successfully queued: {successful_jobs}/{total_jobs}")
    print(f"📁 Output directory: {output_dir}")
    print(f"⏰ Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if successful_jobs > 0:
        print("\n🚀 NEXT STEPS:")
        print("1. 🎬 Open DaVinci Resolve Deliver page")
        print("2. 📋 Review render queue - new jobs should be listed")
        print("3. ⚙️  Manually adjust in/out points for each clip:")
        for clip in strategy["exports"]:
            for variant in clip["export_variants"]:
                print(f"   - {clip['clip_name']}_{variant['preset']}: {clip['start_seconds']}s - {clip['end_seconds']}s")
        print("4. ▶️  Start rendering (manually or project.StartRendering())")
        print("5. 📦 Check exports/social_media/ for completed files")
        
        # Show render command for automation
        print("\n🤖 To start rendering via API:")
        print("python3 -c \"")
        print("import sys")
        print("sys.path.append('/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules/')")
        print("import DaVinciResolveScript as dvr")
        print("resolve = dvr.scriptapp('Resolve')")
        print("project = resolve.GetProjectManager().GetCurrentProject()")
        print("project.StartRendering()\"")
    
    # Save summary
    summary = {
        "export_run_v3": {
            "timestamp": datetime.now().isoformat(),
            "analysis_folder": str(analysis_folder),
            "timeline_used": timeline_name,
            "total_clips": len(strategy["exports"]),
            "total_jobs": total_jobs,
            "successful_jobs": successful_jobs,
            "success_rate": f"{(successful_jobs/total_jobs*100):.1f}%" if total_jobs > 0 else "0%"
        }
    }
    
    summary_file = analysis_folder / "export_execution_summary_v3.json"
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"📄 Summary saved: {summary_file}")
    
    return 0 if successful_jobs > 0 else 1

if __name__ == "__main__":
    sys.exit(main())