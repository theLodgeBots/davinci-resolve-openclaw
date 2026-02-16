#!/usr/bin/env python3
"""
Test timeline creation through MediaPool
"""

import sys
import os

def main():
    try:
        # Connect to DaVinci Resolve
        dvr_modules_path = '/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules/'
        if dvr_modules_path not in sys.path:
            sys.path.append(dvr_modules_path)
        
        import DaVinciResolveScript as dvr_script
        resolve = dvr_script.scriptapp("Resolve")
        
        if not resolve:
            print("❌ Could not connect to DaVinci Resolve")
            return False
        
        project_manager = resolve.GetProjectManager()
        project = project_manager.GetCurrentProject()
        
        if not project:
            print("❌ No project loaded")
            return False
        
        print(f"✅ Connected to project: {project.GetName()}")
        
        # Get media pool
        media_pool = project.GetMediaPool()
        if not media_pool:
            print("❌ No media pool available")
            return False
        
        print(f"✅ Got media pool: {media_pool}")
        
        # List existing timelines
        timeline_count = project.GetTimelineCount()
        print(f"📽️  Existing timelines ({timeline_count}):")
        for i in range(timeline_count):
            timeline = project.GetTimelineByIndex(i + 1)
            if timeline:
                print(f"   {i+1}: {timeline.GetName()}")
        
        # Test creating a timeline
        test_timeline_name = "TEST_SOCIAL_TIMELINE"
        
        # Check if it already exists and delete it
        for i in range(timeline_count):
            timeline = project.GetTimelineByIndex(i + 1)
            if timeline and timeline.GetName() == test_timeline_name:
                print(f"🗑️  Deleting existing timeline: {test_timeline_name}")
                media_pool.DeleteTimelines([timeline])
                break
        
        print(f"🏗️  Creating new timeline: {test_timeline_name}")
        new_timeline = media_pool.CreateEmptyTimeline(test_timeline_name)
        
        if new_timeline:
            print(f"✅ Successfully created timeline!")
            print(f"   Type: {type(new_timeline)}")
            print(f"   Name: {new_timeline.GetName()}")
            
            # Test setting it as current
            success = project.SetCurrentTimeline(new_timeline)
            print(f"   Set as current: {'✅ Success' if success else '❌ Failed'}")
            
            # Get timeline info
            print(f"   Video tracks: {new_timeline.GetTrackCount('video')}")
            print(f"   Audio tracks: {new_timeline.GetTrackCount('audio')}")
            
        else:
            print(f"❌ CreateEmptyTimeline returned: {new_timeline}")
            
            # Try to understand why it failed
            print(f"🔍 MediaPool methods available:")
            methods = [m for m in dir(media_pool) if not m.startswith('_')]
            timeline_methods = [m for m in methods if 'timeline' in m.lower()]
            create_methods = [m for m in methods if 'create' in m.lower()]
            
            print(f"   Timeline methods: {timeline_methods}")
            print(f"   Create methods: {create_methods}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    print(f"\n🎯 Timeline creation test: {'Success' if success else 'Failed'}")