#!/usr/bin/env python3
"""Enhanced pipeline with Phase 5 features: speaker diarization, color grading, and scene detection."""

import json
import os
import sys
from pathlib import Path
import argparse

from ingest import scan_folder, save_manifest
from transcribe import transcribe_project


def run_enhanced_pipeline(project_folder: str, **options):
    """Run the full enhanced editing pipeline with Phase 5 features.
    
    Args:
        project_folder: Path to project folder
        options: Dictionary of pipeline options
    """
    project_folder = os.path.abspath(project_folder)
    print(f"═══════════════════════════════════════")
    print(f"  🚀 Enhanced DaVinci Resolve Pipeline")
    print(f"  Project: {project_folder}")
    print(f"═══════════════════════════════════════\n")

    # Phase 1: Ingest
    print("▶ PHASE 1: Ingesting media...")
    manifest_path = os.path.join(project_folder, "manifest.json")
    
    if os.path.exists(manifest_path):
        print(f"  Using existing manifest: {manifest_path}")
        with open(manifest_path) as f:
            manifest = json.load(f)
    else:
        manifest = scan_folder(project_folder)
        save_manifest(manifest, manifest_path)
    
    print(f"  Found {manifest['total_clips']} clips, {manifest['total_duration_minutes']:.1f} min total\n")

    # Phase 2: Advanced Analysis
    print("▶ PHASE 2: Advanced Analysis...")
    
    # Speaker Diarization (if enabled)
    if options.get('diarization', True):
        print("  🎙️ Analyzing speakers...")
        try:
            from speaker_diarization import diarize_project
            diarization_results = diarize_project(manifest_path)
            if diarization_results:
                speakers_found = diarization_results['project_analysis']['total_speakers']
                print(f"    ✅ Found {speakers_found} unique speakers across project")
            else:
                print(f"    ⚠️ Speaker diarization completed with no speakers detected")
        except Exception as e:
            print(f"    ❌ Speaker diarization failed: {str(e)}")
    
    # Scene Detection (if enabled)
    if options.get('scene_detection', True):
        print("  🎬 Analyzing scenes...")
        try:
            from scene_detection import analyze_project_scenes
            scene_results = analyze_project_scenes(manifest_path)
            if scene_results:
                total_scenes = sum(len(clip_data.get('scenes', [])) for clip_data in scene_results.get('clip_results', {}).values())
                print(f"    ✅ Detected {total_scenes} scene classifications")
            else:
                print(f"    ⚠️ Scene detection completed")
        except Exception as e:
            print(f"    ❌ Scene detection failed: {str(e)}")
    
    # Color Grading Analysis
    print("  🎨 Analyzing camera types...")
    try:
        from color_grading import analyze_project_cameras
        camera_analysis = analyze_project_cameras(manifest_path)
        if camera_analysis:
            print(f"    ✅ Found {camera_analysis['camera_types']} camera types")
            for camera_type, count in camera_analysis['camera_stats'].items():
                percentage = (count / camera_analysis['total_clips']) * 100
                print(f"      {camera_type}: {count} clips ({percentage:.1f}%)")
        else:
            print(f"    ⚠️ Camera analysis completed")
    except Exception as e:
        print(f"    ❌ Camera analysis failed: {str(e)}")
    
    print()

    # Phase 3: Transcription
    print("▶ PHASE 3: Transcribing audio...")
    transcripts = transcribe_project(manifest_path)
    print(f"  Transcribed {len(transcripts)} clips\n")

    # Phase 4: AI Script Generation
    print("▶ PHASE 4: Generating AI edit script...")
    
    script_engine = 'enhanced' if options.get('enhanced_script', True) else 'basic'
    transcripts_dir = os.path.join(project_folder, "_transcripts")
    
    if script_engine == 'enhanced':
        from script_engine_enhanced import generate_enhanced_edit_plan
        edit_plan_path = os.path.join(project_folder, "edit_plan_enhanced.json")
        
        if os.path.exists(edit_plan_path):
            print(f"  Using existing enhanced edit plan: {edit_plan_path}")
            with open(edit_plan_path) as f:
                edit_plan = json.load(f)
        else:
            edit_plan = generate_enhanced_edit_plan(manifest_path, transcripts_dir, edit_plan_path)
    else:
        from script_engine import generate_edit_plan
        edit_plan_path = os.path.join(project_folder, "edit_plan.json")
        
        if os.path.exists(edit_plan_path):
            print(f"  Using existing edit plan: {edit_plan_path}")
            with open(edit_plan_path) as f:
                edit_plan = json.load(f)
        else:
            edit_plan = generate_edit_plan(manifest_path, transcripts_dir, edit_plan_path)
    
    if not edit_plan:
        print("  ❌ Failed to generate edit plan")
        return False
    
    sections = len(edit_plan.get("sections", []))
    total_clips = sum(len(s.get("clips", [])) for s in edit_plan.get("sections", []))
    estimated_duration = edit_plan.get("metadata", {}).get("estimated_duration_minutes", 0)
    print(f"  Generated {script_engine} plan: {sections} sections, {total_clips} clips, ~{estimated_duration:.1f} min\n")

    # Phase 5: Timeline Building
    print("▶ PHASE 5: Building DaVinci Resolve timeline...")
    from timeline_builder import build_timeline_from_plan
    
    project_name = options.get('project_name') or os.path.basename(project_folder)
    
    try:
        timeline = build_timeline_from_plan(edit_plan_path, manifest_path, project_name)
        if not timeline:
            print("  ❌ Failed to create timeline")
            return False
        
        timeline_name = timeline.GetName()
        print(f"  ✅ Timeline created: {timeline_name}")
        
        # Phase 6: Color Grading (if enabled)
        if options.get('color_grading', True):
            print("\n▶ PHASE 6: Applying color grading...")
            try:
                from color_grading import apply_project_color_grading
                uniform_preset = options.get('color_preset')
                success = apply_project_color_grading(manifest_path, project_name, uniform_preset)
                if success:
                    print("  ✅ Color grading applied successfully")
                else:
                    print("  ⚠️ Color grading completed with some issues")
            except Exception as e:
                print(f"  ❌ Color grading failed: {str(e)}")
        
        # Phase 7: Auto-Render (if enabled)
        if options.get('auto_render'):
            print("\n▶ PHASE 7: Auto-rendering...")
            try:
                from auto_export import render_timeline
                render_preset = options.get('render_preset', 'youtube_1080p')
                output_path = os.path.join(project_folder, "renders")
                os.makedirs(output_path, exist_ok=True)
                
                success = render_timeline(project_name, timeline_name, render_preset, output_path)
                if success:
                    print(f"  ✅ Render started with preset: {render_preset}")
                else:
                    print("  ❌ Failed to start render")
            except Exception as e:
                print(f"  ❌ Auto-render failed: {str(e)}")
        
        print("\n" + "="*50)
        print("  🎬 ENHANCED PIPELINE COMPLETE!")
        print(f"  Project: {os.path.basename(project_folder)}")
        print(f"  Timeline: {timeline_name}")
        print(f"  Clips processed: {manifest['total_clips']}")
        print(f"  Total duration: {manifest['total_duration_minutes']:.1f} min")
        print(f"  Edit duration: ~{estimated_duration:.1f} min")
        print(f"  Script type: {script_engine}")
        
        if options.get('color_grading', True):
            print(f"  Color grading: Applied")
        
        if options.get('auto_render'):
            print(f"  Render: {options.get('render_preset', 'youtube_1080p')}")
        
        print("="*50)
        return True
        
    except Exception as e:
        print(f"  ❌ Error in pipeline: {e}")
        return False

def main():
    """Command line interface for enhanced pipeline."""
    parser = argparse.ArgumentParser(description="Enhanced DaVinci Resolve video editing pipeline")
    parser.add_argument("project_folder", help="Path to project folder containing video files")
    parser.add_argument("--project-name", help="Custom project name for DaVinci Resolve")
    parser.add_argument("--basic-script", action="store_true", help="Use basic script engine instead of enhanced")
    parser.add_argument("--no-diarization", action="store_true", help="Skip speaker diarization")
    parser.add_argument("--no-scene-detection", action="store_true", help="Skip scene detection")
    parser.add_argument("--no-color-grading", action="store_true", help="Skip color grading")
    parser.add_argument("--color-preset", choices=['sony', 'dji', 'canon', 'iphone', 'gopro', 'mixed'],
                       help="Apply uniform color preset to all clips")
    parser.add_argument("--auto-render", action="store_true", help="Automatically render after timeline creation")
    parser.add_argument("--render-preset", choices=['youtube_4k', 'youtube_1080p', 'social_media', 'proxy'],
                       default='youtube_1080p', help="Render preset for auto-render")
    
    if len(sys.argv) == 1:
        parser.print_help()
        print("\nExamples:")
        print("  python3 pipeline_enhanced.py /Volumes/LaCie/VIDEO/my-project/")
        print("  python3 pipeline_enhanced.py /path/to/footage --project-name 'Product Review'")
        print("  python3 pipeline_enhanced.py /path/to/footage --color-preset sony --auto-render")
        print("  python3 pipeline_enhanced.py /path/to/footage --basic-script --no-diarization")
        sys.exit(1)
    
    args = parser.parse_args()
    
    # Validate project folder
    if not os.path.exists(args.project_folder):
        print(f"❌ Project folder not found: {args.project_folder}")
        sys.exit(1)
    
    # Build options dictionary
    options = {
        'project_name': args.project_name,
        'enhanced_script': not args.basic_script,
        'diarization': not args.no_diarization,
        'scene_detection': not args.no_scene_detection,
        'color_grading': not args.no_color_grading,
        'color_preset': args.color_preset,
        'auto_render': args.auto_render,
        'render_preset': args.render_preset
    }
    
    # Run the enhanced pipeline
    success = run_enhanced_pipeline(args.project_folder, **options)
    
    if not success:
        print("\n❌ Pipeline failed")
        sys.exit(1)
    
    print("\n✅ Pipeline completed successfully!")

if __name__ == "__main__":
    main()