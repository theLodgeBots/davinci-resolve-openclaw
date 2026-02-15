#!/usr/bin/env python3
"""AI-enhanced script engine with scene detection integration."""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

from script_engine_enhanced import generate_enhanced_edit_plan

def load_scene_analysis(project_path: str) -> Optional[Dict]:
    """Load scene analysis data if available."""
    scene_path = os.path.join(project_path, "scene_analysis.json")
    if os.path.exists(scene_path):
        with open(scene_path, 'r') as f:
            return json.load(f)
    return None

def enhance_clip_metadata(clips: List[Dict], scene_analysis: Dict) -> List[Dict]:
    """Enhance clip metadata with scene analysis data."""
    enhanced_clips = []
    
    for clip in clips:
        filename = clip['filename']
        enhanced_clip = clip.copy()
        
        # Add scene analysis if available
        if filename in scene_analysis.get('clips', {}):
            scene_data = scene_analysis['clips'][filename]
            
            if 'error' not in scene_data and 'overall_classification' in scene_data:
                classification = scene_data['overall_classification']
                enhanced_clip['scene'] = {
                    'shot_scale': classification.get('shot_scale', 'unknown'),
                    'shot_movement': classification.get('shot_movement', 'static'),
                    'subject_focus': classification.get('subject_focus', 'unknown'),
                    'subject_count': classification.get('subject_count', 1),
                    'confidence': classification.get('confidence', 0.5),
                    'description': classification.get('description', ''),
                    'consistency': scene_data.get('consistency', {})
                }
        
        enhanced_clips.append(enhanced_clip)
    
    return enhanced_clips

def generate_ai_enhanced_edit_plan(manifest_path: str, transcripts_dir: str, 
                                 output_path: Optional[str] = None) -> Dict:
    """Generate edit plan using AI scene analysis for optimal shot selection.
    
    Args:
        manifest_path: Path to manifest.json
        transcripts_dir: Path to transcripts directory
        output_path: Optional custom output path
    
    Returns:
        Generated edit plan dict
    """
    project_path = os.path.dirname(manifest_path)
    
    # Load manifest
    with open(manifest_path, 'r') as f:
        manifest = json.load(f)
    
    # Load scene analysis
    scene_analysis = load_scene_analysis(project_path)
    
    if not scene_analysis:
        print("⚠️  No scene analysis found. Run 'scenes' command first for optimal results.")
        print("   Falling back to standard enhanced editing...")
        return generate_enhanced_edit_plan(manifest_path, transcripts_dir, output_path)
    
    print("🤖 Using AI scene analysis for enhanced editing...")
    
    # Enhance clips with scene data
    enhanced_clips = enhance_clip_metadata(manifest['clips'], scene_analysis)
    
    # Create enhanced manifest
    enhanced_manifest = manifest.copy()
    enhanced_manifest['clips'] = enhanced_clips
    
    # Generate scene-aware prompt
    scene_summary = scene_analysis.get('scene_summary', {})
    shot_scales = scene_summary.get('shot_scale_distribution', {})
    movements = scene_summary.get('movement_distribution', {})
    subjects = scene_summary.get('subject_distribution', {})
    
    scene_prompt = f"""
SCENE ANALYSIS SUMMARY:
- Shot scales available: {', '.join(shot_scales.keys())}
- Camera movements: {', '.join(movements.keys())}
- Subject types: {', '.join(subjects.keys())}

Use this scene data to create a visually dynamic edit:
1. VARY SHOT SCALES: Mix wide shots, medium shots, and close-ups for visual interest
2. MOVEMENT CONTRAST: Alternate between static and moving shots for pacing
3. SUBJECT MATCHING: Match shot types to content (close-ups for emotional moments, wide shots for context)
4. B-ROLL STRATEGY: Use different shot scales for B-roll to create professional coverage
5. VISUAL RHYTHM: Create a rhythm with shot variety - don't use the same shot scale consecutively

When selecting clips, prioritize:
- High confidence scene classifications
- Varied shot scales within each section
- Movement that matches the content tone
- Visual contrast between adjacent clips

Each clip now includes scene data like:
{{
  "scene": {{
    "shot_scale": "WS|MS|CU|etc",
    "shot_movement": "static|pan|tilt|zoom|tracking", 
    "subject_focus": "person|object|environment|action",
    "confidence": 0.0-1.0
  }}
}}

Use this data to make informed editing decisions.
"""
    
    # Generate edit plan with scene-aware prompt
    return generate_enhanced_edit_plan_with_scenes(
        enhanced_manifest, transcripts_dir, scene_prompt, output_path
    )

def generate_enhanced_edit_plan_with_scenes(manifest: Dict, transcripts_dir: str, 
                                          scene_prompt: str, output_path: Optional[str]) -> Dict:
    """Generate enhanced edit plan using scene analysis data."""
    
    # This would call the OpenAI API with the enhanced prompt and scene data
    # For now, let's create a smart fallback that uses the scene data locally
    
    from script_engine_enhanced import create_enhanced_sections_prompt, call_openai_api
    
    # Load transcripts  
    transcripts = {}
    if os.path.exists(transcripts_dir):
        for filename in os.listdir(transcripts_dir):
            if filename.endswith('.txt'):
                clip_name = filename[:-4]  # Remove .txt
                with open(os.path.join(transcripts_dir, filename), 'r') as f:
                    transcripts[clip_name] = f.read().strip()
    
    # Create scene-aware prompt
    base_prompt = create_enhanced_sections_prompt(manifest, transcripts)
    enhanced_prompt = base_prompt + "\n\n" + scene_prompt
    
    # Call OpenAI with enhanced prompt
    response = call_openai_api(enhanced_prompt)
    
    if not response:
        print("❌ OpenAI API call failed")
        return {}
    
    try:
        edit_plan = json.loads(response)
        
        # Enhance edit plan with scene metadata
        edit_plan = add_scene_metadata_to_plan(edit_plan, manifest)
        
        # Save edit plan
        if not output_path:
            project_path = os.path.dirname(manifest.get('project_path', os.getcwd()))
            output_path = os.path.join(project_path, "edit_plan_ai_enhanced.json")
        
        with open(output_path, 'w') as f:
            json.dump(edit_plan, f, indent=2)
        
        print(f"✅ AI-enhanced edit plan saved: {output_path}")
        
        return edit_plan
        
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse OpenAI response: {e}")
        return {}

def add_scene_metadata_to_plan(edit_plan: Dict, manifest: Dict) -> Dict:
    """Add scene metadata to edit plan clips."""
    
    # Create lookup for enhanced clips
    clip_lookup = {clip['filename']: clip for clip in manifest['clips']}
    
    # Add scene data to each clip in the plan
    for section in edit_plan.get('sections', []):
        for clip_info in section.get('clips', []):
            filename = clip_info['filename']
            if filename in clip_lookup and 'scene' in clip_lookup[filename]:
                clip_info['scene'] = clip_lookup[filename]['scene']
    
    # Add scene summary to metadata
    edit_plan['scene_analysis_used'] = True
    edit_plan['generation_method'] = 'ai_enhanced_with_scenes'
    
    return edit_plan

def analyze_edit_variety(edit_plan: Dict) -> Dict:
    """Analyze shot variety and visual dynamics in the edit plan."""
    analysis = {
        'total_clips': 0,
        'clips_with_scene_data': 0,
        'shot_scale_variety': {},
        'movement_variety': {},
        'subject_variety': {},
        'sections_analysis': []
    }
    
    from collections import Counter
    
    all_scales = []
    all_movements = []
    all_subjects = []
    
    for section in edit_plan.get('sections', []):
        section_analysis = {
            'title': section.get('title', 'Untitled'),
            'clip_count': len(section.get('clips', [])),
            'scene_clips': 0,
            'shot_scales': [],
            'movements': [],
            'subjects': []
        }
        
        for clip_info in section.get('clips', []):
            analysis['total_clips'] += 1
            
            if 'scene' in clip_info:
                analysis['clips_with_scene_data'] += 1
                section_analysis['scene_clips'] += 1
                
                scene = clip_info['scene']
                scale = scene.get('shot_scale', 'unknown')
                movement = scene.get('shot_movement', 'unknown')
                subject = scene.get('subject_focus', 'unknown')
                
                all_scales.append(scale)
                all_movements.append(movement)
                all_subjects.append(subject)
                
                section_analysis['shot_scales'].append(scale)
                section_analysis['movements'].append(movement)
                section_analysis['subjects'].append(subject)
        
        # Analyze variety within section
        section_analysis['scale_variety'] = len(set(section_analysis['shot_scales']))
        section_analysis['movement_variety'] = len(set(section_analysis['movements']))
        section_analysis['subject_variety'] = len(set(section_analysis['subjects']))
        
        analysis['sections_analysis'].append(section_analysis)
    
    # Overall variety analysis
    analysis['shot_scale_variety'] = dict(Counter(all_scales))
    analysis['movement_variety'] = dict(Counter(all_movements))
    analysis['subject_variety'] = dict(Counter(all_subjects))
    
    # Calculate variety scores (0-1)
    analysis['variety_scores'] = {
        'shot_scale_diversity': len(set(all_scales)) / max(len(all_scales), 1),
        'movement_diversity': len(set(all_movements)) / max(len(all_movements), 1),
        'subject_diversity': len(set(all_subjects)) / max(len(all_subjects), 1)
    }
    
    return analysis

def main():
    """Command line interface for AI-enhanced script generation."""
    if len(sys.argv) < 3:
        print("Usage: python3 script_engine_ai.py /path/to/manifest.json /path/to/_transcripts [output_path]")
        sys.exit(1)
    
    manifest_path = sys.argv[1]
    transcripts_dir = sys.argv[2]
    output_path = sys.argv[3] if len(sys.argv) > 3 else None
    
    if not os.path.exists(manifest_path):
        print(f"❌ Manifest not found: {manifest_path}")
        sys.exit(1)
    
    if not os.path.exists(transcripts_dir):
        print(f"❌ Transcripts directory not found: {transcripts_dir}")
        sys.exit(1)
    
    print("🤖 AI-Enhanced Script Generation (with Scene Analysis)")
    print("=" * 55)
    
    try:
        edit_plan = generate_ai_enhanced_edit_plan(manifest_path, transcripts_dir, output_path)
        
        if not edit_plan:
            print("❌ Failed to generate edit plan")
            sys.exit(1)
        
        # Analyze edit variety
        variety_analysis = analyze_edit_variety(edit_plan)
        
        # Print results
        sections = len(edit_plan.get("sections", []))
        total_clips = variety_analysis['total_clips']
        scene_clips = variety_analysis['clips_with_scene_data']
        
        print(f"\n✅ Generated AI-enhanced edit plan:")
        print(f"   Title: {edit_plan.get('title', 'Untitled')}")
        print(f"   Sections: {sections}")
        print(f"   Total clips: {total_clips}")
        print(f"   Clips with scene data: {scene_clips}/{total_clips} ({scene_clips/max(total_clips,1)*100:.1f}%)")
        print(f"   Estimated duration: {edit_plan.get('estimated_duration_seconds', 0)//60:.0f}:{edit_plan.get('estimated_duration_seconds', 0)%60:02.0f}")
        
        print(f"\n🎨 Visual variety analysis:")
        variety = variety_analysis['variety_scores']
        print(f"   Shot scale diversity: {variety['shot_scale_diversity']:.1%}")
        print(f"   Movement diversity: {variety['movement_diversity']:.1%}")
        print(f"   Subject diversity: {variety['subject_diversity']:.1%}")
        
        print(f"\n📊 Shot distribution:")
        for shot_type, count in variety_analysis['shot_scale_variety'].items():
            print(f"   {shot_type}: {count}")
        
        final_path = output_path or os.path.join(os.path.dirname(manifest_path), "edit_plan_ai_enhanced.json")
        print(f"\n💾 Edit plan saved: {final_path}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()