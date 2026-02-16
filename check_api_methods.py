#!/usr/bin/env python3
"""
Check what methods are available on DaVinci Resolve API objects
"""

import sys

def check_api_methods():
    try:
        # Add DaVinci Resolve scripting modules to path
        dvr_modules_path = '/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules/'
        if dvr_modules_path not in sys.path:
            sys.path.append(dvr_modules_path)
        import DaVinciResolveScript as dvr_script
        
        resolve = dvr_script.scriptapp("Resolve")
        pm = resolve.GetProjectManager()
        project = pm.GetCurrentProject()
        
        print("🔍 Available methods on PROJECT object:")
        project_methods = [method for method in dir(project) if not method.startswith('_')]
        for method in sorted(project_methods):
            try:
                attr = getattr(project, method)
                if callable(attr):
                    print(f"   ✅ {method}() - callable")
                else:
                    print(f"   📄 {method} - {type(attr)}")
            except:
                print(f"   ❌ {method} - error accessing")
        
        # Check if CreateTimeline exists and what it returns
        if hasattr(project, 'CreateTimeline'):
            print(f"\n🔍 CreateTimeline method:")
            create_method = getattr(project, 'CreateTimeline')
            print(f"   Type: {type(create_method)}")
            print(f"   Callable: {callable(create_method)}")
            if create_method is None:
                print("   ❌ CreateTimeline is None!")
        else:
            print("\n❌ CreateTimeline method does not exist")
            
        # Test a simple method that should work
        print(f"\n🔍 Testing GetTimelineCount:")
        count = project.GetTimelineCount()
        print(f"   Result: {count} (type: {type(count)})")
        
        # Check timeline methods
        if count > 0:
            print(f"\n🔍 Testing GetTimelineByIndex:")
            timeline = project.GetTimelineByIndex(1)
            print(f"   Result: {type(timeline)}")
            if timeline:
                timeline_methods = [method for method in dir(timeline) if not method.startswith('_')]
                print(f"   Timeline methods: {len(timeline_methods)} available")
                for method in sorted(timeline_methods)[:10]:  # First 10 methods
                    print(f"      {method}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_api_methods()