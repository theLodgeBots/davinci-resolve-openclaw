#!/usr/bin/env python3
"""Test script to debug timeline information access."""

from resolve_bridge import get_resolve

def test_timeline_info():
    """Test what timeline information we can access."""
    print("🔧 Testing Timeline Information Access")
    print("=" * 50)
    
    try:
        # Connect to DaVinci Resolve
        resolve = get_resolve()
        if not resolve:
            print("❌ Could not connect to DaVinci Resolve")
            return False
        
        project_manager = resolve.GetProjectManager()
        project = project_manager.GetCurrentProject()
        
        if not project:
            print("❌ No project loaded")
            return False
        
        timeline = project.GetCurrentTimeline()
        if not timeline:
            print("❌ No timeline selected")
            return False
        
        project_name = project.GetName()
        timeline_name = timeline.GetName()
        
        print(f"✅ Project: {project_name}")
        print(f"✅ Timeline: {timeline_name}")
        
        # Test available methods
        print("\n🔍 Testing Timeline Methods:")
        
        # Basic info
        try:
            duration = timeline.GetDuration()
            print(f"✅ Duration: {duration} frames")
        except Exception as e:
            print(f"❌ GetDuration failed: {e}")
        
        try:
            start = timeline.GetStartFrame()
            print(f"✅ Start Frame: {start}")
        except Exception as e:
            print(f"❌ GetStartFrame failed: {e}")
        
        try:
            end = timeline.GetEndFrame()
            print(f"✅ End Frame: {end}")
        except Exception as e:
            print(f"❌ GetEndFrame failed: {e}")
        
        # Settings
        try:
            fps = timeline.GetSetting("timelineFrameRate")
            print(f"✅ Frame Rate: {fps}")
        except Exception as e:
            print(f"❌ GetSetting(timelineFrameRate) failed: {e}")
        
        # Markers
        try:
            marker_count = timeline.GetMarkerCount()
            print(f"✅ Marker Count: {marker_count}")
        except Exception as e:
            print(f"❌ GetMarkerCount failed: {e}")
        
        # Track count
        try:
            track_count = timeline.GetTrackCount("video")
            print(f"✅ Video Tracks: {track_count}")
        except Exception as e:
            print(f"❌ GetTrackCount(video) failed: {e}")
        
        try:
            track_count = timeline.GetTrackCount("audio") 
            print(f"✅ Audio Tracks: {track_count}")
        except Exception as e:
            print(f"❌ GetTrackCount(audio) failed: {e}")
        
        print("\n✅ Timeline information test completed!")
        return True
        
    except Exception as e:
        print(f"❌ Error testing timeline info: {e}")
        return False

if __name__ == "__main__":
    test_timeline_info()