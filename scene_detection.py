#!/usr/bin/env python3
"""Scene detection and shot classification for video clips."""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import tempfile
import base64
import requests

# OpenAI API for vision analysis
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"

def extract_frame(video_path: str, timestamp: float = 5.0) -> Optional[str]:
    """Extract a single frame from video at specified timestamp for analysis.
    
    Args:
        video_path: Path to video file
        timestamp: Time in seconds to extract frame (default: 5 seconds)
    
    Returns:
        Base64 encoded image data, or None if extraction failed
    """
    try:
        # Create temp file for frame
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
            temp_path = temp_file.name
        
        # Extract frame using ffmpeg
        cmd = [
            'ffmpeg', '-i', video_path,
            '-ss', str(timestamp),
            '-vframes', '1',
            '-q:v', '2',  # High quality
            '-y',  # Overwrite output file
            temp_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"❌ ffmpeg failed for {video_path}: {result.stderr}")
            return None
        
        # Read and encode image
        with open(temp_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')
        
        # Cleanup
        os.unlink(temp_path)
        
        return image_data
        
    except Exception as e:
        print(f"❌ Frame extraction failed for {video_path}: {e}")
        return None

def classify_shot_type(image_data: str) -> Dict:
    """Classify shot type using OpenAI Vision API.
    
    Args:
        image_data: Base64 encoded image
    
    Returns:
        Dict with shot classification results
    """
    if not OPENAI_API_KEY:
        return {"error": "OpenAI API key not found"}
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }
    
    prompt = """Analyze this video frame and classify the shot type. Consider:

SHOT SCALE:
- Extreme Wide Shot (EWS): Shows large landscape/environment, subjects very small
- Wide Shot (WS): Shows full subject with surrounding environment
- Medium Wide Shot (MWS): Shows subject from waist up with some environment  
- Medium Shot (MS): Shows subject from waist up, focused on person
- Medium Close-Up (MCU): Shows subject from chest up
- Close-Up (CU): Shows subject's face/head, minimal background
- Extreme Close-Up (ECU): Shows details like eyes, hands, objects

SHOT MOVEMENT:
- Static: No camera movement
- Pan: Horizontal camera movement
- Tilt: Vertical camera movement  
- Zoom: Camera zoom in/out
- Tracking: Camera follows subject

SUBJECT FOCUS:
- Person: Human subject(s) in frame
- Object: Product, item, or specific object focus
- Environment: Landscape, room, or location focus
- Action: Movement or activity focus

Return ONLY a JSON object with this structure:
{
  "shot_scale": "WS|MS|CU|etc",
  "shot_movement": "static|pan|tilt|zoom|tracking",
  "subject_focus": "person|object|environment|action",
  "subject_count": number,
  "confidence": 0.0-1.0,
  "description": "Brief description of what's in the frame"
}"""
    
    payload = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_data}",
                            "detail": "high"
                        }
                    }
                ]
            }
        ],
        "max_tokens": 300,
        "temperature": 0.1
    }
    
    try:
        response = requests.post(OPENAI_API_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        content = result['choices'][0]['message']['content'].strip()
        
        # Parse JSON response
        if content.startswith('```json'):
            content = content.split('```json')[1].split('```')[0].strip()
        elif content.startswith('```'):
            content = content.split('```')[1].strip()
            
        return json.loads(content)
        
    except json.JSONDecodeError as e:
        return {"error": f"Failed to parse JSON response: {e}", "raw_response": content}
    except Exception as e:
        return {"error": f"API request failed: {e}"}

def analyze_clip_scenes(video_path: str, duration: float) -> Dict:
    """Analyze a video clip for scene classification.
    
    Args:
        video_path: Path to video file
        duration: Duration of clip in seconds
    
    Returns:
        Dict with scene analysis results
    """
    print(f"🎯 Analyzing scenes in {os.path.basename(video_path)}")
    
    # Extract frames at different timestamps for analysis
    # For clips under 30 seconds, analyze beginning and middle
    # For longer clips, analyze beginning, middle, end
    timestamps = []
    if duration <= 30:
        timestamps = [min(3.0, duration * 0.2), min(duration * 0.6, duration - 2)]
    else:
        timestamps = [5.0, duration * 0.5, max(duration - 10, duration * 0.8)]
    
    # Remove duplicates and ensure timestamps are within duration
    timestamps = list(set(t for t in timestamps if 0 < t < duration))
    
    if not timestamps:
        return {"error": "Could not determine valid timestamps for analysis"}
    
    frame_analyses = []
    
    for i, timestamp in enumerate(timestamps):
        print(f"   📷 Extracting frame at {timestamp:.1f}s...")
        image_data = extract_frame(video_path, timestamp)
        
        if not image_data:
            continue
            
        print(f"   🤖 Analyzing frame {i+1}/{len(timestamps)}...")
        classification = classify_shot_type(image_data)
        
        if "error" not in classification:
            classification["timestamp"] = timestamp
            frame_analyses.append(classification)
            print(f"   ✅ {classification['shot_scale']} - {classification['description']}")
        else:
            print(f"   ❌ Classification failed: {classification['error']}")
    
    if not frame_analyses:
        return {"error": "No frames successfully analyzed"}
    
    # Determine overall clip characteristics
    # Use most confident classification, or aggregate if similar
    best_analysis = max(frame_analyses, key=lambda x: x.get('confidence', 0))
    
    # Count shot scales to determine consistency
    shot_scales = [a['shot_scale'] for a in frame_analyses]
    movements = [a['shot_movement'] for a in frame_analyses]
    subjects = [a['subject_focus'] for a in frame_analyses]
    
    return {
        "overall_classification": best_analysis,
        "frame_analyses": frame_analyses,
        "consistency": {
            "shot_scales": list(set(shot_scales)),
            "movements": list(set(movements)),
            "subjects": list(set(subjects)),
            "is_consistent": len(set(shot_scales)) == 1
        },
        "timestamps_analyzed": timestamps
    }

def analyze_project_scenes(manifest_path: str) -> Dict:
    """Analyze all clips in a project for scene classification.
    
    Args:
        manifest_path: Path to manifest.json file
    
    Returns:
        Dict with all scene analysis results
    """
    if not os.path.exists(manifest_path):
        return {"error": f"Manifest not found: {manifest_path}"}
    
    with open(manifest_path, 'r') as f:
        manifest = json.load(f)
    
    results = {
        "project_path": os.path.dirname(manifest_path),
        "total_clips": len(manifest['clips']),
        "analyzed_clips": 0,
        "failed_clips": 0,
        "scene_summary": {},
        "clips": {}
    }
    
    print(f"🎬 Starting scene analysis for {results['total_clips']} clips...")
    
    for clip in manifest['clips']:
        filename = clip['filename']
        # Use full path from manifest instead of constructing
        video_path = clip.get('path', os.path.join(results["project_path"], filename))
        
        if not os.path.exists(video_path):
            print(f"❌ Clip not found: {filename}")
            results["failed_clips"] += 1
            results["clips"][filename] = {"error": "File not found"}
            continue
        
        try:
            analysis = analyze_clip_scenes(video_path, clip['duration_seconds'])
            results["clips"][filename] = analysis
            
            if "error" not in analysis:
                results["analyzed_clips"] += 1
            else:
                results["failed_clips"] += 1
                
        except Exception as e:
            print(f"❌ Failed to analyze {filename}: {e}")
            results["failed_clips"] += 1
            results["clips"][filename] = {"error": str(e)}
    
    # Generate scene summary
    shot_scales = []
    movements = []
    subjects = []
    
    for filename, analysis in results["clips"].items():
        if "error" not in analysis and "overall_classification" in analysis:
            classification = analysis["overall_classification"]
            shot_scales.append(classification.get("shot_scale", "unknown"))
            movements.append(classification.get("shot_movement", "unknown"))
            subjects.append(classification.get("subject_focus", "unknown"))
    
    from collections import Counter
    
    results["scene_summary"] = {
        "shot_scale_distribution": dict(Counter(shot_scales)),
        "movement_distribution": dict(Counter(movements)),
        "subject_distribution": dict(Counter(subjects)),
        "total_analyzed": results["analyzed_clips"],
        "success_rate": f"{results['analyzed_clips']}/{results['total_clips']} ({results['analyzed_clips']/results['total_clips']*100:.1f}%)"
    }
    
    return results

def save_scene_analysis(analysis: Dict, output_path: str):
    """Save scene analysis results to JSON file."""
    try:
        with open(output_path, 'w') as f:
            json.dump(analysis, f, indent=2)
        print(f"✅ Scene analysis saved: {output_path}")
    except Exception as e:
        print(f"❌ Failed to save analysis: {e}")

def main():
    """Command line interface for scene detection."""
    if len(sys.argv) != 2:
        print("Usage: python3 scene_detection.py /path/to/manifest.json")
        sys.exit(1)
    
    manifest_path = sys.argv[1]
    
    if not OPENAI_API_KEY:
        print("❌ OpenAI API key not found. Set OPENAI_API_KEY environment variable.")
        sys.exit(1)
    
    print("🎬 DaVinci Resolve Scene Detection")
    print("=" * 40)
    
    # Run analysis
    analysis = analyze_project_scenes(manifest_path)
    
    # Save results
    output_path = os.path.join(os.path.dirname(manifest_path), "scene_analysis.json")
    save_scene_analysis(analysis, output_path)
    
    # Print summary
    print("\n📊 Scene Analysis Summary:")
    summary = analysis.get("scene_summary", {})
    print(f"   Success rate: {summary.get('success_rate', 'N/A')}")
    print(f"   Shot scales: {summary.get('shot_scale_distribution', {})}")
    print(f"   Movements: {summary.get('movement_distribution', {})}")
    print(f"   Subjects: {summary.get('subject_distribution', {})}")
    
    if analysis["failed_clips"] > 0:
        print(f"\n⚠️  {analysis['failed_clips']} clips failed analysis")
    
    print(f"\n✅ Complete! Scene analysis saved to: {output_path}")

if __name__ == "__main__":
    main()