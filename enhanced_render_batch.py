#!/usr/bin/env python3
"""Enhanced batch rendering for professional delivery formats."""

import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime

from resolve_bridge import get_resolve
from auto_export import create_render_job, monitor_render_progress, get_timeline_info
from enhanced_render_presets import ENHANCED_RENDER_PRESETS

def batch_render_professional_formats(timeline_name=None, formats=None):
    """Render multiple professional formats in batch.
    
    Args:
        timeline_name: Name of timeline to render (current if None)
        formats: List of format names to render (default professional set)
    """
    if formats is None:
        # Default professional formats for client delivery
        formats = [
            "broadcast_prores422hq",  # Professional broadcast 
            "client_review_hq",       # High quality client review
            "vimeo_hq",              # Cinematic 24fps
            "web_streaming",         # Web optimized
            "client_review_compressed"  # Email friendly
        ]
    
    print("🎬 Enhanced Professional Batch Render")
    print("=" * 50)
    print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📹 Formats: {', '.join(formats)}")
    print()
    
    # Connect to DaVinci Resolve
    try:
        resolve = get_resolve()
        project_manager = resolve.GetProjectManager()
        project = project_manager.GetCurrentProject()
        
        if not project:
            print("❌ No project loaded")
            return False
            
        print(f"📁 Project: {project.GetName()}")
        
        # Get timeline
        if timeline_name:
            timeline = None
            timeline_count = project.GetTimelineCount()
            for i in range(1, timeline_count + 1):
                tl = project.GetTimelineByIndex(i)
                if tl.GetName() == timeline_name:
                    timeline = tl
                    break
            if not timeline:
                print(f"❌ Timeline '{timeline_name}' not found")
                return False
        else:
            timeline = project.GetCurrentTimeline()
            if not timeline:
                print("❌ No current timeline")
                return False
        
        timeline_info = get_timeline_info(timeline)
        if not timeline_info:
            print("❌ Could not get timeline information")
            return False
            
        print(f"🎞️  Timeline: {timeline_info.get('name', 'Unknown')}")
        print(f"   Resolution: {timeline_info.get('resolution', ['?', '?'])[0]}x{timeline_info.get('resolution', ['?', '?'])[1]}")
        print(f"   Frame Rate: {timeline_info.get('fps', '?')}fps") 
        print(f"   Duration: {timeline_info.get('duration', '?')} frames")
        print()
        
        # Create output directory
        output_dir = Path("renders") / "professional_batch" / datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"📁 Output Directory: {output_dir}")
        print()
        
        # Track results
        results = {
            "timeline": timeline_info['name'],
            "started": datetime.now().isoformat(),
            "formats": {},
            "total_formats": len(formats),
            "successful": 0,
            "failed": 0
        }
        
        # Render each format
        for i, format_name in enumerate(formats, 1):
            print(f"🎬 [{i}/{len(formats)}] Rendering: {format_name}")
            
            if format_name in ENHANCED_RENDER_PRESETS:
                preset = ENHANCED_RENDER_PRESETS[format_name]
            else:
                # Try original presets
                from auto_export import RENDER_PRESETS
                if format_name in RENDER_PRESETS:
                    preset = RENDER_PRESETS[format_name]
                else:
                    print(f"   ❌ Unknown format: {format_name}")
                    results["formats"][format_name] = {"status": "unknown_format"}
                    results["failed"] += 1
                    continue
            
            print(f"   📝 {preset['description']}")
            
            # Create render job
            job_id = create_render_job(project, timeline, format_name, str(output_dir))
            
            if not job_id:
                print(f"   ❌ Failed to create render job")
                results["formats"][format_name] = {"status": "job_creation_failed"}
                results["failed"] += 1
                continue
            
            # Monitor render
            render_result = monitor_render_progress(project, job_id, timeout=1800)  # 30 min timeout
            
            if render_result.get("status") == "completed":
                print(f"   ✅ Completed successfully")
                file_size = render_result.get("file_size", "unknown")
                results["formats"][format_name] = {
                    "status": "completed", 
                    "job_id": job_id,
                    "file_size": file_size,
                    "duration": render_result.get("duration", 0)
                }
                results["successful"] += 1
            else:
                print(f"   ❌ Failed: {render_result.get('error', 'Unknown error')}")
                results["formats"][format_name] = {
                    "status": "failed",
                    "job_id": job_id,
                    "error": render_result.get("error", "Unknown error")
                }
                results["failed"] += 1
            
            print()
        
        # Summary
        results["completed"] = datetime.now().isoformat()
        results["total_duration"] = (datetime.fromisoformat(results["completed"]) - 
                                   datetime.fromisoformat(results["started"])).total_seconds()
        
        print("=" * 50)
        print("📊 BATCH RENDER SUMMARY")
        print("=" * 50)
        print(f"✅ Successful: {results['successful']}")
        print(f"❌ Failed: {results['failed']}")
        print(f"⏱️  Total Duration: {results['total_duration']:.1f} seconds")
        print(f"📁 Output Location: {output_dir}")
        
        # Save results
        results_file = output_dir / "batch_render_results.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"📄 Results saved: {results_file}")
        
        # List output files
        output_files = list(output_dir.glob("*.*"))
        if output_files:
            print("\n📹 Generated Files:")
            for file_path in sorted(output_files):
                if file_path.suffix in ['.mp4', '.mov', '.wav']:
                    size_mb = file_path.stat().st_size / (1024*1024)
                    print(f"   {file_path.name} ({size_mb:.1f} MB)")
        
        return results["successful"] > 0
        
    except Exception as e:
        print(f"❌ Batch render failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Enhanced batch rendering for professional delivery')
    parser.add_argument('--timeline', help='Timeline name to render (current if not specified)')
    parser.add_argument('--formats', nargs='+', help='Specific formats to render')
    parser.add_argument('--list', action='store_true', help='List available formats')
    
    args = parser.parse_args()
    
    if args.list:
        from enhanced_render_presets import print_all_presets
        print_all_presets()
        return
    
    success = batch_render_professional_formats(
        timeline_name=args.timeline,
        formats=args.formats
    )
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()