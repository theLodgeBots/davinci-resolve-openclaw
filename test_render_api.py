#!/usr/bin/env python3
"""
Test render API methods to see what's actually working
"""

import sys

def test_render_methods():
    try:
        # Add DaVinci Resolve scripting modules to path
        dvr_modules_path = '/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules/'
        if dvr_modules_path not in sys.path:
            sys.path.append(dvr_modules_path)
        import DaVinciResolveScript as dvr_script
        
        resolve = dvr_script.scriptapp("Resolve")
        pm = resolve.GetProjectManager()
        project = pm.GetCurrentProject()
        
        print("🔍 Testing render-related methods:")
        
        # Test getting render job list
        print("\n📋 Current render jobs:")
        jobs = project.GetRenderJobList()
        if jobs:
            print(f"   Found {len(jobs)} render jobs:")
            for i, job in enumerate(jobs):
                print(f"   {i+1}. {job}")
        else:
            print("   No render jobs found")
        
        # Test current render settings
        print("\n⚙️ Current render format and codec:")
        format_codec = project.GetCurrentRenderFormatAndCodec()
        print(f"   {format_codec}")
        
        # Test render presets
        print("\n🎨 Available render presets:")
        presets = project.GetRenderPresetList()
        if presets:
            print(f"   Found {len(presets)} presets:")
            for preset in presets[:10]:  # Show first 10
                print(f"   - {preset}")
        
        # Test render formats
        print("\n📺 Available render formats:")
        formats = project.GetRenderFormats()
        if formats:
            for format_name in formats[:5]:  # Show first 5
                print(f"   - {format_name}")
        
        # Test if we can just add a simple render job
        print("\n🚀 Testing simple render job creation:")
        job_id = project.AddRenderJob()
        if job_id:
            print(f"   ✅ Created render job with ID: {job_id}")
            
            # Check the job list again
            jobs_after = project.GetRenderJobList()
            print(f"   📋 Render jobs after creation: {len(jobs_after) if jobs_after else 0}")
        else:
            print("   ❌ Failed to create render job")
        
        # Test if we can start rendering
        print("\n▶️ Testing render start:")
        rendering_status = project.IsRenderingInProgress()
        print(f"   Current rendering status: {rendering_status}")
        
        if not rendering_status:
            print("   Attempting to start rendering...")
            start_result = project.StartRendering()
            print(f"   Start rendering result: {start_result}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_render_methods()