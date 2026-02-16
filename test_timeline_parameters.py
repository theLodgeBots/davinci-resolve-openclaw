#!/usr/bin/env python3
"""
Test different parameters for timeline creation
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
        media_pool = project.GetMediaPool()
        
        print(f"✅ Connected to project: {project.GetName()}")
        
        # Try different timeline names and approaches
        test_names = [
            "Test1",
            "SocialTest", 
            "Timeline123",
            "test_timeline"
        ]
        
        for name in test_names:
            print(f"\n🧪 Testing timeline name: '{name}'")
            
            # Check if it already exists and delete it
            timeline_count = project.GetTimelineCount()
            for i in range(timeline_count):
                timeline = project.GetTimelineByIndex(i + 1)
                if timeline and timeline.GetName() == name:
                    print(f"   Deleting existing: {name}")
                    media_pool.DeleteTimelines([timeline])
                    break
            
            # Try creating
            new_timeline = media_pool.CreateEmptyTimeline(name)
            
            if new_timeline:
                print(f"   ✅ SUCCESS! Created: {name}")
                print(f"   Type: {type(new_timeline)}")
                break
            else:
                print(f"   ❌ Failed: {name}")
        
        # If all failed, try looking at project settings
        if not new_timeline:
            print("\n🔍 Investigating project constraints...")
            
            # Check project settings
            project_name = project.GetName()
            print(f"   Project name: {project_name}")
            
            # Check if there are any special project settings
            print(f"   Timeline count: {project.GetTimelineCount()}")
            
            # Try to see what project settings exist
            print(f"   Project type: {type(project)}")
            
            # Try CreateTimelineFromClips as alternative
            print(f"\n🧪 Testing CreateTimelineFromClips...")
            root_folder = media_pool.GetRootFolder()
            clips = root_folder.GetClipList()
            if clips:
                print(f"   Found {len(clips)} clips")
                # Try to create timeline from first clip
                timeline_from_clips = media_pool.CreateTimelineFromClips("TestFromClips", [clips[0]])
                if timeline_from_clips:
                    print(f"   ✅ CreateTimelineFromClips worked!")
                    print(f"   Timeline: {timeline_from_clips.GetName()}")
                else:
                    print(f"   ❌ CreateTimelineFromClips also failed")
            else:
                print(f"   No clips available for CreateTimelineFromClips test")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    print(f"\n🎯 Parameter test: {'Success' if success else 'Failed'}")