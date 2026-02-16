#!/usr/bin/env python3
"""
🎬 DaVinci Resolve OpenClaw - Social Media Export Guide Generator
Creates detailed manual instructions for social media exports since API automation has limitations.

Usage:
    python3 social_export_guide_generator.py [analysis_folder]
"""

import sys
import json
from pathlib import Path
from datetime import datetime

def load_analysis_data(analysis_folder):
    """Load export strategy from analysis folder"""
    strategy_path = Path(analysis_folder) / "export_strategy.json"
    presets_path = Path(analysis_folder) / "render_presets_used.json"
    
    if not strategy_path.exists():
        print(f"❌ Export strategy file not found: {strategy_path}")
        return None, None
    
    try:
        with open(strategy_path, 'r') as f:
            strategy = json.load(f)
        
        presets = None
        if presets_path.exists():
            with open(presets_path, 'r') as f:
                presets = json.load(f)
        
        return strategy, presets
    except Exception as e:
        print(f"❌ Error loading analysis data: {e}")
        return None, None

def generate_export_guide(strategy, presets, output_file):
    """Generate comprehensive manual export guide"""
    
    guide_content = f"""# 🎬 Social Media Export Guide
**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**Source:** {strategy['timeline_name']}  
**Total Exports:** {strategy['total_export_jobs']} social media variants

---

## 📋 Quick Reference

| Clip | Duration | Start Time | Preset | Priority | Platforms |
|------|----------|------------|--------|----------|-----------|"""

    for clip in strategy["exports"]:
        for variant in clip["export_variants"]:
            platforms = ", ".join(variant["platforms"])
            guide_content += f"""
| {clip['clip_name']} | {clip['duration_seconds']}s | {clip['start_seconds']}s | {variant['preset']} | {variant['priority']} | {platforms} |"""

    guide_content += """

---

## 🎯 Step-by-Step Export Instructions

### 1️⃣ Setup
1. Open DaVinci Resolve
2. Load project and navigate to the **Deliver** page
3. Set the current timeline: **""" + strategy['timeline_name'] + """**

### 2️⃣ Export Each Clip

"""

    job_counter = 1
    for clip in strategy["exports"]:
        if len(clip["export_variants"]) == 0:
            continue
            
        guide_content += f"""
#### 🎞️ Clip {job_counter}: {clip['clip_name']}
**Description:** {clip.get('clip_description', 'No description')}  
**Timing:** {clip['start_seconds']}s - {clip['end_seconds']}s ({clip['duration_seconds']}s)

"""
        
        for variant in clip["export_variants"]:
            preset_name = variant["preset"]
            priority = variant["priority"]
            platforms = ", ".join(variant["platforms"])
            
            # Get preset details if available
            preset_details = ""
            if presets and preset_name in presets.get("presets", {}):
                preset_config = presets["presets"][preset_name]
                preset_details = f"""
**Resolution:** {preset_config.get('width', '?')}×{preset_config.get('height', '?')}  
**Frame Rate:** {preset_config.get('framerate', '?')} fps  
**Quality:** {preset_config.get('quality', '?')}%"""

            guide_content += f"""
##### 📱 Export: {preset_name} ({priority} priority)
**Target Platforms:** {platforms}{preset_details}

**Manual Steps:**
1. Set **In Point** to frame {int(clip['start_seconds'] * 24)} (timecode: {format_timecode(clip['start_seconds'])})
2. Set **Out Point** to frame {int(clip['end_seconds'] * 24)} (timecode: {format_timecode(clip['end_seconds'])})
3. Choose render preset: **YouTube - 1080p** (closest available)
4. Set output filename: `{clip['clip_name']}_{preset_name}_{int(clip['duration_seconds'])}s`
5. Set output directory: `exports/social_media/`
6. Add to render queue
7. ✅ **Added to queue:** `{clip['clip_name']}_{preset_name}_{int(clip['duration_seconds'])}s.mp4`

---
"""
        job_counter += 1

    guide_content += """
### 3️⃣ Batch Render
1. Review all render jobs in the queue
2. Click **Start Render** to process all jobs
3. Monitor progress in the render queue
4. Check `exports/social_media/` for completed files

---

## 📱 Social Media Specifications

### Platform Requirements:
"""

    # Add preset specifications if available
    if presets:
        for preset_name, preset_config in presets.get("presets", {}).items():
            guide_content += f"""
#### {preset_config.get('name', preset_name)}
- **Resolution:** {preset_config.get('width', '?')}×{preset_config.get('height', '?')}
- **Aspect Ratio:** {preset_config.get('aspect_ratio', 'Custom')}
- **Frame Rate:** {preset_config.get('framerate', 30)} fps
- **Bitrate:** {preset_config.get('bitrate', 'Auto')} Mbps
- **Max Duration:** {preset_config.get('max_duration', 'No limit')}
"""

    guide_content += """
---

## 🚀 Export Automation Script

For future automation, save this Python snippet:

```python
#!/usr/bin/env python3
import sys
sys.path.append('/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules/')
import DaVinciResolveScript as dvr

# Connect to DaVinci Resolve
resolve = dvr.scriptapp('Resolve')
project = resolve.GetProjectManager().GetCurrentProject()

# Start rendering all queued jobs
print("🚀 Starting render queue...")
result = project.StartRendering()
print(f"Render started: {result}")

# Check progress
while project.IsRenderingInProgress():
    print("⏳ Rendering in progress...")
    import time
    time.sleep(10)

print("✅ Rendering completed!")
```

---

## 📊 Expected Output Files

After rendering, you should have these files in `exports/social_media/`:

"""

    for clip in strategy["exports"]:
        for variant in clip["export_variants"]:
            expected_filename = f"{clip['clip_name']}_{variant['preset']}_{int(clip['duration_seconds'])}s.mp4"
            guide_content += f"- `{expected_filename}` ({clip['duration_seconds']}s, {variant['priority']} priority)\n"

    guide_content += f"""
**Total Files:** {strategy['total_export_jobs']} social media variants  
**Total Content:** {sum(clip['duration_seconds'] * len(clip['export_variants']) for clip in strategy['exports'])}s of optimized content

---

## 💡 Tips for Success

1. **Use Timeline Markers:** Add markers at key moments for easier navigation
2. **Color Grading:** Apply platform-specific color correction if needed  
3. **Audio Levels:** Check audio levels for each platform's requirements
4. **File Size:** Monitor output file sizes for platform limits
5. **Quality Control:** Preview each export before uploading

---

*Generated by DaVinci Resolve OpenClaw Social Export System*  
*Ready for professional social media distribution* 🎬✨
"""

    # Write guide to file
    with open(output_file, 'w') as f:
        f.write(guide_content)
    
    return guide_content

def format_timecode(seconds):
    """Convert seconds to SMPTE timecode format"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    frames = int((seconds % 1) * 24)  # Assuming 24fps
    return f"{hours:02d}:{minutes:02d}:{secs:02d}:{frames:02d}"

def main():
    if len(sys.argv) < 2:
        print("❌ Analysis folder not provided")
        print("Usage: python3 social_export_guide_generator.py [analysis_folder]")
        sys.exit(1)
    
    analysis_folder = Path(sys.argv[1])
    if not analysis_folder.exists():
        print(f"❌ Analysis folder not found: {analysis_folder}")
        sys.exit(1)
    
    print("🎬 DaVinci Resolve OpenClaw - Social Export Guide Generator")
    print(f"📁 Analysis Folder: {analysis_folder}")
    print("=" * 60)
    
    # Load analysis data
    strategy, presets = load_analysis_data(analysis_folder)
    if not strategy:
        sys.exit(1)
    
    print(f"📊 Loaded export strategy: {len(strategy['exports'])} clips")
    print(f"🎯 Timeline: {strategy['timeline_name']}")
    print(f"📱 Total exports: {strategy['total_export_jobs']}")
    
    # Generate export guide
    output_file = analysis_folder / "SOCIAL_EXPORT_GUIDE.md"
    guide_content = generate_export_guide(strategy, presets, output_file)
    
    print(f"\n✅ Export guide generated: {output_file}")
    print(f"📄 Guide length: {len(guide_content)} characters")
    
    # Also create a simple checklist
    checklist_file = analysis_folder / "export_checklist.txt"
    checklist_content = f"""🎬 Social Media Export Checklist - {datetime.now().strftime('%Y-%m-%d')}

Timeline: {strategy['timeline_name']}
Total Exports: {strategy['total_export_jobs']}

Quick Checklist:
"""
    
    for clip in strategy["exports"]:
        for variant in clip["export_variants"]:
            filename = f"{clip['clip_name']}_{variant['preset']}_{int(clip['duration_seconds'])}s"
            checklist_content += f"☐ {filename} ({clip['start_seconds']}s-{clip['end_seconds']}s)\n"
    
    with open(checklist_file, 'w') as f:
        f.write(checklist_content)
    
    print(f"📋 Checklist created: {checklist_file}")
    
    print("\n🚀 NEXT STEPS:")
    print(f"1. Open the guide: {output_file}")
    print("2. Follow step-by-step instructions in DaVinci Resolve")
    print("3. Use the checklist to track progress")
    print("4. Check exports/social_media/ for completed files")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())