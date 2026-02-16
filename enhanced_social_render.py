#!/usr/bin/env python3
"""
🎬 Enhanced Social Media Render System
Automatically handles batch rendering of social media timelines once they're created.

This script works in conjunction with the streamlined workflow to provide
full automation for the render phase.
"""

import os
import sys
from pathlib import Path
from datetime import datetime
import time
import json
from typing import List, Dict, Tuple, Optional

def get_resolve_connection():
    """Connect to DaVinci Resolve using proper API setup"""
    try:
        RESOLVE_SCRIPT_API = "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting"
        RESOLVE_SCRIPT_LIB = "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so"

        os.environ["RESOLVE_SCRIPT_API"] = RESOLVE_SCRIPT_API
        os.environ["RESOLVE_SCRIPT_LIB"] = RESOLVE_SCRIPT_LIB

        resolve_script_modules = f"{RESOLVE_SCRIPT_API}/Modules/"
        if resolve_script_modules not in sys.path:
            sys.path.append(resolve_script_modules)

        import DaVinciResolveScript as dvr_script
        resolve = dvr_script.scriptapp("Resolve")
        
        if resolve:
            return resolve
        else:
            print("❌ Failed to connect to DaVinci Resolve")
            return None
    except Exception as e:
        print(f"❌ Error connecting to DaVinci Resolve: {e}")
        return None

def get_available_render_presets(project) -> Dict[str, str]:
    """Get all available render presets from DaVinci Resolve"""
    try:
        preset_list = project.GetPresetList()
        if preset_list:
            print(f"✅ Found {len(preset_list)} render presets:")
            for i, preset in enumerate(preset_list):
                print(f"   {i+1}. {preset}")
            return {preset: preset for preset in preset_list}
        else:
            print("⚠️  No render presets found")
            return {}
    except Exception as e:
        print(f"❌ Error getting render presets: {e}")
        return {}

def create_social_media_presets() -> Dict[str, Dict]:
    """Define social media render presets with optimal settings"""
    return {
        "TikTok Vertical 9:16": {
            "format": "H.264",
            "codec": "H.264",
            "width": 1080,
            "height": 1920,
            "framerate": 30,
            "bitrate": 8000,
            "description": "TikTok/Instagram Stories vertical format"
        },
        "Instagram Reels 9:16": {
            "format": "H.264", 
            "codec": "H.264",
            "width": 1080,
            "height": 1920,
            "framerate": 30,
            "bitrate": 10000,
            "description": "Instagram Reels optimized vertical"
        },
        "YouTube HD 1080p": {
            "format": "H.264",
            "codec": "H.264", 
            "width": 1920,
            "height": 1080,
            "framerate": 30,
            "bitrate": 12000,
            "description": "YouTube 1080p standard"
        },
        "LinkedIn Optimized 16:9": {
            "format": "H.264",
            "codec": "H.264",
            "width": 1920,
            "height": 1080,
            "framerate": 30,
            "bitrate": 8000,
            "description": "LinkedIn business content"
        },
        "Facebook Optimized 16:9": {
            "format": "H.264",
            "codec": "H.264",
            "width": 1920,
            "height": 1080,
            "framerate": 30,
            "bitrate": 8000,
            "description": "Facebook video posts"
        },
        "Twitter Optimized 16:9": {
            "format": "H.264",
            "codec": "H.264",
            "width": 1280,
            "height": 720,
            "framerate": 30,
            "bitrate": 6000,
            "description": "Twitter video posts"
        },
        "Universal CTA 16:9": {
            "format": "H.264",
            "codec": "H.264",
            "width": 1920,
            "height": 1080,
            "framerate": 30,
            "bitrate": 10000,
            "description": "Universal call-to-action format"
        }
    }

def detect_social_timelines(project) -> List[Tuple[str, str]]:
    """Detect timelines that match the social media naming convention"""
    social_timelines = []
    
    try:
        timeline_count = project.GetTimelineCount()
        print(f"📊 Scanning {timeline_count} timelines for social media clips...")
        
        social_keywords = ["social_", "Social_", "tiktok", "instagram", "linkedin", "youtube", "twitter", "facebook"]
        
        for i in range(timeline_count):
            timeline = project.GetTimelineByIndex(i + 1)
            if timeline:
                name = timeline.GetName()
                
                # Check if timeline matches social media naming pattern
                if any(keyword.lower() in name.lower() for keyword in social_keywords):
                    social_timelines.append((name, "auto-detected"))
                    print(f"   🎬 Found social timeline: {name}")
                    
        return social_timelines
        
    except Exception as e:
        print(f"❌ Error detecting social timelines: {e}")
        return []

def create_render_jobs(project, social_timelines: List[Tuple[str, str]], output_dir: Path) -> List[Dict]:
    """Create render jobs for social media timelines"""
    render_jobs = []
    presets = create_social_media_presets()
    
    print(f"🎬 Creating render jobs for {len(social_timelines)} social timelines")
    
    for timeline_name, preset_hint in social_timelines:
        try:
            # Find the timeline
            timeline = None
            timeline_count = project.GetTimelineCount()
            
            for i in range(timeline_count):
                t = project.GetTimelineByIndex(i + 1)
                if t and t.GetName() == timeline_name:
                    timeline = t
                    break
            
            if not timeline:
                print(f"   ❌ Timeline not found: {timeline_name}")
                continue
            
            # Determine best preset based on timeline name
            best_preset = None
            if "vertical" in timeline_name.lower() or "9:16" in timeline_name:
                best_preset = "TikTok Vertical 9:16"
            elif "instagram" in timeline_name.lower():
                best_preset = "Instagram Reels 9:16"
            elif "linkedin" in timeline_name.lower():
                best_preset = "LinkedIn Optimized 16:9"
            elif "youtube" in timeline_name.lower():
                best_preset = "YouTube HD 1080p"
            elif "twitter" in timeline_name.lower():
                best_preset = "Twitter Optimized 16:9"
            elif "facebook" in timeline_name.lower():
                best_preset = "Facebook Optimized 16:9"
            else:
                best_preset = "YouTube HD 1080p"  # Default
            
            # Generate output filename
            clean_name = timeline_name.replace(" ", "_").replace("-", "_")
            preset_info = presets[best_preset]
            output_filename = f"{clean_name}_{preset_info['width']}x{preset_info['height']}.mp4"
            output_path = output_dir / output_filename
            
            render_job = {
                "timeline_name": timeline_name,
                "preset_name": best_preset,
                "preset_settings": preset_info,
                "output_path": str(output_path),
                "output_filename": output_filename,
                "estimated_size_mb": estimate_file_size(timeline, preset_info),
                "status": "queued"
            }
            
            render_jobs.append(render_job)
            print(f"   ✅ Queued: {timeline_name} → {best_preset} → {output_filename}")
            
        except Exception as e:
            print(f"   ❌ Error creating render job for {timeline_name}: {e}")
    
    return render_jobs

def estimate_file_size(timeline, preset_info: Dict) -> int:
    """Estimate output file size in MB"""
    try:
        # Get timeline duration
        start_frame = timeline.GetStartFrame()
        end_frame = timeline.GetEndFrame()
        duration_frames = end_frame - start_frame
        fps = float(timeline.GetSetting("timelineFrameRate")) or 30.0
        duration_seconds = duration_frames / fps
        
        # Estimate based on bitrate
        bitrate_kbps = preset_info.get("bitrate", 8000)  # Default 8Mbps
        size_mb = (bitrate_kbps * duration_seconds) / (8 * 1024)  # Convert to MB
        
        return int(size_mb)
        
    except Exception:
        return 50  # Default estimate

def execute_render_batch(project, render_jobs: List[Dict]) -> Dict[str, int]:
    """Execute the batch render jobs (simulation since API write is blocked)"""
    print(f"\n🎬 Batch Render Execution Plan")
    print("=" * 50)
    
    results = {"queued": 0, "ready": 0, "estimated_total_mb": 0}
    
    for i, job in enumerate(render_jobs, 1):
        print(f"\nRender Job {i}/{len(render_jobs)}:")
        print(f"   📽️  Timeline: {job['timeline_name']}")
        print(f"   🎨 Preset: {job['preset_name']}")
        print(f"   📁 Output: {job['output_filename']}")
        print(f"   📏 Size: ~{job['estimated_size_mb']} MB")
        
        # Since API write is blocked, we'll simulate the process
        print(f"   ⏳ Status: Ready for manual execution")
        results["ready"] += 1
        results["estimated_total_mb"] += job["estimated_size_mb"]
    
    print(f"\n📊 Batch Render Summary:")
    print(f"   🎬 Total jobs: {len(render_jobs)}")
    print(f"   ✅ Ready for render: {results['ready']}")
    print(f"   📦 Estimated total size: {results['estimated_total_mb']} MB")
    print(f"   ⏱️  Estimated render time: {len(render_jobs) * 3}-{len(render_jobs) * 5} minutes")
    
    return results

def generate_manual_render_guide(render_jobs: List[Dict], output_dir: Path) -> str:
    """Generate a manual render guide for the user"""
    
    guide_content = f"""
# 🎬 Manual Render Guide - Social Media Batch Export
**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**Output Directory**: {output_dir}  
**Total Render Jobs**: {len(render_jobs)}

## Quick Execution Steps:

### 1. Open Render Queue (Ctrl+Shift+R / Cmd+Shift+R)

### 2. Add Each Timeline to Render Queue:
"""
    
    for i, job in enumerate(render_jobs, 1):
        guide_content += f"""
#### Job {i}: {job['timeline_name']}
- **Select Timeline**: "{job['timeline_name']}"
- **Output Settings**:
  - Format: {job['preset_settings']['format']}
  - Codec: {job['preset_settings']['codec']}  
  - Resolution: {job['preset_settings']['width']}x{job['preset_settings']['height']}
  - Frame Rate: {job['preset_settings']['framerate']} fps
  - Bitrate: {job['preset_settings']['bitrate']} kbps
- **Output File**: `{job['output_filename']}`
- **Estimated Size**: ~{job['estimated_size_mb']} MB
"""
    
    total_mb = sum(job['estimated_size_mb'] for job in render_jobs)
    total_time = len(render_jobs) * 4  # Average 4 minutes per job
    
    guide_content += f"""

## Summary:
- **Total Render Jobs**: {len(render_jobs)}
- **Estimated Total Size**: {total_mb} MB ({total_mb/1024:.1f} GB)
- **Estimated Render Time**: {total_time} minutes
- **Output Directory**: `{output_dir}`

## After Rendering:
```bash
# Verify all outputs are created
ls -la "{output_dir}"

# Check total size  
du -sh "{output_dir}"

# Quality check (optional)
python3 verify_social_outputs.py "{output_dir}"
```

---
*Generated by DaVinci Resolve OpenClaw - Enhanced Social Render System*
"""
    
    guide_path = output_dir / "manual_render_guide.md"
    with open(guide_path, 'w') as f:
        f.write(guide_content)
    
    print(f"📋 Manual render guide saved: {guide_path}")
    return str(guide_path)

def main():
    """Main execution function"""
    print("🎬 DaVinci Resolve OpenClaw - Enhanced Social Render System")
    print("=" * 60)
    
    # Connect to Resolve
    resolve = get_resolve_connection()
    if not resolve:
        print("❌ Cannot proceed without DaVinci Resolve connection")
        return False
    
    try:
        # Get current project
        project_manager = resolve.GetProjectManager()
        project = project_manager.GetCurrentProject()
        
        if not project:
            print("❌ No project loaded in DaVinci Resolve")
            return False
        
        print(f"✅ Connected to project: {project.GetName()}")
        
        # Create output directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path("social_exports") / f"batch_{timestamp}"
        output_dir.mkdir(parents=True, exist_ok=True)
        print(f"📁 Output directory: {output_dir}")
        
        # Detect social media timelines
        social_timelines = detect_social_timelines(project)
        
        if not social_timelines:
            print("⚠️  No social media timelines detected.")
            print("💡 Create timelines with names containing: social_, Social_, tiktok, instagram, etc.")
            return False
        
        print(f"🎯 Found {len(social_timelines)} social media timelines")
        
        # Create render jobs
        render_jobs = create_render_jobs(project, social_timelines, output_dir)
        
        if not render_jobs:
            print("❌ No render jobs could be created")
            return False
        
        # Execute batch render (simulation)
        results = execute_render_batch(project, render_jobs)
        
        # Generate manual guide
        guide_path = generate_manual_render_guide(render_jobs, output_dir)
        
        # Save render jobs as JSON for reference
        jobs_path = output_dir / "render_jobs.json"
        with open(jobs_path, 'w') as f:
            json.dump(render_jobs, f, indent=2)
        
        print(f"\n🎉 Enhanced Social Render System Complete!")
        print(f"📋 Manual render guide: {guide_path}")
        print(f"🎬 Render jobs data: {jobs_path}")
        print(f"📁 Output directory: {output_dir}")
        print(f"✅ {results['ready']} render jobs ready for execution")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during enhanced social render: {e}")
        return False

if __name__ == "__main__":
    success = main()
    if success:
        print("\n🚀 Ready for social media domination!")
    else:
        print("\n🚧 Check the issues above and try again")