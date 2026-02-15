#!/usr/bin/env python3
"""
Dashboard Data Generator for DaVinci Resolve OpenClaw
Generates real-time data for the web dashboard from analysis files.
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime

def load_project_data(project_path):
    """Load all analysis data for a project."""
    project_path = Path(project_path)
    
    data = {
        'project_name': project_path.name,
        'timestamp': datetime.now().isoformat(),
        'overview': {},
        'clips': [],
        'transcripts': [],
        'analysis': {},
        'renders': []
    }
    
    # Load manifest
    manifest_file = project_path / 'manifest.json'
    if manifest_file.exists():
        with open(manifest_file) as f:
            manifest = json.load(f)
            data['clips'] = manifest.get('clips', [])
            data['overview']['total_clips'] = len(data['clips'])
            data['overview']['total_duration'] = sum(clip.get('duration_seconds', 0) for clip in data['clips'])
    
    # Load speaker diarization
    diarization_file = project_path / 'project_diarization.json'
    if diarization_file.exists():
        with open(diarization_file) as f:
            diarization = json.load(f)
            data['analysis']['diarization'] = diarization
    
    # Load scene analysis
    scene_file = project_path / 'scene_analysis.json'
    if scene_file.exists():
        with open(scene_file) as f:
            scenes = json.load(f)
            data['analysis']['scenes'] = scenes
    
    # Load color grading
    color_file = project_path / f'{project_path.name}_color_grading.json'
    if color_file.exists():
        with open(color_file) as f:
            color_data = json.load(f)
            data['analysis']['color_grading'] = color_data
    
    # Load edit plans
    edit_plans = []
    for plan_file in ['edit_plan.json', 'edit_plan_enhanced.json']:
        plan_path = project_path / plan_file
        if plan_path.exists():
            with open(plan_path) as f:
                plan = json.load(f)
                plan['filename'] = plan_file
                edit_plans.append(plan)
    data['edit_plans'] = edit_plans
    
    # Scan transcripts (JSON format)
    transcript_dir = project_path / '_transcripts'
    if transcript_dir.exists():
        transcripts = []
        for transcript_file in transcript_dir.glob('*.json'):
            try:
                with open(transcript_file, 'r', encoding='utf-8') as f:
                    transcript_data = json.load(f)
                    # Extract text content from JSON
                    text_content = transcript_data.get('text', '')
                    transcripts.append({
                        'filename': transcript_file.name,
                        'content': text_content[:200] + '...' if len(text_content) > 200 else text_content,
                        'word_count': len(text_content.split()),
                        'size': transcript_file.stat().st_size,
                        'language': transcript_data.get('language', 'unknown'),
                        'duration': transcript_data.get('duration', 0)
                    })
            except Exception as e:
                transcripts.append({
                    'filename': transcript_file.name,
                    'error': str(e),
                    'size': transcript_file.stat().st_size
                })
        
        data['transcripts'] = transcripts
        data['overview']['transcription_success'] = len([t for t in transcripts if 'error' not in t])
        data['overview']['transcription_total'] = len(transcripts)
    
    # Calculate success rates
    if data['clips']:
        data['overview']['transcription_rate'] = (
            data['overview'].get('transcription_success', 0) / 
            data['overview']['total_clips'] * 100
        )
        
        # Scene analysis success
        if 'scenes' in data['analysis']:
            analyzed_clips = data['analysis']['scenes'].get('analyzed_clips', 0)
            data['overview']['analysis_rate'] = analyzed_clips / data['overview']['total_clips'] * 100
        else:
            data['overview']['analysis_rate'] = 0
    
    return data

def generate_dashboard_js(project_path, output_path):
    """Generate JavaScript data file for the dashboard."""
    
    data = load_project_data(project_path)
    
    js_content = f"""
// Auto-generated dashboard data
// Generated: {data['timestamp']}
// Project: {data['project_name']}

const dashboardData = {json.dumps(data, indent=2, default=str)};

// Update dashboard with real data
function updateDashboardWithData() {{
    // Update overview stats
    const stats = dashboardData.overview;
    if (document.getElementById('total-clips')) {{
        document.getElementById('total-clips').textContent = stats.total_clips || 0;
        document.getElementById('total-duration').textContent = (stats.total_duration / 60).toFixed(1) || '0.0';
        document.getElementById('transcription-rate').textContent = (stats.transcription_rate || 0).toFixed(1) + '%';
        document.getElementById('analysis-rate').textContent = (stats.analysis_rate || 0).toFixed(1) + '%';
    }}
    
    // Update analysis data when that section loads
    window.realAnalysisData = dashboardData.analysis;
    window.realTranscriptData = dashboardData.transcripts;
    window.realClipsData = dashboardData.clips;
    
    console.log('✅ Dashboard updated with real project data');
}}

// Auto-update when DOM is ready
if (document.readyState === 'loading') {{
    document.addEventListener('DOMContentLoaded', updateDashboardWithData);
}} else {{
    updateDashboardWithData();
}}
"""
    
    with open(output_path, 'w') as f:
        f.write(js_content)
    
    return data

def print_summary(data):
    """Print a summary of the loaded data."""
    print(f"\n🎬 Dashboard Data Summary for '{data['project_name']}'")
    print("=" * 60)
    
    overview = data['overview']
    print(f"📊 Clips: {overview.get('total_clips', 0)}")
    print(f"⏱️  Duration: {overview.get('total_duration', 0) / 60:.1f} minutes")
    print(f"📝 Transcripts: {overview.get('transcription_success', 0)}/{overview.get('transcription_total', 0)} ({overview.get('transcription_rate', 0):.1f}%)")
    print(f"🔍 Analysis: {overview.get('analysis_rate', 0):.1f}% success")
    
    if 'diarization' in data['analysis']:
        project_analysis = data['analysis']['diarization'].get('project_analysis', {})
        unique_speakers = project_analysis.get('unique_speakers', [])
        print(f"🎙️  Speakers: {len(unique_speakers)} identified")
        if unique_speakers:
            for speaker in unique_speakers:
                print(f"   - {speaker}: Active across multiple clips")
    
    if 'scenes' in data['analysis']:
        scenes_data = data['analysis']['scenes']
        if 'scene_summary' in scenes_data and 'shot_scale_distribution' in scenes_data['scene_summary']:
            print("🎬 Scene Types:")
            for scene_type, count in scenes_data['scene_summary']['shot_scale_distribution'].items():
                print(f"   - {scene_type}: {count} clips")
    
    print(f"\n📁 Edit Plans: {len(data.get('edit_plans', []))}")
    for plan in data.get('edit_plans', []):
        print(f"   - {plan['filename']}: {len(plan.get('timeline', {}).get('clips', []))} clips")
    
    print(f"\n✅ Data generated at: {data['timestamp']}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 dashboard_data.py <project_path> [output_js_file]")
        print("Example: python3 dashboard_data.py /Volumes/LaCie/VIDEO/nycap-portalcam")
        return
    
    project_path = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'dashboard_data.js'
    
    if not os.path.exists(project_path):
        print(f"❌ Error: Project path '{project_path}' not found")
        return
    
    try:
        print(f"🔍 Loading project data from: {project_path}")
        data = generate_dashboard_js(project_path, output_file)
        
        print(f"✅ Generated dashboard data: {output_file}")
        print_summary(data)
        
        # Also save the raw JSON for debugging
        json_output = output_file.replace('.js', '.json')
        with open(json_output, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        print(f"📄 Raw data saved: {json_output}")
        
    except Exception as e:
        print(f"❌ Error generating dashboard data: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()