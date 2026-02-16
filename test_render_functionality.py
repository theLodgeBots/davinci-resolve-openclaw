#!/usr/bin/env python3
"""
Test render functionality without creating new timelines
"""

import os
import sys

# Set up Resolve scripting environment
RESOLVE_SCRIPT_API = "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting"
RESOLVE_SCRIPT_LIB = "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so"

os.environ["RESOLVE_SCRIPT_API"] = RESOLVE_SCRIPT_API
os.environ["RESOLVE_SCRIPT_LIB"] = RESOLVE_SCRIPT_LIB

resolve_script_modules = f"{RESOLVE_SCRIPT_API}/Modules/"
if resolve_script_modules not in sys.path:
    sys.path.append(resolve_script_modules)

def test_render_functionality():
    """Test render functionality with existing timelines"""
    try:
        import DaVinciResolveScript as dvr_script
        resolve = dvr_script.scriptapp("Resolve")
        
        if not resolve:
            print("❌ Could not connect to DaVinci Resolve")
            return
        
        print("🎬 Render Functionality Test")
        print("=" * 40)
        
        project_manager = resolve.GetProjectManager()
        project = project_manager.GetCurrentProject()
        
        print(f"✅ Project: {project.GetName()}")
        print(f"✅ Timeline count: {project.GetTimelineCount()}")
        
        # List all timelines
        print(f"\n📋 Available timelines:")
        for i in range(project.GetTimelineCount()):
            timeline = project.GetTimelineByIndex(i + 1)
            if timeline:
                print(f"   {i+1}. {timeline.GetName()}")
        
        # Test with an existing timeline
        current_timeline = project.GetCurrentTimeline()
        if not current_timeline:
            # Use the first timeline
            current_timeline = project.GetTimelineByIndex(1)
            if current_timeline:
                project.SetCurrentTimeline(current_timeline)
        
        if not current_timeline:
            print("❌ No timeline available for testing")
            return
        
        print(f"\n🎬 Testing with timeline: {current_timeline.GetName()}")
        
        # Test render settings creation
        print(f"\n🔧 Testing render settings:")
        
        # Test basic render settings
        test_settings = {
            "SelectAllFrames": True,
            "TargetDir": "/Users/thelodgestudio/.openclaw/workspace/davinci-resolve-openclaw/exports/test/",
            "CustomName": "test-render",
            "ExportVideo": True,
            "ExportAudio": True,
            "FormatWidth": 1920,
            "FormatHeight": 1080,
            "FrameRate": 30.0,
            "PixelAspectRatio": 1.0,
            "VideoQuality": "Medium",
            "AudioCodec": "LinearPCM",
            "AudioBitDepth": "16",
            "AudioSampleRate": "48000",
        }
        
        print(f"✅ Created render settings for {test_settings['FormatWidth']}x{test_settings['FormatHeight']}")
        
        # Check if we can set render settings
        print(f"\n🧪 Testing SetRenderSettings...")
        try:
            success = project.SetRenderSettings(test_settings)
            print(f"   SetRenderSettings result: {success}")
        except Exception as e:
            print(f"   ❌ SetRenderSettings error: {e}")
        
        # Check current render settings
        print(f"\n🧪 Testing GetRenderSettings...")
        try:
            current_settings = project.GetRenderSettings()
            print(f"   Current render format: {current_settings.get('FormatWidth', 'N/A')}x{current_settings.get('FormatHeight', 'N/A')}")
            print(f"   Current codec: {current_settings.get('VideoCodec', 'N/A')}")
            print(f"   Current quality: {current_settings.get('VideoQuality', 'N/A')}")
        except Exception as e:
            print(f"   ❌ GetRenderSettings error: {e}")
        
        # Test render job creation
        print(f"\n🧪 Testing AddRenderJob...")
        try:
            # Create output directory
            os.makedirs(test_settings["TargetDir"], exist_ok=True)
            
            render_job_id = project.AddRenderJob()
            print(f"   AddRenderJob result: {render_job_id}")
            
            if render_job_id:
                print(f"   ✅ Successfully added render job: {render_job_id}")
                
                # Check render queue
                try:
                    render_jobs = project.GetRenderJobList()
                    print(f"   Current render jobs: {len(render_jobs) if render_jobs else 0}")
                    
                    if render_jobs:
                        for job in render_jobs:
                            print(f"      Job: {job}")
                            
                except Exception as e:
                    print(f"   ⚠️  GetRenderJobList error: {e}")
                    
            else:
                print(f"   ❌ Failed to add render job")
                
        except Exception as e:
            print(f"   ❌ AddRenderJob error: {e}")
        
        # Test render presets
        print(f"\n🧪 Testing render presets...")
        try:
            presets = project.GetRenderPresetList()
            if presets:
                print(f"   Available render presets: {len(presets)}")
                for preset in presets[:5]:  # Show first 5
                    print(f"      - {preset}")
                if len(presets) > 5:
                    print(f"      ... and {len(presets) - 5} more")
            else:
                print(f"   No render presets found")
                
        except Exception as e:
            print(f"   ❌ GetRenderPresetList error: {e}")
        
        print(f"\n📊 Render functionality test complete!")
        
    except Exception as e:
        print(f"❌ Error during render test: {e}")

if __name__ == "__main__":
    test_render_functionality()