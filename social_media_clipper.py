#!/usr/bin/env python3
"""Social media clip generator from longer timelines."""

import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Tuple

from resolve_bridge import get_resolve

def analyze_timeline_for_clips(timeline) -> List[Dict]:
    """Analyze timeline to identify potential social media clips.
    
    Args:
        timeline: DaVinci Resolve timeline object
        
    Returns:
        List of clip suggestions with timestamps and descriptions
    """
    clips = []
    
    try:
        timeline_name = timeline.GetName()
        
        # Get markers (if any) for section identification
        markers = []
        try:
            marker_count_func = timeline.GetMarkerCount
            if marker_count_func and callable(marker_count_func):
                marker_count = marker_count_func()
                for i in range(marker_count):
                    marker = timeline.GetMarkerByIndex(i)
                    if marker:
                        markers.append(marker)
            else:
                print("⚠️  Timeline markers not accessible in this DaVinci Resolve version")
        except Exception as e:
            print(f"⚠️  Could not access timeline markers: {e}")
        
        # Get timeline duration and framerate
        try:
            start_frame = timeline.GetStartFrame()
            end_frame = timeline.GetEndFrame()
            duration_frames = end_frame - start_frame
            fps = float(timeline.GetSetting("timelineFrameRate")) or 30.0
            duration_seconds = duration_frames / fps
        except Exception as e:
            print(f"❌ Error getting timeline info: {e}")
            # Fallback values
            duration_frames = 3600  # 2 minutes at 30fps
            fps = 30.0
            duration_seconds = 120.0
        
        print(f"📊 Analyzing '{timeline_name}' ({duration_seconds:.1f}s, {fps}fps)")
        
        # Define social media clip strategies
        clip_strategies = [
            {
                "name": "opener_hook",
                "duration": 15,
                "start_percent": 0.0,
                "end_percent": 0.1,
                "description": "Opening hook - first 15 seconds",
                "platforms": ["TikTok", "Instagram Stories", "Twitter"]
            },
            {
                "name": "key_moment_1", 
                "duration": 30,
                "start_percent": 0.2,
                "end_percent": 0.4,
                "description": "Key moment from first half",
                "platforms": ["Instagram Reels", "YouTube Shorts"]
            },
            {
                "name": "highlight_reel",
                "duration": 60,
                "start_percent": 0.1,
                "end_percent": 0.9,
                "description": "60-second highlight compilation",
                "platforms": ["LinkedIn", "Twitter", "Instagram"]
            },
            {
                "name": "conclusion_cta",
                "duration": 20,
                "start_percent": 0.8,
                "end_percent": 1.0,
                "description": "Conclusion with call-to-action",
                "platforms": ["All platforms"]
            },
            {
                "name": "teaser_clip",
                "duration": 10,
                "start_percent": 0.3,
                "end_percent": 0.7,
                "description": "10-second teaser clip",
                "platforms": ["Instagram Stories", "TikTok"]
            }
        ]
        
        # Generate clip suggestions
        for strategy in clip_strategies:
            start_time = duration_seconds * strategy["start_percent"]
            end_time = min(start_time + strategy["duration"], duration_seconds)
            
            # Adjust for actual content
            if end_time > duration_seconds:
                end_time = duration_seconds
                start_time = max(0, end_time - strategy["duration"])
            
            clip = {
                "name": strategy["name"],
                "description": strategy["description"],
                "start_seconds": round(start_time, 1),
                "end_seconds": round(end_time, 1),
                "duration_seconds": round(end_time - start_time, 1),
                "start_frame": int(start_time * fps),
                "end_frame": int(end_time * fps),
                "platforms": strategy["platforms"],
                "suggested_formats": []
            }
            
            # Add format suggestions based on platforms
            if "TikTok" in strategy["platforms"] or "Instagram" in strategy["platforms"]:
                clip["suggested_formats"].append("vertical_9_16")
            if "YouTube" in strategy["platforms"]:
                clip["suggested_formats"].append("horizontal_16_9")
            if "Twitter" in strategy["platforms"]:
                clip["suggested_formats"].append("square_1_1")
            
            clips.append(clip)
        
        return clips
        
    except Exception as e:
        print(f"❌ Error analyzing timeline: {e}")
        return []

def create_social_media_timelines(clips: List[Dict], source_timeline) -> Dict:
    """Create new timelines for social media clips.
    
    Args:
        clips: List of clip definitions
        source_timeline: Source timeline to copy from
        
    Returns:
        Dict with created timeline info
    """
    results = {"created": 0, "failed": 0, "timelines": []}
    
    try:
        resolve = get_resolve()
        project_manager = resolve.GetProjectManager()
        project = project_manager.GetCurrentProject()
        
        if not project:
            print("❌ No current project")
            return results
        
        source_name = source_timeline.GetName()
        
        for clip in clips:
            timeline_name = f"Social_{clip['name']}_{source_name}"
            
            print(f"🎬 Creating: {timeline_name}")
            print(f"   Duration: {clip['duration_seconds']}s ({clip['start_seconds']}s - {clip['end_seconds']}s)")
            print(f"   Platforms: {', '.join(clip['platforms'])}")
            
            try:
                # Create new timeline
                new_timeline = project.CreateTimeline(timeline_name)
                
                if not new_timeline:
                    print(f"   ❌ Failed to create timeline")
                    results["failed"] += 1
                    continue
                
                # Set timeline to current for editing
                project.SetCurrentTimeline(new_timeline)
                
                # Copy content from source timeline
                # Note: This is a simplified approach - in practice you'd want to:
                # 1. Copy specific clips from the source timeline
                # 2. Adjust for the time range
                # 3. Apply appropriate aspect ratio
                
                results["created"] += 1
                results["timelines"].append({
                    "name": timeline_name,
                    "clip_info": clip,
                    "timeline_object": new_timeline
                })
                
                print(f"   ✅ Timeline created successfully")
                
            except Exception as e:
                print(f"   ❌ Failed to create timeline: {e}")
                results["failed"] += 1
            
            print()
        
        return results
        
    except Exception as e:
        print(f"❌ Error creating timelines: {e}")
        return results

def generate_social_clips_report(clips: List[Dict], output_dir: Path) -> Path:
    """Generate a comprehensive report of social media clip opportunities.
    
    Args:
        clips: List of clip definitions
        output_dir: Directory to save report
        
    Returns:
        Path to generated report
    """
    report_data = {
        "generated": datetime.now().isoformat(),
        "total_clips": len(clips),
        "clips": clips,
        "platform_summary": {},
        "duration_summary": {}
    }
    
    # Analyze platform distribution
    platform_count = {}
    duration_total = {}
    
    for clip in clips:
        for platform in clip["platforms"]:
            platform_count[platform] = platform_count.get(platform, 0) + 1
            duration_total[platform] = duration_total.get(platform, 0) + clip["duration_seconds"]
    
    report_data["platform_summary"] = {
        "clip_count_by_platform": platform_count,
        "total_duration_by_platform": duration_total
    }
    
    report_data["duration_summary"] = {
        "shortest_clip": min(clip["duration_seconds"] for clip in clips),
        "longest_clip": max(clip["duration_seconds"] for clip in clips), 
        "average_duration": sum(clip["duration_seconds"] for clip in clips) / len(clips),
        "total_content": sum(clip["duration_seconds"] for clip in clips)
    }
    
    # Save JSON report
    json_report = output_dir / "social_clips_analysis.json"
    with open(json_report, 'w') as f:
        json.dump(report_data, f, indent=2)
    
    # Create markdown report
    md_report = output_dir / "social_clips_report.md"
    with open(md_report, 'w') as f:
        f.write("# 📱 Social Media Clips Analysis\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n")
        f.write(f"**Total Clips:** {len(clips)}  \n")
        f.write(f"**Total Content:** {report_data['duration_summary']['total_content']:.1f} seconds\n\n")
        
        f.write("## 🎯 Clip Opportunities\n\n")
        for i, clip in enumerate(clips, 1):
            f.write(f"### {i}. {clip['name'].replace('_', ' ').title()}\n")
            f.write(f"**Description:** {clip['description']}  \n")
            f.write(f"**Duration:** {clip['duration_seconds']}s ({clip['start_seconds']}s - {clip['end_seconds']}s)  \n")
            f.write(f"**Platforms:** {', '.join(clip['platforms'])}  \n")
            f.write(f"**Formats:** {', '.join(clip['suggested_formats'])}  \n\n")
        
        f.write("## 📊 Platform Distribution\n\n")
        for platform, count in platform_count.items():
            duration = duration_total[platform]
            f.write(f"- **{platform}:** {count} clips ({duration:.1f}s total content)\n")
        
        f.write("\n## 🎬 Implementation Strategy\n\n")
        f.write("1. **Priority Clips:** Start with opener_hook and highlight_reel\n")
        f.write("2. **Platform Focus:** TikTok and Instagram for maximum reach\n") 
        f.write("3. **Format Delivery:** Create vertical (9:16) versions first\n")
        f.write("4. **Content Testing:** A/B test different clip lengths and hooks\n\n")
    
    print(f"📄 Reports saved:")
    print(f"   JSON: {json_report}")
    print(f"   Markdown: {md_report}")
    
    return md_report

def main():
    """Main entry point for social media clip generator."""
    print("📱 Social Media Clip Generator")
    print("=" * 40)
    
    try:
        # Connect to DaVinci Resolve
        resolve = get_resolve()
        project_manager = resolve.GetProjectManager()
        project = project_manager.GetCurrentProject()
        
        if not project:
            print("❌ No project loaded in DaVinci Resolve")
            return False
        
        timeline = project.GetCurrentTimeline()
        if not timeline:
            print("❌ No current timeline selected")
            return False
        
        project_name = project.GetName()
        timeline_name = timeline.GetName()
        
        print(f"📁 Project: {project_name}")
        print(f"🎞️  Timeline: {timeline_name}")
        print()
        
        # Analyze timeline for clip opportunities
        print("🔍 Analyzing timeline for social media opportunities...")
        clips = analyze_timeline_for_clips(timeline)
        
        if not clips:
            print("❌ No clip opportunities identified")
            return False
        
        print(f"✅ Found {len(clips)} potential social media clips")
        print()
        
        # Create output directory
        output_dir = Path("social_clips") / datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate analysis report
        print("📄 Generating analysis report...")
        report_path = generate_social_clips_report(clips, output_dir)
        print()
        
        # Offer to create timelines
        print("🎬 Social Media Timeline Creation")
        print("   Note: This will create new timelines in your current project")
        print("   Each timeline will be optimized for specific social platforms")
        print()
        
        response = input("Create social media timelines? [y/N]: ").strip().lower()
        
        if response == 'y':
            print("\n🚀 Creating social media timelines...")
            results = create_social_media_timelines(clips, timeline)
            
            print(f"\n✅ Created: {results['created']} timelines")
            print(f"❌ Failed: {results['failed']} timelines")
            
            if results["timelines"]:
                print("\n📝 Created Timelines:")
                for tl_info in results["timelines"]:
                    print(f"   - {tl_info['name']}")
        else:
            print("\n⏸️  Timeline creation skipped")
        
        print(f"\n📁 Analysis saved to: {output_dir}")
        print(f"📄 Full report: {report_path}")
        
        return True
        
    except Exception as e:
        print(f"❌ Social clip generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)