#!/usr/bin/env python3
"""Bridge to DaVinci Resolve Studio scripting API."""

import sys
import os

# Set up Resolve scripting environment
RESOLVE_SCRIPT_API = "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting"
RESOLVE_SCRIPT_LIB = "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so"

os.environ["RESOLVE_SCRIPT_API"] = RESOLVE_SCRIPT_API
os.environ["RESOLVE_SCRIPT_LIB"] = RESOLVE_SCRIPT_LIB

if f"{RESOLVE_SCRIPT_API}/Modules/" not in sys.path:
    sys.path.append(f"{RESOLVE_SCRIPT_API}/Modules/")


def get_resolve():
    """Connect to running DaVinci Resolve instance."""
    try:
        import DaVinciResolveScript as dvr_script
        resolve = dvr_script.scriptapp("Resolve")
        if resolve is None:
            print("ERROR: Could not connect to DaVinci Resolve.")
            print("Make sure DaVinci Resolve Studio is running.")
            print("Also check: Preferences > System > General > External scripting using = Local")
            return None
        return resolve
    except ImportError as e:
        print(f"ERROR: Could not import DaVinciResolveScript: {e}")
        print(f"Check that RESOLVE_SCRIPT_API path exists: {RESOLVE_SCRIPT_API}")
        return None


def get_project_manager(resolve):
    """Get the project manager from Resolve."""
    return resolve.GetProjectManager()


def get_current_project(resolve):
    """Get the currently open project."""
    pm = get_project_manager(resolve)
    return pm.GetCurrentProject()


def create_project(resolve, name):
    """Create a new project."""
    pm = get_project_manager(resolve)
    project = pm.CreateProject(name)
    if project is None:
        print(f"ERROR: Could not create project '{name}' (name may already exist)")
    return project


def import_media(project, file_paths):
    """Import media files into the current media pool folder."""
    media_pool = project.GetMediaPool()
    items = media_pool.ImportMedia(file_paths)
    return items


def create_timeline(project, name, clips=None):
    """Create a new timeline, optionally with clips."""
    media_pool = project.GetMediaPool()
    if clips:
        timeline = media_pool.CreateTimelineFromClips(name, clips)
    else:
        timeline = media_pool.CreateEmptyTimeline(name)
    return timeline


def get_media_storage(resolve):
    """Get media storage for browsing mounted volumes."""
    return resolve.GetMediaStorage()


def print_status(resolve):
    """Print current Resolve status."""
    print(f"Product: {resolve.GetProductName()} {resolve.GetVersionString()}")
    
    pm = get_project_manager(resolve)
    project = pm.GetCurrentProject()
    if project:
        print(f"Current Project: {project.GetName()}")
        print(f"Timeline Count: {project.GetTimelineCount()}")
        
        timeline = project.GetCurrentTimeline()
        if timeline:
            print(f"Current Timeline: {timeline.GetName()}")
            print(f"  Video Tracks: {timeline.GetTrackCount('video')}")
            print(f"  Audio Tracks: {timeline.GetTrackCount('audio')}")
    else:
        print("No project currently open")
    
    ms = resolve.GetMediaStorage()
    volumes = ms.GetMountedVolumeList()
    print(f"Mounted Volumes: {volumes}")


if __name__ == "__main__":
    resolve = get_resolve()
    if resolve:
        print_status(resolve)
