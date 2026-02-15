#!/usr/bin/env python3
"""Simple professional format render for current timeline."""

import os
import sys
from datetime import datetime
from pathlib import Path

from resolve_bridge import get_resolve

def render_professional_formats():
    """Render key professional formats for current timeline."""
    print("🎬 Professional Format Render")
    print("=" * 40)
    print(f"⏰ Started: {datetime.now().strftime('%H:%M:%S')}")
    
    try:
        # Connect to Resolve
        resolve = get_resolve()
        project_manager = resolve.GetProjectManager()
        project = project_manager.GetCurrentProject()
        
        if not project:
            print("❌ No project loaded")
            return False
            
        timeline = project.GetCurrentTimeline()
        if not timeline:
            print("❌ No current timeline")
            return False
        
        project_name = project.GetName()
        timeline_name = timeline.GetName()
        
        print(f"📁 Project: {project_name}")
        print(f"🎞️  Timeline: {timeline_name}")
        print()
        
        # Create output directory
        output_dir = Path("renders") / "professional" / datetime.now().strftime("%Y%m%d_%H%M")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"📁 Output: {output_dir}")
        print()
        
        # Define professional render settings
        professional_formats = {
            "ProRes_HQ": {
                "format": "mov",
                "codec": "ProRes422HQ",
                "description": "Professional ProRes HQ for editing/grading"
            },
            "Client_Review": {  
                "format": "mp4",
                "codec": "H264",
                "description": "High quality client review (H.264)"
            },
            "Vimeo_24p": {
                "format": "mp4", 
                "codec": "H264",
                "description": "Cinematic 24fps for Vimeo"
            }
        }
        
        results = {"successful": 0, "failed": 0}
        
        for format_name, settings in professional_formats.items():
            print(f"🎬 Rendering: {format_name}")
            print(f"   {settings['description']}")
            
            try:
                # Set basic render settings
                project.SetRenderSettings({
                    "SelectAllFrames": True,
                    "TargetDir": str(output_dir),
                    "CustomName": f"{timeline_name}_{format_name}",
                    "VideoFormat": settings["format"],
                    "VideoCodec": settings["codec"],
                    "VideoQuality": "High"
                })
                
                # Add to render queue
                job_id = project.AddRenderJob()
                
                if job_id:
                    print(f"   ✅ Render job queued: {job_id}")
                    results["successful"] += 1
                else:
                    print(f"   ❌ Failed to queue render job")
                    results["failed"] += 1
                    
            except Exception as e:
                print(f"   ❌ Error: {e}")
                results["failed"] += 1
            
            print()
        
        print("=" * 40)
        print(f"📊 Queued: {results['successful']} renders")
        print(f"❌ Failed: {results['failed']} renders")
        
        if results["successful"] > 0:
            print()
            print("🚀 Renders queued successfully!")
            print("   Check DaVinci Resolve's Deliver page for progress")
            print(f"   Output location: {output_dir}")
            
            return True
        else:
            return False
            
    except Exception as e:
        print(f"❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = render_professional_formats()
    sys.exit(0 if success else 1)