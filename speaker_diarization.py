#!/usr/bin/env python3
"""Speaker diarization for multi-person video footage."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import requests
import time

# OpenAI API for speaker identification
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_API_URL = "https://api.openai.com/v1/audio/transcriptions"

def extract_audio_segments(video_path: str, output_dir: str, segment_duration: float = 30.0) -> List[str]:
    """Extract audio segments from video for diarization analysis.
    
    Args:
        video_path: Path to video file
        output_dir: Directory to save audio segments
        segment_duration: Duration of each segment in seconds
    
    Returns:
        List of audio segment file paths
    """
    print(f"  Extracting audio segments from {os.path.basename(video_path)}...")
    
    # Get video duration first
    duration_cmd = [
        'ffprobe', '-v', 'quiet', '-print_format', 'json', 
        '-show_format', video_path
    ]
    
    try:
        result = subprocess.run(duration_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"    ❌ Could not get duration for {video_path}")
            return []
        
        metadata = json.loads(result.stdout)
        total_duration = float(metadata['format']['duration'])
        
    except (json.JSONDecodeError, KeyError, ValueError):
        print(f"    ❌ Invalid metadata for {video_path}")
        return []
    
    # Create segments directory
    video_name = Path(video_path).stem
    segment_dir = os.path.join(output_dir, f"{video_name}_segments")
    os.makedirs(segment_dir, exist_ok=True)
    
    segments = []
    current_time = 0
    
    while current_time < total_duration:
        # Calculate segment end time
        end_time = min(current_time + segment_duration, total_duration)
        segment_duration_actual = end_time - current_time
        
        # Skip very short segments
        if segment_duration_actual < 5.0:
            break
        
        # Create segment filename
        segment_filename = f"segment_{int(current_time):04d}s.wav"
        segment_path = os.path.join(segment_dir, segment_filename)
        
        # Extract audio segment
        extract_cmd = [
            'ffmpeg', '-i', video_path,
            '-ss', str(current_time),
            '-t', str(segment_duration_actual),
            '-vn',  # No video
            '-acodec', 'pcm_s16le',
            '-ar', '16000',  # 16kHz for Whisper
            '-ac', '1',      # Mono
            '-y',
            segment_path
        ]
        
        result = subprocess.run(extract_cmd, capture_output=True, text=True)
        if result.returncode == 0:
            segments.append(segment_path)
            print(f"    ✅ {segment_filename} ({segment_duration_actual:.1f}s)")
        else:
            print(f"    ❌ Failed to extract {segment_filename}")
        
        current_time += segment_duration
    
    return segments

def identify_speakers_whisper(audio_segments: List[str]) -> List[Dict]:
    """Use OpenAI Whisper API to identify speakers in audio segments.
    
    Args:
        audio_segments: List of audio segment file paths
    
    Returns:
        List of speaker identification results
    """
    if not OPENAI_API_KEY:
        print("    ❌ OpenAI API key not found. Set OPENAI_API_KEY environment variable.")
        return []
    
    print(f"  Analyzing {len(audio_segments)} segments for speaker identification...")
    
    results = []
    for i, segment_path in enumerate(audio_segments):
        print(f"    Processing segment {i+1}/{len(audio_segments)}...")
        
        try:
            # Read audio file
            with open(segment_path, 'rb') as audio_file:
                # Use Whisper API with speaker detection prompt
                files = {
                    'file': (os.path.basename(segment_path), audio_file, 'audio/wav'),
                    'model': (None, 'whisper-1'),
                    'language': (None, 'en'),
                    'prompt': (None, 'Identify different speakers. Include speaker labels like "Speaker 1:" and "Speaker 2:" in the transcript.'),
                    'response_format': (None, 'verbose_json')
                }
                
                headers = {'Authorization': f'Bearer {OPENAI_API_KEY}'}
                response = requests.post(OPENAI_API_URL, headers=headers, files=files)
                
                if response.status_code == 200:
                    transcription = response.json()
                    
                    # Extract timing info from segment filename
                    segment_name = os.path.basename(segment_path)
                    start_time = int(segment_name.split('_')[1].replace('s.wav', ''))
                    
                    result = {
                        'segment_path': segment_path,
                        'start_time': start_time,
                        'transcription': transcription,
                        'text': transcription.get('text', ''),
                        'speakers_detected': identify_speakers_in_text(transcription.get('text', ''))
                    }
                    results.append(result)
                    
                    print(f"      ✅ {len(result['speakers_detected'])} speaker(s) detected")
                    
                else:
                    print(f"      ❌ API error: {response.status_code}")
                    
        except Exception as e:
            print(f"      ❌ Error processing {segment_path}: {str(e)}")
        
        # Rate limiting
        time.sleep(1)
    
    return results

def identify_speakers_in_text(text: str) -> List[str]:
    """Extract speaker identifiers from transcribed text.
    
    Args:
        text: Transcribed text potentially containing speaker labels
    
    Returns:
        List of unique speaker identifiers found
    """
    import re
    
    # Common speaker patterns
    patterns = [
        r'Speaker\s+(\d+):',
        r'SPEAKER\s+(\d+):',
        r'Person\s+(\d+):',
        r'Voice\s+(\d+):',
        r'Host:',
        r'Guest:',
        r'Interviewer:',
        r'Interviewee:'
    ]
    
    speakers = set()
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            if match.isdigit():
                speakers.add(f"Speaker {match}")
            else:
                speakers.add(match)
    
    # If no explicit labels found, check for dialogue patterns
    if not speakers:
        # Look for multiple sentences that might indicate conversation
        sentences = text.split('.')
        if len(sentences) > 3:
            # Assume at least one speaker if there's substantial content
            speakers.add("Speaker 1")
    
    return list(speakers)

def analyze_speaker_distribution(diarization_results: List[Dict]) -> Dict:
    """Analyze speaker distribution across the video.
    
    Args:
        diarization_results: Results from speaker diarization
    
    Returns:
        Speaker distribution analysis
    """
    speaker_stats = {}
    total_segments = len(diarization_results)
    
    # Count appearances
    for result in diarization_results:
        for speaker in result['speakers_detected']:
            if speaker not in speaker_stats:
                speaker_stats[speaker] = {
                    'appearances': 0,
                    'segments': [],
                    'total_time': 0
                }
            
            speaker_stats[speaker]['appearances'] += 1
            speaker_stats[speaker]['segments'].append(result['start_time'])
            speaker_stats[speaker]['total_time'] += 30  # Approximate segment duration
    
    # Calculate percentages
    for speaker in speaker_stats:
        speaker_stats[speaker]['percentage'] = (
            speaker_stats[speaker]['appearances'] / total_segments * 100
        )
    
    analysis = {
        'total_segments': total_segments,
        'speakers_found': len(speaker_stats),
        'speaker_stats': speaker_stats,
        'dominant_speaker': max(speaker_stats.keys(), key=lambda x: speaker_stats[x]['appearances']) if speaker_stats else None
    }
    
    return analysis

def diarize_video(video_path: str, output_dir: str = None) -> Dict:
    """Perform complete speaker diarization on a video file.
    
    Args:
        video_path: Path to video file
        output_dir: Directory for temporary files (default: video directory)
    
    Returns:
        Complete diarization results
    """
    if not os.path.exists(video_path):
        print(f"❌ Video file not found: {video_path}")
        return {}
    
    if output_dir is None:
        output_dir = os.path.dirname(video_path)
    
    video_name = Path(video_path).stem
    print(f"🎙️ Speaker Diarization: {video_name}")
    print("=" * 50)
    
    # Step 1: Extract audio segments
    audio_segments = extract_audio_segments(video_path, output_dir)
    
    if not audio_segments:
        print("❌ No audio segments extracted")
        return {}
    
    # Step 2: Analyze segments with Whisper
    diarization_results = identify_speakers_whisper(audio_segments)
    
    if not diarization_results:
        print("❌ No speaker analysis results")
        return {}
    
    # Step 3: Analyze speaker distribution
    analysis = analyze_speaker_distribution(diarization_results)
    
    # Step 4: Save results
    results = {
        'video_path': video_path,
        'video_name': video_name,
        'segments_analyzed': len(audio_segments),
        'segments_processed': len(diarization_results),
        'diarization_results': diarization_results,
        'analysis': analysis
    }
    
    output_path = os.path.join(output_dir, f"{video_name}_diarization.json")
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📊 Diarization Complete:")
    print(f"  Speakers found: {analysis['speakers_found']}")
    for speaker, stats in analysis['speaker_stats'].items():
        print(f"  {speaker}: {stats['appearances']} segments ({stats['percentage']:.1f}%)")
    print(f"  Results saved: {output_path}")
    
    # Cleanup audio segments
    cleanup_segments(audio_segments)
    
    return results

def cleanup_segments(audio_segments: List[str]):
    """Clean up temporary audio segment files.
    
    Args:
        audio_segments: List of audio segment file paths to delete
    """
    for segment_path in audio_segments:
        try:
            if os.path.exists(segment_path):
                os.remove(segment_path)
        except OSError:
            pass
    
    # Try to remove segment directories if empty
    for segment_path in audio_segments:
        try:
            segment_dir = os.path.dirname(segment_path)
            if os.path.exists(segment_dir) and not os.listdir(segment_dir):
                os.rmdir(segment_dir)
        except OSError:
            pass

def diarize_project(manifest_path: str) -> Dict:
    """Run speaker diarization on all clips in a project.
    
    Args:
        manifest_path: Path to project manifest.json
    
    Returns:
        Combined diarization results for all clips
    """
    if not os.path.exists(manifest_path):
        print(f"❌ Manifest not found: {manifest_path}")
        return {}
    
    with open(manifest_path) as f:
        manifest = json.load(f)
    
    project_folder = os.path.dirname(manifest_path)
    print(f"🎙️ Project Speaker Diarization")
    print(f"Project: {project_folder}")
    print(f"Clips: {manifest['total_clips']}")
    print("=" * 50)
    
    project_results = {
        'project_folder': project_folder,
        'manifest_path': manifest_path,
        'clip_results': {},
        'project_analysis': {}
    }
    
    # Process each clip
    for clip_info in manifest['clips']:
        clip_path = clip_info['path']
        clip_name = clip_info['filename']
        
        print(f"\n📹 Processing: {clip_name}")
        
        # Run diarization on clip
        clip_results = diarize_video(clip_path, project_folder)
        
        if clip_results:
            project_results['clip_results'][clip_name] = clip_results
        else:
            print(f"  ❌ Diarization failed for {clip_name}")
    
    # Analyze overall project speaker patterns
    all_speakers = set()
    total_segments = 0
    
    for clip_name, clip_data in project_results['clip_results'].items():
        analysis = clip_data.get('analysis', {})
        speaker_stats = analysis.get('speaker_stats', {})
        
        all_speakers.update(speaker_stats.keys())
        total_segments += analysis.get('total_segments', 0)
    
    project_results['project_analysis'] = {
        'total_clips_processed': len(project_results['clip_results']),
        'unique_speakers': list(all_speakers),
        'total_speakers': len(all_speakers),
        'total_segments_analyzed': total_segments
    }
    
    # Save project diarization results
    output_path = os.path.join(project_folder, "project_diarization.json")
    with open(output_path, 'w') as f:
        json.dump(project_results, f, indent=2)
    
    print(f"\n🎯 Project Diarization Complete:")
    print(f"  Clips processed: {len(project_results['clip_results'])}")
    print(f"  Unique speakers found: {len(all_speakers)}")
    print(f"  Speakers: {', '.join(all_speakers) if all_speakers else 'None detected'}")
    print(f"  Results saved: {output_path}")
    
    return project_results

def main():
    """Command line interface for speaker diarization."""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 speaker_diarization.py <video_file>     # Single video")
        print("  python3 speaker_diarization.py <manifest.json> # Entire project")
        sys.exit(1)
    
    input_path = sys.argv[1]
    
    if input_path.endswith('.json'):
        # Process entire project
        diarize_project(input_path)
    else:
        # Process single video
        diarize_video(input_path)

if __name__ == "__main__":
    main()