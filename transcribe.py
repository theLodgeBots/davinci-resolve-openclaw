#!/usr/bin/env python3
"""Extract audio from video files and transcribe with Whisper."""

import json
import os
import subprocess
import sys
from pathlib import Path


def extract_audio(video_path: str, output_dir: str) -> str:
    """Extract audio from video file as WAV."""
    os.makedirs(output_dir, exist_ok=True)
    stem = Path(video_path).stem
    audio_path = os.path.join(output_dir, f"{stem}.wav")
    
    if os.path.exists(audio_path):
        print(f"  Audio already extracted: {stem}.wav")
        return audio_path
    
    print(f"  Extracting audio: {stem}...")
    result = subprocess.run(
        [
            "ffmpeg", "-i", video_path,
            "-vn",  # no video
            "-acodec", "pcm_s16le",  # WAV format
            "-ar", "16000",  # 16kHz for Whisper
            "-ac", "1",  # mono
            "-y",  # overwrite
            audio_path
        ],
        capture_output=True, text=True, timeout=300
    )
    
    if result.returncode != 0:
        print(f"  ERROR extracting audio: {result.stderr[:200]}")
        return None
    
    return audio_path


def transcribe_whisper_api(audio_path: str, api_key: str = None) -> dict:
    """Transcribe audio using OpenAI Whisper API."""
    api_key = api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: No OpenAI API key. Set OPENAI_API_KEY env var.")
        return None
    
    import requests
    
    # Check file size — Whisper API limit is 25MB
    file_size = os.path.getsize(audio_path)
    if file_size > 25 * 1024 * 1024:
        print(f"  WARNING: File too large for Whisper API ({file_size // (1024*1024)}MB). Splitting...")
        return transcribe_chunked(audio_path, api_key)
    
    print(f"  Transcribing: {Path(audio_path).name}...")
    
    with open(audio_path, "rb") as f:
        response = requests.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": f},
            data={
                "model": "whisper-1",
                "response_format": "verbose_json",
                "timestamp_granularities[]": "word",
            },
        )
    
    if response.status_code != 200:
        print(f"  ERROR: Whisper API returned {response.status_code}: {response.text[:200]}")
        return None
    
    return response.json()


def transcribe_chunked(audio_path: str, api_key: str, chunk_seconds: int = 600) -> dict:
    """Split long audio and transcribe in chunks."""
    import tempfile
    
    # Get duration
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", audio_path],
        capture_output=True, text=True
    )
    duration = float(result.stdout.strip())
    
    all_segments = []
    all_words = []
    full_text = []
    offset = 0
    chunk_idx = 0
    
    with tempfile.TemporaryDirectory() as tmpdir:
        while offset < duration:
            chunk_path = os.path.join(tmpdir, f"chunk_{chunk_idx}.wav")
            subprocess.run(
                [
                    "ffmpeg", "-i", audio_path,
                    "-ss", str(offset),
                    "-t", str(chunk_seconds),
                    "-y", chunk_path
                ],
                capture_output=True, timeout=60
            )
            
            result = transcribe_whisper_api(chunk_path, api_key)
            if result:
                full_text.append(result.get("text", ""))
                for seg in result.get("segments", []):
                    seg["start"] += offset
                    seg["end"] += offset
                    all_segments.append(seg)
                for word in result.get("words", []):
                    word["start"] += offset
                    word["end"] += offset
                    all_words.append(word)
            
            offset += chunk_seconds
            chunk_idx += 1
    
    return {
        "text": " ".join(full_text),
        "segments": all_segments,
        "words": all_words,
    }


def transcribe_project(manifest_path: str, output_dir: str = None):
    """Transcribe all video clips in a project manifest."""
    with open(manifest_path) as f:
        manifest = json.load(f)
    
    project_folder = manifest["project_folder"]
    output_dir = output_dir or os.path.join(project_folder, "_transcripts")
    audio_dir = os.path.join(project_folder, "_audio")
    os.makedirs(output_dir, exist_ok=True)
    
    transcripts = {}
    
    for clip in manifest["clips"]:
        # Skip non-video or clips without audio
        if "audio" not in clip:
            continue
        
        stem = Path(clip["filename"]).stem
        transcript_path = os.path.join(output_dir, f"{stem}.json")
        
        # Skip if already transcribed
        if os.path.exists(transcript_path):
            print(f"  Already transcribed: {stem}")
            with open(transcript_path) as f:
                transcripts[clip["filename"]] = json.load(f)
            continue
        
        # Extract audio
        audio_path = extract_audio(clip["path"], audio_dir)
        if not audio_path:
            continue
        
        # Transcribe
        result = transcribe_whisper_api(audio_path)
        if result:
            # Save individual transcript
            with open(transcript_path, "w") as f:
                json.dump(result, f, indent=2)
            transcripts[clip["filename"]] = result
            print(f"  ✓ {stem}: {len(result.get('text', ''))} chars")
    
    # Save combined transcript summary
    summary_path = os.path.join(output_dir, "_summary.json")
    summary = {
        "project": project_folder,
        "clips_transcribed": len(transcripts),
        "transcripts": {
            name: {
                "text": t.get("text", ""),
                "duration": t.get("duration", 0),
                "word_count": len(t.get("text", "").split()),
            }
            for name, t in transcripts.items()
        }
    }
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    
    print(f"\nTranscribed {len(transcripts)} clips → {output_dir}")
    return transcripts


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python transcribe.py <manifest.json> [output_dir]")
        sys.exit(1)
    
    manifest_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    transcribe_project(manifest_path, output_dir)
