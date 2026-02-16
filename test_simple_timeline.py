#!/usr/bin/env python3
"""
Test simple timeline creation with different naming approaches
"""

import os
import sys
import time

# Set up Resolve scripting environment
RESOLVE_SCRIPT_API = "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting"
RESOLVE_SCRIPT_LIB = "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so"

os.environ["RESOLVE_SCRIPT_API"] = RESOLVE_SCRIPT_API
os.environ["RESOLVE_SCRIPT_LIB"] = RESOLVE_SCRIPT_LIB

resolve_script_modules = f"{RESOLVE_SCRIPT_API}/Modules/"
if resolve_script_modules not in sys.path:
    sys.path.append(resolve_script_modules)

def test_timeline_creation():
    """Test timeline creation with various naming approaches"""
    try:
        import DaVinciResolveScript as dvr_script
        resolve = dvr_script.scriptapp("Resolve")
        
        if not resolve:
            print("❌ Could not connect to DaVinci Resolve")
            return
        
        print("🧪 Simple Timeline Creation Test")
        print("=" * 40)
        
        project_manager = resolve.GetProjectManager()
        project = project_manager.GetCurrentProject()
        media_pool = project.GetMediaPool()
        
        print(f"✅ Project: {project.GetName()}")
        print(f"✅ Timeline count: {project.GetTimelineCount()}")
        
        # Test different naming patterns
        test_names = [
            "Simple Test",
            "test-timeline-1",
            f"Test-{int(time.time())}",  # timestamp-based
            "AI_Timeline_Test",
            "Test Timeline",
            "Test",
            "TestTimeline"
        ]
        
        successful_timelines = []
        
        for name in test_names:
            print(f"\n🧪 Testing name: '{name}'")
            
            # Check if it already exists
            exists = False
            for i in range(project.GetTimelineCount()):
                timeline = project.GetTimelineByIndex(i + 1)
                if timeline and timeline.GetName() == name:
                    exists = True
                    print(f"   ⚠️  Already exists: {name}")
                    break
            
            if exists:
                continue
                
            # Try to create
            try:
                new_timeline = media_pool.CreateEmptyTimeline(name)
                
                if new_timeline:
                    print(f"   ✅ SUCCESS: Created '{name}'")
                    print(f"      Timeline object: {new_timeline}")
                    print(f"      Timeline name: {new_timeline.GetName()}")
                    successful_timelines.append(new_timeline)
                else:
                    print(f"   ❌ FAILED: CreateEmptyTimeline returned None for '{name}'")
                    
            except Exception as e:
                print(f"   ❌ ERROR: Exception creating '{name}': {e}")
        
        print(f"\n📊 RESULTS:")
        print(f"✅ Successfully created: {len(successful_timelines)}")
        
        # If we created any timelines, try to use one
        if successful_timelines:
            test_timeline = successful_timelines[0]
            print(f"\n🎬 Testing timeline operations with: {test_timeline.GetName()}")
            
            # Set as current
            success = project.SetCurrentTimeline(test_timeline)
            print(f"   Set as current: {success}")
            
            # Get info
            video_tracks = test_timeline.GetTrackCount('video')
            audio_tracks = test_timeline.GetTrackCount('audio')
            print(f"   Video tracks: {video_tracks}")
            print(f"   Audio tracks: {audio_tracks}")
            
        else:
            print("❌ No timelines created successfully")
            
            # Try checking the project state
            print(f"\n🔍 Project state debug:")
            print(f"   Project name: {project.GetName()}")
            print(f"   Timeline count: {project.GetTimelineCount()}")
            
            # Check current timeline
            current_timeline = project.GetCurrentTimeline()
            if current_timeline:
                print(f"   Current timeline: {current_timeline.GetName()}")
            else:
                print(f"   Current timeline: None")
            
    except Exception as e:
        print(f"❌ Error during test: {e}")

if __name__ == "__main__":
    test_timeline_creation()