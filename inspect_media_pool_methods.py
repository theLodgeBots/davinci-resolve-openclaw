#!/usr/bin/env python3
"""
Inspect available methods on DaVinci Resolve MediaPool object
"""

import os
import sys

# Set up Resolve scripting environment (same as resolve_bridge.py)
RESOLVE_SCRIPT_API = "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting"
RESOLVE_SCRIPT_LIB = "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so"

os.environ["RESOLVE_SCRIPT_API"] = RESOLVE_SCRIPT_API
os.environ["RESOLVE_SCRIPT_LIB"] = RESOLVE_SCRIPT_LIB

resolve_script_modules = f"{RESOLVE_SCRIPT_API}/Modules/"
if resolve_script_modules not in sys.path:
    sys.path.append(resolve_script_modules)

def inspect_media_pool():
    """Inspect MediaPool object methods"""
    try:
        import DaVinciResolveScript as dvr_script
        resolve = dvr_script.scriptapp("Resolve")
        
        if not resolve:
            print("❌ Could not connect to DaVinci Resolve")
            return
        
        print("🔧 DaVinci Resolve MediaPool Method Inspector")
        print("=" * 50)
        
        project_manager = resolve.GetProjectManager()
        project = project_manager.GetCurrentProject()
        
        if not project:
            print("❌ No project loaded")
            return
        
        media_pool = project.GetMediaPool()
        
        if not media_pool:
            print("❌ No media pool available")
            return
        
        print(f"✅ MediaPool object: {media_pool}")
        print(f"✅ Project: {project.GetName()}")
        
        # Get all methods
        methods = [method for method in dir(media_pool) if not method.startswith('_')]
        methods.sort()
        
        print(f"\n📋 Available MediaPool methods ({len(methods)} total):")
        for method in methods:
            try:
                attr = getattr(media_pool, method)
                if callable(attr):
                    print(f"   🔧 {method}()")
                else:
                    print(f"   📊 {method} = {attr}")
            except Exception as e:
                print(f"   ⚠️  {method} - Error: {e}")
        
        # Try specific timeline creation methods
        print(f"\n🎬 Testing Timeline Creation Methods:")
        
        # Test CreateEmptyTimeline
        print(f"🧪 Testing CreateEmptyTimeline...")
        try:
            result = media_pool.CreateEmptyTimeline("Test-Method-1")
            print(f"   ✅ CreateEmptyTimeline: {result}")
            
            if result:
                # Clean up
                media_pool.DeleteTimelines([result])
                print("   🗑️  Cleaned up test timeline")
                
        except Exception as e:
            print(f"   ❌ CreateEmptyTimeline error: {e}")
        
        # Test alternative methods
        print(f"🧪 Testing GetRootFolder().CreateEmptyTimeline...")
        try:
            root_folder = media_pool.GetRootFolder()
            print(f"   📁 Root folder: {root_folder}")
            
            if hasattr(root_folder, 'CreateEmptyTimeline'):
                result = root_folder.CreateEmptyTimeline("Test-Method-2")
                print(f"   ✅ Folder.CreateEmptyTimeline: {result}")
                
                if result:
                    media_pool.DeleteTimelines([result])
                    print("   🗑️  Cleaned up test timeline")
            else:
                print("   ❌ Root folder doesn't have CreateEmptyTimeline method")
                
        except Exception as e:
            print(f"   ❌ Folder CreateEmptyTimeline error: {e}")
        
        # Check current folder
        print(f"🧪 Testing GetCurrentFolder().CreateEmptyTimeline...")
        try:
            current_folder = media_pool.GetCurrentFolder()
            print(f"   📁 Current folder: {current_folder}")
            print(f"   📁 Current folder name: {current_folder.GetName()}")
            
            if hasattr(current_folder, 'CreateEmptyTimeline'):
                result = current_folder.CreateEmptyTimeline("Test-Method-3")
                print(f"   ✅ CurrentFolder.CreateEmptyTimeline: {result}")
                
                if result:
                    media_pool.DeleteTimelines([result])
                    print("   🗑️  Cleaned up test timeline")
            else:
                print("   ❌ Current folder doesn't have CreateEmptyTimeline method")
                
        except Exception as e:
            print(f"   ❌ CurrentFolder CreateEmptyTimeline error: {e}")

    except Exception as e:
        print(f"❌ Error during inspection: {e}")

if __name__ == "__main__":
    inspect_media_pool()