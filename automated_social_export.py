#!/usr/bin/env python3
"""Automated social media export system combining clip analysis with render presets."""

import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

from social_media_clipper import analyze_timeline_for_clips, generate_social_clips_report
from social_media_render_presets import SocialMediaRenderPresets
from resolve_bridge import get_resolve

class AutomatedSocialExport:
    """Complete automated social media export system."""
    
    def __init__(self):
        self.presets = SocialMediaRenderPresets()
        self.export_dir = Path.cwd() / "exports" / "social_media"
        self.export_dir.mkdir(parents=True, exist_ok=True)
    
    def analyze_and_export(self, timeline_name: str = None, create_timelines: bool = False, start_renders: bool = False):
        """Complete workflow: analyze timeline for clips, create optimized renders.
        
        Args:
            timeline_name: Specific timeline name (uses current if None)
            create_timelines: Whether to attempt creating clip timelines in DaVinci
            start_renders: Whether to start render queue after adding jobs
        """
        print("🚀 Automated Social Media Export System")
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
                print("❌ No project loaded in DaVinci Resolve")
                return False
            
            # Get timeline
            if timeline_name:
                timeline = self._find_timeline(project, timeline_name)
                if not timeline:
                    print(f"❌ Timeline '{timeline_name}' not found")
                    return False
                project.SetCurrentTimeline(timeline)
            else:
                timeline = project.GetCurrentTimeline()
                if not timeline:
                    print("❌ No current timeline selected")
                    return False
                timeline_name = timeline.GetName()
            
            project_name = project.GetName()
            
            print(f"📁 Project: {project_name}")
            print(f"🎞️  Timeline: {timeline_name}")
            print()
            
            # Step 1: Analyze timeline for social media clips
            print("🔍 Step 1: Analyzing timeline for social media opportunities...")
            clips = analyze_timeline_for_clips(timeline)
            
            if not clips:
                print("❌ No social media clips identified")
                return False
            
            print(f"✅ Found {len(clips)} potential social media clips")
            
            # Step 2: Generate analysis report
            print("📄 Step 2: Generating detailed analysis report...")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            analysis_dir = Path("social_clips") / timestamp
            analysis_dir.mkdir(parents=True, exist_ok=True)
            
            report_path = generate_social_clips_report(clips, analysis_dir)
            print(f"✅ Analysis report saved: {report_path}")
            
            # Step 3: Create export strategy
            print("🎯 Step 3: Creating platform-optimized export strategy...")
            export_strategy = self._create_export_strategy(clips, timeline_name)
            
            # Save strategy to file
            strategy_file = analysis_dir / "export_strategy.json"
            with open(strategy_file, 'w') as f:
                json.dump(export_strategy, f, indent=2)
            
            print(f"✅ Export strategy saved: {strategy_file}")
            print()
            
            # Display export plan
            self._display_export_plan(export_strategy)
            
            # Step 4: Generate render presets documentation
            print("📋 Step 4: Generating render presets documentation...")
            presets_file = analysis_dir / "render_presets_used.json"
            self.presets.save_preset_library(str(presets_file))
            
            # Step 5: Create timeline extraction guides (since auto-creation fails)
            print("📖 Step 5: Creating manual timeline extraction guides...")
            self._create_timeline_guides(export_strategy, analysis_dir)
            
            # Step 6: Summary report
            summary_file = analysis_dir / "SOCIAL_EXPORT_SUMMARY.md"
            self._create_summary_report(export_strategy, clips, timeline_name, summary_file)
            
            print(f"\n✅ Automated Social Export Analysis Complete!")
            print(f"📁 All files saved to: {analysis_dir}")
            print(f"📋 Next steps: See {summary_file}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error in automated export: {e}")
            return False
    
    def _find_timeline(self, project, timeline_name: str):
        """Find timeline by name in project."""
        timeline_count = project.GetTimelineCount()
        for i in range(timeline_count):
            timeline = project.GetTimelineByIndex(i + 1)
            if timeline and timeline.GetName() == timeline_name:
                return timeline
        return None
    
    def _create_export_strategy(self, clips: List[Dict], timeline_name: str) -> Dict:
        """Create comprehensive export strategy for all clips."""
        strategy = {
            "timeline_name": timeline_name,
            "generated": datetime.now().isoformat(),
            "total_clips": len(clips),
            "exports": []
        }
        
        for clip in clips:
            platforms = clip.get("platforms", [])
            
            # Determine optimal presets for this clip
            clip_exports = []
            
            # Vertical formats (9:16)
            if any(p in platforms for p in ["TikTok", "Instagram Stories", "YouTube Shorts"]):
                if "TikTok" in platforms or "Instagram Stories" in platforms:
                    clip_exports.append({
                        "preset": "tiktok_vertical",
                        "priority": "high",
                        "platforms": ["TikTok", "Instagram Stories"]
                    })
                
                if "YouTube Shorts" in platforms:
                    clip_exports.append({
                        "preset": "youtube_shorts", 
                        "priority": "medium",
                        "platforms": ["YouTube Shorts"]
                    })
                
                if "Instagram Reels" in platforms:
                    clip_exports.append({
                        "preset": "instagram_reels",
                        "priority": "high", 
                        "platforms": ["Instagram Reels", "Facebook Reels"]
                    })
            
            # Square format (1:1)
            if any(p in platforms for p in ["Instagram", "Facebook"]) and "Stories" not in str(platforms):
                clip_exports.append({
                    "preset": "instagram_square",
                    "priority": "medium",
                    "platforms": ["Instagram Post", "Facebook"]
                })
            
            # Horizontal formats (16:9)
            if any(p in platforms for p in ["LinkedIn", "Twitter"]):
                if "LinkedIn" in platforms:
                    clip_exports.append({
                        "preset": "linkedin_horizontal",
                        "priority": "high",
                        "platforms": ["LinkedIn", "Professional networks"]
                    })
                else:
                    clip_exports.append({
                        "preset": "twitter_optimized", 
                        "priority": "medium",
                        "platforms": ["Twitter", "X"]
                    })
            
            # Add to strategy
            strategy["exports"].append({
                "clip_name": clip["name"],
                "clip_description": clip["description"],
                "duration_seconds": clip["duration_seconds"],
                "start_seconds": clip["start_seconds"],
                "end_seconds": clip["end_seconds"],
                "source_platforms": platforms,
                "export_variants": clip_exports,
                "total_exports": len(clip_exports)
            })
        
        # Calculate totals
        total_exports = sum(len(export["export_variants"]) for export in strategy["exports"])
        strategy["total_export_jobs"] = total_exports
        
        return strategy
    
    def _display_export_plan(self, strategy: Dict):
        """Display the export plan in a readable format."""
        print("🎬 Export Plan Summary:")
        print(f"   📊 {strategy['total_clips']} clips → {strategy['total_export_jobs']} export jobs")
        print()
        
        for export in strategy["exports"]:
            clip_name = export["clip_name"].replace("_", " ").title()
            duration = export["duration_seconds"]
            variants = len(export["export_variants"])
            
            print(f"📱 {clip_name} ({duration}s)")
            for variant in export["export_variants"]:
                preset_info = self.presets.get_preset(variant["preset"])
                resolution = f"{preset_info['resolution']['width']}x{preset_info['resolution']['height']}"
                platforms = ", ".join(variant["platforms"])
                priority = variant["priority"].upper()
                
                print(f"   → {preset_info['name']} ({resolution}) - {platforms} [{priority}]")
            print()
    
    def _create_timeline_guides(self, strategy: Dict, output_dir: Path):
        """Create manual timeline extraction guides."""
        guides_dir = output_dir / "timeline_guides"
        guides_dir.mkdir(exist_ok=True)
        
        for export in strategy["exports"]:
            clip_name = export["clip_name"]
            guide_file = guides_dir / f"{clip_name}_extraction_guide.md"
            
            with open(guide_file, 'w') as f:
                f.write(f"# {clip_name.replace('_', ' ').title()} Extraction Guide\n\n")
                f.write(f"**Source Timeline:** {strategy['timeline_name']}  \n")
                f.write(f"**Duration:** {export['duration_seconds']}s  \n") 
                f.write(f"**Time Range:** {export['start_seconds']}s - {export['end_seconds']}s  \n\n")
                
                f.write("## Manual Extraction Steps\n\n")
                f.write("1. **Set In/Out Points:**\n")
                f.write(f"   - Navigate to {export['start_seconds']}s in timeline\n")
                f.write(f"   - Press `I` to set In point\n")
                f.write(f"   - Navigate to {export['end_seconds']}s in timeline\n")
                f.write(f"   - Press `O` to set Out point\n\n")
                
                f.write("2. **Create New Timeline:**\n")
                f.write(f"   - Right-click in Media Pool → Create New Timeline\n")
                f.write(f"   - Name: `Social_{clip_name}_{strategy['timeline_name']}`\n")
                f.write(f"   - Copy In/Out selection to new timeline\n\n")
                
                f.write("## Recommended Export Formats\n\n")
                for variant in export["export_variants"]:
                    preset_info = self.presets.get_preset(variant["preset"])
                    f.write(f"### {preset_info['name']}\n")
                    f.write(f"**Resolution:** {preset_info['resolution']['width']}x{preset_info['resolution']['height']}  \n")
                    f.write(f"**Platforms:** {', '.join(variant['platforms'])}  \n")
                    f.write(f"**Priority:** {variant['priority']}  \n\n")
        
        print(f"📖 Timeline extraction guides created: {guides_dir}")
    
    def _create_summary_report(self, strategy: Dict, clips: List[Dict], timeline_name: str, output_file: Path):
        """Create comprehensive summary report."""
        with open(output_file, 'w') as f:
            f.write("# 📱 Social Media Export Summary\n\n")
            f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n")
            f.write(f"**Source Timeline:** {timeline_name}  \n")
            f.write(f"**Total Clips:** {strategy['total_clips']}  \n")
            f.write(f"**Total Export Jobs:** {strategy['total_export_jobs']}  \n\n")
            
            f.write("## 🎯 Export Strategy Overview\n\n")
            f.write("This automated analysis identified strategic social media clip opportunities and ")
            f.write("created platform-optimized export recommendations.\n\n")
            
            f.write("### Platform Distribution:\n")
            platform_count = {}
            for export in strategy["exports"]:
                for variant in export["export_variants"]:
                    for platform in variant["platforms"]:
                        platform_count[platform] = platform_count.get(platform, 0) + 1
            
            for platform, count in sorted(platform_count.items()):
                f.write(f"- **{platform}:** {count} export variants\n")
            
            f.write("\n## 📊 Clip Analysis Results\n\n")
            for i, export in enumerate(strategy["exports"], 1):
                f.write(f"### {i}. {export['clip_name'].replace('_', ' ').title()}\n")
                f.write(f"**Description:** {export['clip_description']}  \n")
                f.write(f"**Duration:** {export['duration_seconds']}s ({export['start_seconds']}s - {export['end_seconds']}s)  \n")
                f.write(f"**Export Variants:** {export['total_exports']}  \n\n")
                
                for variant in export["export_variants"]:
                    preset_info = self.presets.get_preset(variant["preset"])
                    f.write(f"- **{preset_info['name']}** ({preset_info['resolution']['width']}x{preset_info['resolution']['height']}) → {', '.join(variant['platforms'])}\n")
                f.write("\n")
            
            f.write("## 🚀 Implementation Roadmap\n\n")
            f.write("### Phase 1: High Priority Clips\n")
            high_priority = [e for e in strategy["exports"] for v in e["export_variants"] if v["priority"] == "high"]
            f.write(f"- **{len(high_priority)} high-priority export jobs**\n")
            f.write("- Focus on TikTok vertical, Instagram Reels, and LinkedIn horizontal formats\n")
            f.write("- These provide maximum reach and engagement potential\n\n")
            
            f.write("### Phase 2: Complete Coverage\n")
            f.write(f"- **{strategy['total_export_jobs']} total export jobs** for complete platform coverage\n")
            f.write("- All major social media platforms represented\n")
            f.write("- Multiple format options for A/B testing\n\n")
            
            f.write("## 📁 Generated Files\n\n")
            f.write("- `social_clips_analysis.json` - Raw clip analysis data\n")
            f.write("- `social_clips_report.md` - Human-readable clip analysis\n")
            f.write("- `export_strategy.json` - Complete export strategy\n")
            f.write("- `render_presets_used.json` - Technical render specifications\n")
            f.write("- `timeline_guides/` - Manual extraction guides for each clip\n")
            f.write("- `SOCIAL_EXPORT_SUMMARY.md` - This summary document\n\n")
            
            f.write("## 💼 Business Impact\n\n")
            total_content = sum(c["duration_seconds"] for c in clips)
            f.write(f"**Content Multiplication:** 1 timeline ({timeline_name}) → {strategy['total_export_jobs']} social media assets  \n")
            f.write(f"**Total Social Content:** {total_content}s ({total_content/60:.1f} minutes)  \n")
            f.write(f"**Platform Coverage:** {len(platform_count)} different platforms  \n")
            f.write(f"**ROI Enhancement:** Each video shoot now produces {strategy['total_export_jobs']}x more deliverable content  \n\n")
            
            f.write("---\n\n")
            f.write("*Generated by DaVinci Resolve OpenClaw - Automated Social Media Export System*  \n")
            f.write("*Ready for immediate implementation and client presentation*\n")
        
        print(f"📋 Summary report created: {output_file}")

def main():
    """Main entry point."""
    print("🤖 DaVinci Resolve OpenClaw - Automated Social Export")
    print("=" * 60)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("Usage: python3 automated_social_export.py [timeline_name]")
        print()
        print("Analyzes current (or specified) timeline and creates comprehensive")
        print("social media export strategy with platform-optimized recommendations.")
        return
    
    timeline_name = sys.argv[1] if len(sys.argv) > 1 else None
    
    exporter = AutomatedSocialExport()
    success = exporter.analyze_and_export(timeline_name)
    
    if success:
        print("\n🎉 Social media export analysis complete!")
        print("📁 Check the social_clips/ directory for all generated files")
        print("🚀 Ready to multiply your content across all social platforms!")
    else:
        print("\n❌ Export analysis failed - check DaVinci Resolve connection")

if __name__ == "__main__":
    main()