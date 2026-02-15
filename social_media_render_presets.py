#!/usr/bin/env python3
"""Social media render presets for DaVinci Resolve."""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List

from resolve_bridge import get_resolve

class SocialMediaRenderPresets:
    """Manages social media render presets for DaVinci Resolve."""
    
    def __init__(self):
        self.presets = {
            # TikTok / Instagram Stories (9:16 Vertical)
            "tiktok_vertical": {
                "name": "TikTok Vertical 9:16",
                "format": "mp4",
                "codec": "h264_aac",
                "resolution": {
                    "width": 1080,
                    "height": 1920
                },
                "framerate": 30,
                "bitrate_video": 8000,  # kbps
                "bitrate_audio": 128,   # kbps
                "quality": "high",
                "platforms": ["TikTok", "Instagram Stories", "YouTube Shorts"],
                "description": "Vertical 9:16 format optimized for mobile social platforms"
            },
            
            # Instagram Post (1:1 Square)  
            "instagram_square": {
                "name": "Instagram Square 1:1",
                "format": "mp4",
                "codec": "h264_aac",
                "resolution": {
                    "width": 1080,
                    "height": 1080
                },
                "framerate": 30,
                "bitrate_video": 6000,
                "bitrate_audio": 128,
                "quality": "high", 
                "platforms": ["Instagram Post", "Facebook", "Twitter"],
                "description": "Square 1:1 format for Instagram posts and social feeds"
            },
            
            # LinkedIn / Twitter (16:9 Horizontal)
            "linkedin_horizontal": {
                "name": "LinkedIn Horizontal 16:9", 
                "format": "mp4",
                "codec": "h264_aac",
                "resolution": {
                    "width": 1920,
                    "height": 1080
                },
                "framerate": 30,
                "bitrate_video": 10000,
                "bitrate_audio": 128,
                "quality": "high",
                "platforms": ["LinkedIn", "Twitter", "Facebook"],
                "description": "Professional horizontal format for business platforms"
            },
            
            # Instagram Reels (9:16 Vertical, optimized)
            "instagram_reels": {
                "name": "Instagram Reels 9:16",
                "format": "mp4", 
                "codec": "h264_aac",
                "resolution": {
                    "width": 1080,
                    "height": 1920
                },
                "framerate": 30,
                "bitrate_video": 9000,
                "bitrate_audio": 128,
                "quality": "high",
                "platforms": ["Instagram Reels", "Facebook Reels"],
                "description": "Vertical 9:16 optimized for Instagram Reels algorithm"
            },
            
            # YouTube Shorts (9:16 Vertical, higher quality)
            "youtube_shorts": {
                "name": "YouTube Shorts 9:16",
                "format": "mp4",
                "codec": "h264_aac", 
                "resolution": {
                    "width": 1080,
                    "height": 1920
                },
                "framerate": 30,
                "bitrate_video": 12000,
                "bitrate_audio": 192,
                "quality": "high",
                "platforms": ["YouTube Shorts"],
                "description": "High-quality vertical format for YouTube Shorts"
            },
            
            # Twitter/X (16:9 Horizontal, compressed)
            "twitter_optimized": {
                "name": "Twitter Optimized 16:9",
                "format": "mp4",
                "codec": "h264_aac",
                "resolution": {
                    "width": 1280,
                    "height": 720
                },
                "framerate": 30,
                "bitrate_video": 5000,
                "bitrate_audio": 128,
                "quality": "medium",
                "platforms": ["Twitter", "X"],
                "description": "Compressed horizontal format for Twitter's file size limits"
            }
        }
    
    def get_preset(self, preset_name: str) -> Dict:
        """Get specific render preset configuration."""
        return self.presets.get(preset_name, {})
    
    def get_presets_for_platform(self, platform: str) -> List[Dict]:
        """Get all presets suitable for a specific platform."""
        matching_presets = []
        for preset_id, preset in self.presets.items():
            if platform in preset.get("platforms", []):
                matching_presets.append({
                    "id": preset_id,
                    **preset
                })
        return matching_presets
    
    def get_all_presets(self) -> Dict:
        """Get all available presets."""
        return self.presets
    
    def create_render_job(self, preset_name: str, timeline_name: str, output_filename: str = None):
        """Create a render job in DaVinci Resolve using the specified preset.
        
        Args:
            preset_name: Name of the preset to use
            timeline_name: Name of the timeline to render
            output_filename: Optional custom filename (will be auto-generated if not provided)
        """
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
            
            # Find the timeline
            timeline_count = project.GetTimelineCount()
            target_timeline = None
            
            for i in range(timeline_count):
                timeline = project.GetTimelineByIndex(i + 1)  # DaVinci uses 1-based indexing
                if timeline and timeline.GetName() == timeline_name:
                    target_timeline = timeline
                    break
            
            if not target_timeline:
                print(f"❌ Timeline '{timeline_name}' not found")
                return False
            
            # Set the timeline as current
            project.SetCurrentTimeline(target_timeline)
            
            # Get preset configuration
            preset = self.get_preset(preset_name)
            if not preset:
                print(f"❌ Preset '{preset_name}' not found")
                return False
            
            # Generate filename if not provided
            if not output_filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                safe_timeline = timeline_name.replace(" ", "_").replace("-", "_")
                output_filename = f"{safe_timeline}_{preset_name}_{timestamp}.{preset['format']}"
            
            # Get render settings from DaVinci Resolve
            render_settings = project.GetRenderSettings()
            if not render_settings:
                print("❌ Could not get render settings")
                return False
            
            # Update render settings with preset values
            render_settings.update({
                "TargetDirectory": str(Path.cwd() / "renders" / "social_media"),
                "CustomName": output_filename.rsplit('.', 1)[0],  # Remove extension
                "VideoFormat": preset["format"].upper(),
                "VideoCodec": preset["codec"],
                "VideoResolutionWidth": preset["resolution"]["width"],
                "VideoResolutionHeight": preset["resolution"]["height"],
                "VideoFrameRate": preset["framerate"],
                "VideoBitRate": preset["bitrate_video"] * 1000,  # Convert kbps to bps
                "AudioBitRate": preset["bitrate_audio"] * 1000,
                "VideoQuality": preset["quality"]
            })
            
            # Apply render settings
            success = project.SetRenderSettings(render_settings)
            if not success:
                print("❌ Could not apply render settings")
                return False
            
            # Add render job to queue
            job_id = project.AddRenderJob()
            if not job_id:
                print("❌ Could not add render job")
                return False
            
            print(f"✅ Render job created successfully!")
            print(f"   Preset: {preset['name']}")
            print(f"   Timeline: {timeline_name}")
            print(f"   Output: {output_filename}")
            print(f"   Resolution: {preset['resolution']['width']}x{preset['resolution']['height']}")
            print(f"   Job ID: {job_id}")
            
            return job_id
            
        except Exception as e:
            print(f"❌ Error creating render job: {e}")
            return False
    
    def batch_render_social_clips(self, timeline_base_name: str, clips_info: List[Dict]):
        """Create render jobs for multiple social media clips.
        
        Args:
            timeline_base_name: Base name of the timeline (clips should be named with prefixes)
            clips_info: List of clip info with platform recommendations
        """
        results = []
        
        # Create output directory
        output_dir = Path.cwd() / "renders" / "social_media"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        for clip in clips_info:
            clip_name = clip.get("name", "unknown")
            platforms = clip.get("platforms", [])
            
            # Determine best preset for each clip based on its recommended platforms
            if "TikTok" in platforms or "Instagram Stories" in platforms:
                preset_name = "tiktok_vertical"
            elif "Instagram" in platforms and "LinkedIn" not in platforms:
                preset_name = "instagram_square"
            elif "LinkedIn" in platforms or "Twitter" in platforms:
                preset_name = "linkedin_horizontal"
            elif "YouTube Shorts" in platforms:
                preset_name = "youtube_shorts"
            else:
                preset_name = "tiktok_vertical"  # Default to vertical
            
            # Create render job
            timeline_name = f"Social_{clip_name}_{timeline_base_name}"
            job_id = self.create_render_job(preset_name, timeline_name)
            
            results.append({
                "clip_name": clip_name,
                "timeline_name": timeline_name,
                "preset_used": preset_name,
                "job_id": job_id,
                "success": bool(job_id)
            })
        
        return results
    
    def save_preset_library(self, filename: str = "social_media_presets.json"):
        """Save preset library to JSON file."""
        output_file = Path(filename)
        
        preset_library = {
            "generated": datetime.now().isoformat(),
            "description": "Social media render presets for DaVinci Resolve OpenClaw",
            "version": "1.0",
            "presets": self.presets
        }
        
        with open(output_file, 'w') as f:
            json.dump(preset_library, f, indent=2)
        
        print(f"📄 Preset library saved to: {output_file}")
        return output_file

def main():
    """Main entry point for social media render presets."""
    print("🎨 Social Media Render Presets")
    print("=" * 40)
    
    presets = SocialMediaRenderPresets()
    
    # Show available presets
    print("📋 Available Presets:")
    for preset_id, preset in presets.get_all_presets().items():
        print(f"   {preset_id}: {preset['name']}")
        print(f"      Resolution: {preset['resolution']['width']}x{preset['resolution']['height']}")
        print(f"      Platforms: {', '.join(preset['platforms'])}")
        print()
    
    # Save preset library
    presets.save_preset_library()
    
    print("✅ Social media render presets ready for use!")
    print("💡 Use create_render_job() to render with specific presets")

if __name__ == "__main__":
    main()