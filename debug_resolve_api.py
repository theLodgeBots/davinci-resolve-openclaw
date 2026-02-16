#!/usr/bin/env python3
"""
Debug DaVinci Resolve API calls to identify the issue
"""

import sys
import os

def main():
    try:
        # Add DaVinci Resolve scripting modules to path
        dvr_modules_path = '/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules/'
        if dvr_modules_path not in sys.path:
            sys.path.append(dvr_modules_path)
        
        print("🔍 Importing DaVinci Resolve Script...")
        import DaVinciResolveScript as dvr_script
        
        print("🔍 Connecting to Resolve...")
        resolve = dvr_script.scriptapp("Resolve")
        if not resolve:
            print("❌ Could not connect to DaVinci Resolve")
            return False
        
        print("✅ Connected to DaVinci Resolve")
        print(f"Resolve object: {resolve}")
        print(f"Resolve type: {type(resolve)}")
        
        print("\n🔍 Getting Project Manager...")
        project_manager = resolve.GetProjectManager()
        if not project_manager:
            print("❌ Could not get project manager")
            return False
        
        print("✅ Got Project Manager")
        print(f"Project Manager object: {project_manager}")
        print(f"Project Manager type: {type(project_manager)}")
        
        print("\n🔍 Getting Current Project...")
        project = project_manager.GetCurrentProject()
        if not project:
            print("❌ No project loaded in DaVinci Resolve")
            return False
            
        print("✅ Got Current Project")
        print(f"Project object: {project}")
        print(f"Project type: {type(project)}")
        print(f"Project name: {project.GetName()}")
        
        print("\n🔍 Getting Timeline Count...")
        timeline_count = project.GetTimelineCount()
        print(f"Timeline count: {timeline_count}")
        
        if timeline_count > 0:
            print("\n🔍 Testing GetTimelineByIndex...")
            for i in range(min(3, timeline_count)):  # Test first 3 timelines
                timeline = project.GetTimelineByIndex(i + 1)  # DaVinci uses 1-based indexing
                print(f"Timeline {i+1}: {timeline}")
                if timeline:
                    print(f"  Type: {type(timeline)}")
                    name = timeline.GetName()
                    print(f"  Name: {name}")
                else:
                    print(f"  ❌ Timeline {i+1} returned None")
        
        print("\n🔍 Testing CreateTimeline...")
        test_timeline_name = "DEBUG_TEST_TIMELINE"
        
        # First check if it already exists
        existing = None
        for i in range(timeline_count):
            timeline = project.GetTimelineByIndex(i + 1)
            if timeline and timeline.GetName() == test_timeline_name:
                existing = timeline
                break
        
        if existing:
            print(f"Test timeline already exists: {test_timeline_name}")
        else:
            print(f"Creating test timeline: {test_timeline_name}")
            new_timeline = project.CreateTimeline(test_timeline_name)
            if new_timeline:
                print(f"✅ Successfully created timeline: {new_timeline}")
                print(f"  Type: {type(new_timeline)}")
                print(f"  Name: {new_timeline.GetName()}")
            else:
                print(f"❌ CreateTimeline returned None")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    print(f"\n🎯 Debug completed: {'Success' if success else 'Failed'}")