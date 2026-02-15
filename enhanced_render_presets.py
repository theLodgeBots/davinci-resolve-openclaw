#!/usr/bin/env python3
"""Enhanced render presets for professional broadcast delivery."""

# Additional professional render presets to extend auto_export.py
ENHANCED_RENDER_PRESETS = {
    # Broadcast Standards
    "broadcast_prores422hq": {
        "format": "mov",
        "codec": "ProRes422HQ", 
        "resolution": (1920, 1080),
        "quality": "High",
        "framerate": 29.97,
        "audio_codec": "Linear PCM",
        "audio_bitrate": None,
        "description": "Broadcast ProRes 422 HQ (29.97fps)"
    },
    
    "broadcast_prores4444": {
        "format": "mov", 
        "codec": "ProRes4444",
        "resolution": (1920, 1080),
        "quality": "High",
        "framerate": 29.97,
        "audio_codec": "Linear PCM", 
        "audio_bitrate": None,
        "description": "Premium ProRes 4444 with alpha support"
    },
    
    # Archive/Master Formats
    "archive_uncompressed": {
        "format": "mov",
        "codec": "Uncompressed 10-bit",
        "resolution": None,  # Use timeline resolution
        "quality": "High", 
        "framerate": None,  # Use timeline framerate
        "audio_codec": "Linear PCM",
        "audio_bitrate": None,
        "description": "Uncompressed master for archival"
    },
    
    # Social Media Optimized
    "instagram_stories": {
        "format": "mp4",
        "codec": "H264",
        "resolution": (1080, 1920),  # 9:16 vertical
        "quality": "High",
        "framerate": 30,
        "audio_codec": "AAC",
        "audio_bitrate": 128,
        "description": "Instagram Stories/Reels (9:16 vertical)"
    },
    
    "tiktok_optimized": {
        "format": "mp4", 
        "codec": "H264",
        "resolution": (1080, 1920),  # 9:16 vertical
        "quality": "Medium",
        "framerate": 30,
        "audio_codec": "AAC", 
        "audio_bitrate": 128,
        "description": "TikTok optimized (9:16, smaller file)"
    },
    
    "youtube_shorts": {
        "format": "mp4",
        "codec": "H264",
        "resolution": (1080, 1920),  # 9:16 vertical  
        "quality": "High",
        "framerate": 30,
        "audio_codec": "AAC",
        "audio_bitrate": 192,
        "description": "YouTube Shorts (9:16 vertical)"
    },
    
    # Platform Specific
    "vimeo_hq": {
        "format": "mp4",
        "codec": "H264", 
        "resolution": (1920, 1080),
        "quality": "High",
        "framerate": 24,  # Cinematic framerate
        "audio_codec": "AAC",
        "audio_bitrate": 320,  # Higher audio quality
        "description": "Vimeo high quality (24fps cinematic)"
    },
    
    "twitter_video": {
        "format": "mp4",
        "codec": "H264",
        "resolution": (1280, 720),  # Twitter recommended
        "quality": "Medium",
        "framerate": 30,
        "audio_codec": "AAC",
        "audio_bitrate": 128,
        "description": "Twitter video optimized"
    },
    
    # Client Review Formats  
    "client_review_hq": {
        "format": "mp4",
        "codec": "H264",
        "resolution": (1920, 1080),
        "quality": "High", 
        "framerate": 30,
        "audio_codec": "AAC",
        "audio_bitrate": 256,
        "description": "High quality client review copy"
    },
    
    "client_review_compressed": {
        "format": "mp4",
        "codec": "H264", 
        "resolution": (1280, 720),
        "quality": "Medium",
        "framerate": 30,
        "audio_codec": "AAC",
        "audio_bitrate": 128, 
        "description": "Compressed client review (email friendly)"
    },
    
    # Streaming/Web Delivery
    "web_streaming": {
        "format": "mp4",
        "codec": "H264",
        "resolution": (1920, 1080),
        "quality": "Medium",
        "framerate": 30,
        "audio_codec": "AAC", 
        "audio_bitrate": 192,
        "description": "Web streaming optimized"
    },
    
    "podcast_audio": {
        "format": "wav",
        "codec": None,  # Audio only
        "resolution": None,
        "quality": "High",
        "framerate": None,
        "audio_codec": "Linear PCM",
        "audio_bitrate": None,
        "description": "Audio-only export for podcast/radio"
    }
}

def get_all_presets():
    """Combine original and enhanced presets."""
    # Import from original auto_export
    import sys
    import os
    sys.path.append(os.path.dirname(__file__))
    
    try:
        from auto_export import RENDER_PRESETS
        combined = RENDER_PRESETS.copy()
        combined.update(ENHANCED_RENDER_PRESETS)
        return combined
    except ImportError:
        return ENHANCED_RENDER_PRESETS

def print_all_presets():
    """Print all available render presets."""
    presets = get_all_presets()
    print("📹 Available Render Presets:")
    print("=" * 50)
    
    categories = {
        "Standard": ["youtube_4k", "youtube_1080p", "proxy"],
        "Professional": ["prores", "broadcast_prores422hq", "broadcast_prores4444", "archive_uncompressed"],
        "Social Media": ["social_media", "instagram_stories", "tiktok_optimized", "youtube_shorts"],
        "Platform Specific": ["vimeo_hq", "twitter_video", "web_streaming"],
        "Client Review": ["client_review_hq", "client_review_compressed"],
        "Audio Only": ["podcast_audio"]
    }
    
    for category, preset_list in categories.items():
        print(f"\n🎬 {category}:")
        for preset in preset_list:
            if preset in presets:
                desc = presets[preset]["description"]
                print(f"  {preset:25} - {desc}")

if __name__ == "__main__":
    print_all_presets()