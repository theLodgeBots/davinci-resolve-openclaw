#!/usr/bin/env python3
"""
Test alternative methods for creating timelines in DaVinci Resolve
when CreateEmptyTimeline is not working.
"""

import sys

# Add the DaVinci Resolve Python API path
resolve_lib_path = "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion"
if resolve_lib_path not in sys.path:
    sys.path.append(resolve_lib_path)

try:
    import DaVinciResolveScript as dvr_script
    resolve = dvr_script.scriptapp("Resolve")
    pm = resolve.GetProjectManager()
    project = pm.GetCurrentProject()
    media_pool = project.GetMediaPool()
    root_folder = media_pool.GetRootFolder()
    
    print("🧪 Alternative Timeline Creation Tests")
    print("=" * 50)
    print(f"✅ Connected to project: {project.GetName()}")
    print(f"✅ MediaPool: {media_pool}")
    print(f"✅ Root Folder: {root_folder}")
    
    # Test 1: Try CreateTimelineFromClips with empty clips list
    print("\n🎬 Test 1: CreateTimelineFromClips with empty list")
    try:
        timeline = media_pool.CreateTimelineFromClips("Test-Timeline-FromClips", [])
        print(f"   ✅ CreateTimelineFromClips result: {timeline}")
    except Exception as e:
        print(f"   ❌ CreateTimelineFromClips error: {e}")
    
    # Test 2: Try CreateTimelineFromClips with actual clips
    print("\n🎬 Test 2: CreateTimelineFromClips with real clips")
    try:
        clips = root_folder.GetClipList()
        if clips:
            print(f"   📹 Found {len(clips)} clips")
            # Try with just the first clip
            timeline = media_pool.CreateTimelineFromClips("Test-Timeline-WithClips", clips[:1])
            print(f"   ✅ CreateTimelineFromClips with clips result: {timeline}")
        else:
            print("   ⚠️  No clips found in root folder")
    except Exception as e:
        print(f"   ❌ CreateTimelineFromClips with clips error: {e}")
    
    # Test 3: Try duplicating existing timeline
    print("\n🎬 Test 3: Timeline duplication approaches")
    try:
        timeline_count = project.GetTimelineCount()
        print(f"   📊 Existing timelines: {timeline_count}")
        
        if timeline_count > 0:
            # Get the first timeline
            existing_timeline = project.GetTimelineByIndex(1)
            print(f"   📽️  First timeline: {existing_timeline}")
            
            # Check if timeline has duplication methods
            if hasattr(existing_timeline, 'DuplicateTimeline'):
                dup_timeline = existing_timeline.DuplicateTimeline("Duplicated-Timeline")
                print(f"   ✅ Timeline duplication result: {dup_timeline}")
            else:
                print("   ⚠️  Timeline does not have DuplicateTimeline method")
                
    except Exception as e:
        print(f"   ❌ Timeline duplication error: {e}")
    
    # Test 4: Check project-level timeline creation
    print("\n🎬 Test 4: Project-level timeline methods")
    try:
        # Check all project methods that might create timelines
        project_methods = dir(project)
        timeline_methods = [m for m in project_methods if 'timeline' in m.lower() or 'Timeline' in m]
        print(f"   🔧 Project timeline-related methods: {timeline_methods}")
        
        for method_name in timeline_methods:
            if method_name.startswith('Create') or method_name.startswith('Add'):
                method = getattr(project, method_name)
                print(f"      🎯 {method_name}: {method}")
                
    except Exception as e:
        print(f"   ❌ Project method inspection error: {e}")
    
    # Test 5: MediaPool folder operations
    print("\n🎬 Test 5: Folder-based timeline creation")
    try:
        # Check if we can create subfolder first
        subfolder = media_pool.AddSubFolder(root_folder, "TestFolder")
        print(f"   📁 Subfolder creation result: {subfolder}")
        
        if subfolder:
            # Try creating timeline in subfolder
            timeline_in_folder = media_pool.CreateEmptyTimeline("Timeline-In-Folder")
            print(f"   📽️  Timeline in subfolder: {timeline_in_folder}")
            
    except Exception as e:
        print(f"   ❌ Folder-based creation error: {e}")
        
    print("\n🎯 Alternative testing completed")
    
except Exception as e:
    print(f"❌ Connection failed: {e}")
    sys.exit(1)