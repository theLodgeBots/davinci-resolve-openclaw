#!/usr/bin/env python3
"""
Test alternative timeline creation methods for DaVinci Resolve
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

def test_alternative_methods():
    """Test alternative methods for timeline creation"""
    print("🧪 Alternative Timeline Creation Tests")
    print("=" * 50)
    
    # Connect to Resolve
    resolve = get_resolve_connection()
    if not resolve:
        return False
    
    try:
        # Get project manager and current project
        project_manager = resolve.GetProjectManager()
        project = project_manager.GetCurrentProject()
        media_pool = project.GetMediaPool()
        root_folder = media_pool.GetRootFolder()
        
        print(f"✅ Project: {project.GetName()}")
        print(f"✅ MediaPool: {media_pool}")
        print(f"✅ Root Folder: {root_folder}")
        
        # Test 1: Try CreateTimelineFromClips with empty clips list
        print("\n🎬 Test 1: CreateTimelineFromClips with empty list")
        try:
            timeline = media_pool.CreateTimelineFromClips("Test-Timeline-FromEmptyClips", [])
            print(f"   ✅ CreateTimelineFromClips result: {timeline}")
            if timeline:
                print(f"   📽️  Timeline name: {timeline.GetName()}")
                return True
        except Exception as e:
            print(f"   ❌ CreateTimelineFromClips error: {e}")
        
        # Test 2: Try CreateTimelineFromClips with actual clips
        print("\n🎬 Test 2: CreateTimelineFromClips with real clips")
        try:
            clips = root_folder.GetClipList()
            print(f"   📹 Found {len(clips) if clips else 0} clips")
            
            if clips and len(clips) > 0:
                # Try with just the first clip
                timeline = media_pool.CreateTimelineFromClips("Test-Timeline-WithOneClip", clips[:1])
                print(f"   ✅ CreateTimelineFromClips with clips result: {timeline}")
                if timeline:
                    print(f"   📽️  Timeline name: {timeline.GetName()}")
                    return True
            else:
                print("   ⚠️  No clips found in root folder")
        except Exception as e:
            print(f"   ❌ CreateTimelineFromClips with clips error: {e}")
        
        # Test 3: Try working with existing timelines
        print("\n🎬 Test 3: Working with existing timelines")
        try:
            timeline_count = project.GetTimelineCount()
            print(f"   📊 Existing timelines: {timeline_count}")
            
            if timeline_count > 0:
                # Get the first timeline
                existing_timeline = project.GetTimelineByIndex(1)
                print(f"   📽️  First timeline: {existing_timeline.GetName()}")
                
                # Try to set as current and modify
                project.SetCurrentTimeline(existing_timeline)
                current = project.GetCurrentTimeline()
                print(f"   ✅ Current timeline set: {current.GetName()}")
                
                # Check if we can modify settings on existing timeline
                timeline_settings = current.GetSetting()
                print(f"   🔧 Current timeline settings: {type(timeline_settings)}")
                
                # Try setting resolution (test if write operations work on existing timelines)
                resolution_test = current.SetSetting("timelineResolutionWidth", "1920")
                print(f"   🧪 Setting resolution test: {resolution_test}")
                
                if resolution_test:
                    print("   ✅ Write operations work on existing timelines!")
                    return True
                
        except Exception as e:
            print(f"   ❌ Existing timeline test error: {e}")
        
        # Test 4: Check if folders help
        print("\n🎬 Test 4: Folder-based operations")
        try:
            # Try creating a subfolder first
            subfolder = media_pool.AddSubFolder(root_folder, "TestSubfolder")
            print(f"   📁 Subfolder creation result: {subfolder}")
            
            if subfolder:
                # Set current folder to subfolder
                media_pool.SetCurrentFolder(subfolder)
                current_folder = media_pool.GetCurrentFolder()
                print(f"   📁 Current folder: {current_folder}")
                
                # Try creating timeline in the subfolder context
                timeline_in_folder = media_pool.CreateEmptyTimeline("Timeline-In-Subfolder")
                print(f"   📽️  Timeline in subfolder: {timeline_in_folder}")
                
                if timeline_in_folder:
                    print("   ✅ Subfolder approach worked!")
                    return True
                    
                # Clean up - delete the test subfolder
                try:
                    media_pool.DeleteFolders([subfolder])
                    print("   🧹 Cleaned up test subfolder")
                except Exception as cleanup_e:
                    print(f"   ⚠️  Couldn't clean up subfolder: {cleanup_e}")
                    
        except Exception as e:
            print(f"   ❌ Folder-based operations error: {e}")
        
        # Test 5: Check DaVinci Resolve preferences
        print("\n🎬 Test 5: DaVinci Resolve preferences check")
        try:
            # Check resolve-level settings
            resolve_settings = resolve.GetProductName()
            print(f"   🔧 Resolve product: {resolve_settings}")
            
            # Check if there's a way to enable external scripting
            project_manager_settings = dir(project_manager)
            scripting_methods = [m for m in project_manager_settings if 'script' in m.lower() or 'external' in m.lower()]
            print(f"   🔧 Project manager scripting methods: {scripting_methods}")
            
        except Exception as e:
            print(f"   ❌ Preferences check error: {e}")
        
        print("\n❌ All alternative methods failed")
        print("🔍 This suggests DaVinci Resolve external scripting permissions are disabled")
        print("💡 Manual timeline creation workflow remains the best approach")
        
        return False
        
    except Exception as e:
        print(f"❌ Error during alternative testing: {e}")
        return False

if __name__ == "__main__":
    success = test_alternative_methods()
    if success:
        print("\n🎉 Found working alternative method!")
    else:
        print("\n🚧 Will proceed with manual-assisted workflow")