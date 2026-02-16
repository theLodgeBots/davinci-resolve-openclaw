#!/usr/bin/env python3
"""
Inspect available methods on DaVinci Resolve API objects
"""

import sys
import os

def inspect_object(obj, name):
    print(f"\n🔍 {name} methods:")
    print("=" * 50)
    
    # Get all attributes
    attrs = dir(obj)
    methods = []
    
    for attr in attrs:
        if not attr.startswith('_'):  # Skip private attributes
            try:
                value = getattr(obj, attr)
                if callable(value) or value is not None:
                    methods.append(attr)
            except:
                pass
    
    # Group by likely function (timeline, project, etc.)
    timeline_methods = [m for m in methods if 'timeline' in m.lower()]
    create_methods = [m for m in methods if 'create' in m.lower()]
    get_methods = [m for m in methods if m.startswith('Get')]
    set_methods = [m for m in methods if m.startswith('Set')]
    other_methods = [m for m in methods if m not in timeline_methods + create_methods + get_methods + set_methods]
    
    if timeline_methods:
        print("📽️  Timeline methods:")
        for method in timeline_methods:
            print(f"   {method}")
    
    if create_methods:
        print("🏗️  Create methods:")
        for method in create_methods:
            print(f"   {method}")
    
    if get_methods:
        print("📥 Get methods:")
        for method in get_methods[:10]:  # Limit to first 10
            print(f"   {method}")
        if len(get_methods) > 10:
            print(f"   ... and {len(get_methods)-10} more")
    
    if set_methods:
        print("📤 Set methods:")
        for method in set_methods[:10]:  # Limit to first 10
            print(f"   {method}")
        if len(set_methods) > 10:
            print(f"   ... and {len(set_methods)-10} more")
    
    if other_methods:
        print("🔧 Other methods:")
        for method in other_methods[:15]:  # Limit to first 15
            print(f"   {method}")
        if len(other_methods) > 15:
            print(f"   ... and {len(other_methods)-15} more")

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
        
        print(f"🎬 Inspecting DaVinci Resolve API for project: {project.GetName()}")
        
        # Inspect project object
        inspect_object(project, "Project")
        
        # Test a specific method we need
        print(f"\n🔍 Testing specific method availability:")
        print(f"   CreateTimeline: {getattr(project, 'CreateTimeline', 'NOT FOUND')}")
        
        # Try alternative method names
        alternatives = [
            'CreateNewTimeline',
            'AddTimeline', 
            'NewTimeline',
            'CreateEmptyTimeline',
            'DuplicateTimeline'
        ]
        
        print(f"\n🔍 Testing alternative timeline creation methods:")
        for alt in alternatives:
            method = getattr(project, alt, None)
            print(f"   {alt}: {'FOUND' if method is not None else 'NOT FOUND'}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    print(f"\n🎯 Inspection completed: {'Success' if success else 'Failed'}")