#!/usr/bin/env python3
"""
Inspect available render settings in DaVinci Resolve
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
        
        # Get current render settings
        print(f"\n🔍 Current render settings:")
        current_settings = project.GetRenderSettings()
        if current_settings:
            print("Current render settings:")
            for key, value in current_settings.items():
                print(f"   {key}: {value}")
        else:
            print("   No render settings returned")
        
        # Try to get render presets
        print(f"\n🔍 Available render presets:")
        presets = project.GetRenderPresets()
        if presets:
            print(f"Available render presets:")
            for preset in presets:
                print(f"   {preset}")
        else:
            print("   No render presets returned")
        
        # Try to get render formats and codecs
        print(f"\n🔍 Available render formats and codecs:")
        format_and_codec = project.GetCurrentRenderFormatAndCodec()
        if format_and_codec:
            print(f"Current format and codec: {format_and_codec}")
        else:
            print("   No format and codec info returned")
        
        # Try a simple render settings change to see what works
        print(f"\n🧪 Testing simple render settings changes:")
        
        # Test basic settings that are likely to work
        test_settings = {
            "CustomName": "test_export"
        }
        
        success = project.SetRenderSettings(test_settings)
        print(f"   SetRenderSettings with CustomName: {'✅ Success' if success else '❌ Failed'}")
        
        # Test with MarkIn/MarkOut
        test_settings_2 = {
            "MarkIn": 0,
            "MarkOut": 100
        }
        
        success = project.SetRenderSettings(test_settings_2)
        print(f"   SetRenderSettings with MarkIn/MarkOut: {'✅ Success' if success else '❌ Failed'}")
        
        # Test with resolution
        test_settings_3 = {
            "VideoResolutionWidth": 1920,
            "VideoResolutionHeight": 1080
        }
        
        success = project.SetRenderSettings(test_settings_3)
        print(f"   SetRenderSettings with resolution: {'✅ Success' if success else '❌ Failed'}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    print(f"\n🎯 Render settings inspection: {'Success' if success else 'Failed'}")