#!/usr/bin/env python3
"""
Debug timeline creation for DaVinci Resolve
"""

import os
import sys
import importlib.util

def get_resolve_connection():
    """Connect to DaVinci Resolve using the correct API path"""
    try:
        # Set up Resolve scripting environment (same as resolve_bridge.py)
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
            print("✅ Connected to DaVinci Resolve")
            return resolve
        else:
            print("❌ Failed to connect to DaVinci Resolve")
            return None
    except Exception as e:
        print(f"❌ Error connecting to DaVinci Resolve: {e}")
        return None

def debug_timeline_creation():
    """Debug timeline creation process"""
    print("🔧 DaVinci Resolve Timeline Creation Debug")
    print("=" * 50)
    
    # Connect to Resolve
    resolve = get_resolve_connection()
    if not resolve:
        return False
    
    try:
        # Get project manager and current project
        project_manager = resolve.GetProjectManager()
        print(f"✅ Project Manager: {project_manager}")
        
        project = project_manager.GetCurrentProject()
        print(f"✅ Current Project: {project.GetName() if project else 'None'}")
        
        if not project:
            print("❌ No project loaded")
            return False
        
        # Get media pool
        media_pool = project.GetMediaPool()
        print(f"✅ Media Pool: {media_pool}")
        
        if not media_pool:
            print("❌ No media pool available")
            return False
        
        # List existing timelines
        timeline_count = project.GetTimelineCount()
        print(f"📊 Existing timelines: {timeline_count}")
        
        for i in range(timeline_count):
            timeline = project.GetTimelineByIndex(i + 1)
            if timeline:
                print(f"   {i+1}. {timeline.GetName()}")
        
        # Try to create a simple test timeline
        test_timeline_name = "Test-Timeline-Debug"
        print(f"\n🧪 Testing timeline creation: {test_timeline_name}")
        
        # Check if test timeline already exists
        existing = None
        for i in range(timeline_count):
            timeline = project.GetTimelineByIndex(i + 1)
            if timeline and timeline.GetName() == test_timeline_name:
                existing = timeline
                break
        
        if existing:
            print(f"⚠️  Timeline already exists, removing it first...")
            # Try to delete the existing timeline
            try:
                media_pool.DeleteTimelines([existing])
                print("✅ Deleted existing timeline")
            except Exception as e:
                print(f"⚠️  Couldn't delete existing timeline: {e}")
        
        # Create new empty timeline
        print("🔧 Creating new timeline...")
        new_timeline = media_pool.CreateEmptyTimeline(test_timeline_name)
        
        if new_timeline:
            print(f"✅ Successfully created timeline: {new_timeline.GetName()}")
            
            # Test setting it as current
            success = project.SetCurrentTimeline(new_timeline)
            print(f"✅ Set as current timeline: {success}")
            
            return True
        else:
            print("❌ Failed to create timeline")
            
            # Try alternative method
            print("🔧 Trying alternative method...")
            try:
                # Some versions use different methods
                timelines = media_pool.GetCurrentFolder().CreateEmptyTimeline(test_timeline_name)
                if timelines:
                    print("✅ Alternative method worked!")
                    return True
            except Exception as e:
                print(f"❌ Alternative method failed: {e}")
            
            return False
            
    except Exception as e:
        print(f"❌ Error during debug: {e}")
        return False

if __name__ == "__main__":
    debug_timeline_creation()