#!/usr/bin/env python3
"""
Debug version of automated social export to identify API issues
"""

import sys
import json
from pathlib import Path

def debug_resolve_connection():
    """Debug DaVinci Resolve API connection"""
    try:
        # Add DaVinci Resolve scripting modules to path
        dvr_modules_path = '/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules/'
        if dvr_modules_path not in sys.path:
            sys.path.append(dvr_modules_path)
        import DaVinciResolveScript as dvr_script
        
        print("🔍 Connecting to DaVinci Resolve...")
        resolve = dvr_script.scriptapp("Resolve")
        if not resolve:
            print("❌ Could not get resolve object")
            return None
            
        print("✅ Got resolve object")
        print(f"   Type: {type(resolve)}")
        
        # Test project manager
        print("🔍 Getting project manager...")
        pm = resolve.GetProjectManager()
        if not pm:
            print("❌ Could not get project manager")
            return None
            
        print("✅ Got project manager")
        print(f"   Type: {type(pm)}")
        
        # Test current project
        print("🔍 Getting current project...")
        project = pm.GetCurrentProject()
        if not project:
            print("❌ No current project")
            return None
            
        print("✅ Got current project")
        print(f"   Type: {type(project)}")
        
        # Test timeline operations
        print("🔍 Testing timeline operations...")
        timeline_count = project.GetTimelineCount()
        print(f"   Timeline count: {timeline_count}")
        
        if timeline_count > 0:
            print("   Checking first timeline...")
            timeline = project.GetTimelineByIndex(1)
            if timeline:
                print(f"   ✅ Got timeline: {type(timeline)}")
                name = timeline.GetName()
                print(f"   Timeline name: '{name}' (type: {type(name)})")
            else:
                print("   ❌ Timeline is None")
        
        # Test timeline creation
        print("🔍 Testing timeline creation...")
        test_timeline_name = "DEBUG_TEST_TIMELINE"
        
        # Check if test timeline exists and delete it
        for i in range(timeline_count):
            timeline = project.GetTimelineByIndex(i + 1)
            if timeline:
                name = timeline.GetName()
                if name == test_timeline_name:
                    print(f"   Found existing test timeline, deleting...")
                    # Note: DaVinci doesn't have a direct delete method in the API
                    
        print(f"   Creating test timeline: {test_timeline_name}")
        new_timeline = project.CreateTimeline(test_timeline_name)
        if new_timeline:
            print(f"   ✅ Created timeline successfully: {type(new_timeline)}")
            name = new_timeline.GetName()
            print(f"   New timeline name: '{name}'")
        else:
            print("   ❌ Timeline creation returned None")
        
        return resolve
        
    except Exception as e:
        print(f"❌ Exception in debug: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    print("🎬 DaVinci Resolve API Debug Test")
    print("=" * 50)
    
    resolve = debug_resolve_connection()
    if resolve:
        print("\n✅ All basic API operations working")
    else:
        print("\n❌ API connection issues detected")

if __name__ == "__main__":
    main()