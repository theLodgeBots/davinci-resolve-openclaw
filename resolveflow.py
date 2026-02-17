#!/usr/bin/env python3
"""ResolveFlow v2 — AI video script editor with DaVinci Resolve transcription pipeline.
Run: python3 resolveflow.py [directory] [--no-browser]
"""

import sys, os, json, subprocess, threading, webbrowser, re, tempfile, time, socket
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path

import resolveflow_db as db

VIDEO_EXTS = {'.mp4', '.mov', '.mxf', '.mkv', '.avi'}
PROJECT_DIR = None
DB_PATH = None
RF_DIR = None
THUMB_DIR = None

# DaVinci Resolve connection
_resolve = None
_resolve_lock = threading.Lock()

# Transcription progress tracking
_transcription_progress = {'running': False, 'current': '', 'done': 0, 'total': 0, 'errors': []}

UI_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resolveflow_ui.html')


def detect_camera(relative_path, filename):
    """Detect camera from path and filename."""
    rel_lower = relative_path.lower()
    if rel_lower.startswith('sony/') or rel_lower.startswith('sony\\') or filename.upper().startswith('C'):
        return 'Sony'
    if rel_lower.startswith('dji/') or rel_lower.startswith('dji\\') or filename.upper().startswith('DJI'):
        return 'DJI'
    return 'Unknown'


def scan_videos(directory):
    clips = []
    for root, _, files in os.walk(directory):
        for f in files:
            if any(root.startswith(os.path.join(directory, skip)) for skip in ['.resolveflow']):
                continue
            ext = os.path.splitext(f)[1].lower()
            if ext not in VIDEO_EXTS:
                continue
            full = os.path.join(root, f)
            rel = os.path.relpath(full, directory)
            meta = probe_video(full)
            meta['filename'] = f
            meta['relative_path'] = rel
            meta['full_path'] = full
            meta['file_size_bytes'] = os.path.getsize(full)
            meta['camera'] = detect_camera(rel, f)
            clips.append(meta)
    return clips


def probe_video(path):
    meta = {'duration_seconds': None, 'resolution': None, 'codec': None, 'fps': None, 'has_audio': 1, 'camera': None}
    try:
        cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams', path]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        data = json.loads(r.stdout)
        fmt = data.get('format', {})
        meta['duration_seconds'] = float(fmt.get('duration', 0)) or None
        has_audio = False
        for s in data.get('streams', []):
            if s.get('codec_type') == 'video':
                meta['resolution'] = f"{s.get('width', '?')}x{s.get('height', '?')}"
                meta['codec'] = s.get('codec_name')
                r_fr = s.get('r_frame_rate', '0/1')
                if '/' in r_fr:
                    num, den = r_fr.split('/')
                    if int(den) > 0:
                        meta['fps'] = round(int(num) / int(den), 2)
            elif s.get('codec_type') == 'audio':
                has_audio = True
        meta['has_audio'] = 1 if has_audio else 0
    except Exception:
        pass
    return meta


def generate_thumbnail(clip_id, full_path, duration):
    os.makedirs(THUMB_DIR, exist_ok=True)
    out_path = os.path.join(THUMB_DIR, f"{clip_id}.jpg")
    if os.path.exists(out_path):
        return out_path
    seek = (duration or 10) * 0.25
    try:
        subprocess.run([
            'ffmpeg', '-y', '-ss', str(seek), '-i', full_path,
            '-frames:v', '1', '-q:v', '5', '-vf', 'scale=320:-1', out_path
        ], capture_output=True, timeout=30)
    except Exception:
        pass
    return out_path if os.path.exists(out_path) else None


def generate_all_thumbnails():
    clips = db.get_all_clips(DB_PATH)
    conn = db.get_db(DB_PATH)
    for c in clips:
        if c.get('thumbnail_path') and os.path.exists(c['thumbnail_path']):
            continue
        tp = generate_thumbnail(c['id'], c['full_path'], c.get('duration_seconds'))
        if tp:
            conn.execute("UPDATE clips SET thumbnail_path=? WHERE id=?", (tp, c['id']))
    conn.commit()
    conn.close()


# ─── DaVinci Resolve API ───────────────────────────────────────────────

def connect_resolve():
    global _resolve
    with _resolve_lock:
        try:
            sys.path.insert(0, '/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules')
            import DaVinciResolveScript as dvr
            _resolve = dvr.scriptapp('Resolve')
            if _resolve and _resolve.GetProductName():
                return _resolve
            _resolve = None
        except Exception:
            _resolve = None
    return _resolve


def get_resolve():
    global _resolve
    if _resolve:
        try:
            _resolve.GetProductName()
            return _resolve
        except Exception:
            _resolve = None
    return connect_resolve()


def get_resolve_status():
    resolve = get_resolve()
    if not resolve:
        return {'connected': False}
    try:
        pm = resolve.GetProjectManager()
        proj = pm.GetCurrentProject()
        tl = proj.GetCurrentTimeline() if proj else None
        return {
            'connected': True,
            'product': resolve.GetProductName(),
            'version': resolve.GetVersionString(),
            'project': proj.GetName() if proj else None,
            'timeline': tl.GetName() if tl else None,
            'fps': float(tl.GetSetting('timelineFrameRate')) if tl else None
        }
    except Exception as e:
        return {'connected': True, 'error': str(e)}


def get_resolve_media_pool_clips():
    resolve = get_resolve()
    if not resolve:
        return []
    try:
        pm = resolve.GetProjectManager()
        proj = pm.GetCurrentProject()
        pool = proj.GetMediaPool()
        root = pool.GetRootFolder()
        clips = []
        def walk(folder):
            for clip in (folder.GetClipList() or []):
                clips.append(clip)
            for sub in (folder.GetSubFolderList() or []):
                walk(sub)
        walk(root)
        return clips
    except Exception:
        return []


def do_transcribe_resolve():
    """Per-clip transcription: create temp timeline per clip, extract subtitles, save to DB."""
    global _transcription_progress
    _transcription_progress = {'running': True, 'current': '', 'done': 0, 'total': 0, 'errors': []}

    resolve = get_resolve()
    if not resolve:
        _transcription_progress['running'] = False
        return {'error': 'DaVinci Resolve not connected'}

    try:
        pm = resolve.GetProjectManager()
        proj = pm.GetCurrentProject()
        pool = proj.GetMediaPool()
        original_tl = proj.GetCurrentTimeline()
        original_tl_name = original_tl.GetName() if original_tl else None
    except Exception as e:
        _transcription_progress['running'] = False
        return {'error': f'Resolve API error: {e}'}

    # Get all media pool clips
    resolve_clips = get_resolve_media_pool_clips()
    if not resolve_clips:
        _transcription_progress['running'] = False
        return {'error': 'No clips in media pool'}

    # Build map: filename -> media pool clip and check transcription status
    clip_map = {}
    for rc in resolve_clips:
        try:
            props = rc.GetClipProperty()
            if not props:
                continue
            fname = props.get('File Name', '')
            if not fname:
                continue
            clip_map[fname] = {
                'media_pool_item': rc,
                'resolve_status': props.get('Transcription Status', ''),
            }
        except Exception:
            pass

    # Get DB clips that need transcription
    db_clips = db.get_all_clips(DB_PATH)
    clips_to_process = []
    for c in db_clips:
        existing = db.get_clip_transcript(DB_PATH, c['id'])
        if existing:
            continue  # Already in DB
        if c['filename'] in clip_map:
            clips_to_process.append(c)

    _transcription_progress['total'] = len(clips_to_process)

    if not clips_to_process:
        _transcription_progress['running'] = False
        return {'transcribed': 0, 'message': 'All clips already have transcripts in DB'}

    saved = 0
    for c in clips_to_process:
        fname = c['filename']
        _transcription_progress['current'] = fname
        print(f"[Transcribe] Processing {fname} ({_transcription_progress['done']+1}/{_transcription_progress['total']})")

        try:
            mpi = clip_map[fname]['media_pool_item']

            # Step 1: Create a temporary timeline with just this clip
            temp_name = f"_rf_temp_{fname}"
            temp_tl = pool.CreateTimelineFromClips(temp_name, [mpi])
            if not temp_tl:
                # Try alternate: create empty timeline, append clip
                pool.CreateEmptyTimeline(temp_name)
                temp_tl = proj.GetCurrentTimeline()
                if temp_tl:
                    pool.AppendToTimeline([{"mediaPoolItem": mpi}])
                else:
                    _transcription_progress['errors'].append(f"{fname}: failed to create temp timeline")
                    _transcription_progress['done'] += 1
                    continue

            # Step 2: Set as current timeline
            proj.SetCurrentTimeline(temp_tl)
            time.sleep(0.5)

            # Step 3: Get FPS from the timeline
            fps_str = temp_tl.GetSetting('timelineFrameRate')
            fps = float(fps_str) if fps_str else 24.0

            # Step 4: Create subtitles from audio
            try:
                result = temp_tl.CreateSubtitlesFromAudio()
                print(f"  CreateSubtitlesFromAudio returned: {result}")
            except Exception as e:
                print(f"  CreateSubtitlesFromAudio error: {e}")

            # Step 5: Wait for subtitle generation
            time.sleep(3)

            # Step 6: Read subtitle items
            subtitle_count = temp_tl.GetTrackCount('subtitle')
            segments = []
            for track_idx in range(1, (subtitle_count or 0) + 1):
                items = temp_tl.GetItemListInTrack('subtitle', track_idx) or []
                for item in items:
                    try:
                        text = item.GetName()
                        start_frame = item.GetStart()
                        end_frame = item.GetEnd()

                        # Get timeline start frame to compute clip-relative times
                        tl_start_str = temp_tl.GetStartFrame()
                        tl_start = int(tl_start_str) if tl_start_str else 0

                        start_sec = (start_frame - tl_start) / fps
                        end_sec = (end_frame - tl_start) / fps

                        # Clamp to non-negative
                        start_sec = max(0, start_sec)
                        end_sec = max(start_sec, end_sec)

                        if text and text.strip():
                            segments.append({
                                'text': text.strip(),
                                'start': round(start_sec, 3),
                                'end': round(end_sec, 3),
                            })
                    except Exception as e:
                        print(f"  Error reading subtitle item: {e}")

            # Step 7: Save to DB
            if segments:
                full_text = ' '.join(s['text'] for s in segments)
                db.save_transcript(
                    DB_PATH, c['id'], full_text, segments,
                    {'source': 'resolve', 'subtitle_count': len(segments), 'fps': fps},
                    duration=segments[-1]['end'] if segments else 0,
                    language='en', method='resolve'
                )
                saved += 1
                print(f"  Saved {len(segments)} segments for {fname}")
            else:
                # If Resolve has it as "Transcribed" but no subtitles appeared,
                # the clip might have no speech. Save empty transcript.
                resolve_status = clip_map[fname].get('resolve_status', '')
                if resolve_status == 'Transcribed':
                    db.save_transcript(
                        DB_PATH, c['id'], '', [],
                        {'source': 'resolve', 'subtitle_count': 0, 'note': 'no speech detected'},
                        duration=0, language='en', method='resolve'
                    )
                    saved += 1
                    print(f"  No speech detected in {fname}, saved empty transcript")
                else:
                    _transcription_progress['errors'].append(f"{fname}: no subtitles generated")

            # Step 8: Delete temp timeline
            try:
                pool.DeleteTimelines([temp_tl])
            except Exception:
                # Fallback: just leave it (will be cleaned up later)
                print(f"  Warning: could not delete temp timeline for {fname}")

        except Exception as e:
            print(f"  Error processing {fname}: {e}")
            _transcription_progress['errors'].append(f"{fname}: {str(e)}")

        _transcription_progress['done'] += 1

    # Restore original timeline
    if original_tl_name:
        try:
            # Find the original timeline by name
            tl_count = proj.GetTimelineCount()
            for i in range(1, tl_count + 1):
                tl = proj.GetTimelineByIndex(i)
                if tl and tl.GetName() == original_tl_name:
                    proj.SetCurrentTimeline(tl)
                    break
        except Exception:
            pass

    _transcription_progress['running'] = False
    return {
        'transcribed': saved,
        'total_clips': len(clips_to_process),
        'errors': _transcription_progress['errors']
    }


def do_ingest():
    clips = scan_videos(PROJECT_DIR)
    added = db.import_clips_from_scan(DB_PATH, clips)
    # Update camera field for existing clips that have camera=NULL
    conn = db.get_db(DB_PATH)
    rows = conn.execute("SELECT id, relative_path, filename FROM clips WHERE camera IS NULL OR camera = ''").fetchall()
    for row in rows:
        cam = detect_camera(row['relative_path'], row['filename'])
        conn.execute("UPDATE clips SET camera=? WHERE id=?", (cam, row['id']))
    conn.commit()
    conn.close()
    generate_all_thumbnails()
    return added


def do_transcribe_whisper():
    """Transcribe clips using OpenAI Whisper API."""
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        return {'error': 'OPENAI_API_KEY not set'}

    clip_ids = db.get_untranscribed_clip_ids(DB_PATH)
    results = []
    for cid in clip_ids:
        clip = db.get_clip(DB_PATH, cid)
        if not clip:
            continue
        tmp_wav = None
        try:
            tmp_wav = tempfile.mktemp(suffix='.wav')
            subprocess.run([
                'ffmpeg', '-y', '-i', clip['full_path'],
                '-ar', '16000', '-ac', '1', '-f', 'wav', tmp_wav
            ], capture_output=True, timeout=300)

            if not os.path.exists(tmp_wav):
                results.append({'clip_id': cid, 'error': 'audio extraction failed'})
                continue

            import urllib.request
            boundary = '----ResolveFlowBoundary'
            body = b''
            body += f'--{boundary}\r\nContent-Disposition: form-data; name="model"\r\n\r\nwhisper-1\r\n'.encode()
            body += f'--{boundary}\r\nContent-Disposition: form-data; name="response_format"\r\n\r\nverbose_json\r\n'.encode()
            body += f'--{boundary}\r\nContent-Disposition: form-data; name="timestamp_granularities[]"\r\n\r\nsegment\r\n'.encode()
            with open(tmp_wav, 'rb') as af:
                audio_data = af.read()
            body += f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="audio.wav"\r\nContent-Type: audio/wav\r\n\r\n'.encode()
            body += audio_data
            body += f'\r\n--{boundary}--\r\n'.encode()

            req = urllib.request.Request(
                'https://api.openai.com/v1/audio/transcriptions',
                data=body,
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': f'multipart/form-data; boundary={boundary}'
                }
            )
            resp = urllib.request.urlopen(req, timeout=600)
            raw = json.loads(resp.read())

            full_text = raw.get('text', '')
            segments = [{'text': s.get('text', ''), 'start': s.get('start', 0), 'end': s.get('end', 0)} for s in raw.get('segments', [])]

            db.save_transcript(DB_PATH, cid, full_text, segments, raw,
                             duration=raw.get('duration'), language=raw.get('language', 'en'), method='whisper')
            results.append({'clip_id': cid, 'status': 'ok', 'words': len(full_text.split())})
        except Exception as e:
            results.append({'clip_id': cid, 'error': str(e)})
        finally:
            if tmp_wav and os.path.exists(tmp_wav):
                os.unlink(tmp_wav)

    return {'transcribed': len([r for r in results if r.get('status') == 'ok']), 'results': results}


def ai_request(prompt, system="You are a professional video editor.", model="gpt-4o-mini", temperature=0.7):
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        raise Exception('OPENAI_API_KEY not set')
    import urllib.request
    data = json.dumps({
        'model': model,
        'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': prompt}
        ],
        'temperature': temperature
    }).encode()
    req = urllib.request.Request(
        'https://api.openai.com/v1/chat/completions',
        data=data,
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
    )
    resp = urllib.request.urlopen(req, timeout=120)
    result = json.loads(resp.read())
    return result['choices'][0]['message']['content']


def do_ai_auto_edit(target_duration=120, style="highlight reel", clip_ids=None, script_id=None):
    """Generate an AI edit plan from transcripts. If clip_ids provided, only use those clips."""
    # Collect all clips and transcripts
    all_clips = db.get_all_clips(DB_PATH)
    all_segments = db.get_full_transcript(DB_PATH)

    # Filter to selected clips if specified
    if clip_ids:
        clip_id_set = set(clip_ids)
        all_clips = [c for c in all_clips if c['id'] in clip_id_set]
        all_segments = [s for s in all_segments if s['clip_id'] in clip_id_set]

    if not all_segments:
        return {'error': 'No transcripts available. Transcribe clips first.'}

    # Group segments by clip
    clip_transcripts = {}
    for seg in all_segments:
        cid = seg['clip_id']
        if cid not in clip_transcripts:
            clip_transcripts[cid] = []
        clip_transcripts[cid].append(seg)

    # Build prompt with clip info and transcripts
    clip_sections = []
    fname_to_id = {}
    for c in all_clips:
        fname_to_id[c['filename']] = c['id']
        dur = c.get('duration_seconds', 0) or 0
        segs = clip_transcripts.get(c['id'], [])
        if not segs:
            continue
        transcript_lines = []
        for s in segs:
            st = s.get('start_time', 0)
            et = s.get('end_time', 0)
            transcript_lines.append(f"  [{st:.1f}s - {et:.1f}s] {s['text']}")
        clip_sections.append(
            f"Clip: {c['filename']} (ID: {c['id']}, Duration: {dur:.1f}s)\n" +
            "\n".join(transcript_lines)
        )

    clips_text = "\n\n".join(clip_sections)

    duration_desc = f"{target_duration} seconds" if target_duration < 120 else f"{target_duration/60:.1f} minutes"

    prompt = f"""You are a professional video editor. Given these transcripts from video clips, create an edit plan for a {duration_desc} {style}.

For each clip, I'm providing the filename, clip ID, duration, and full transcript with timecodes.

{clips_text}

Create a compelling edit plan. Return ONLY a JSON object (no markdown, no explanation) with this exact structure:
{{
  "name": "{style.title()} - {duration_desc}",
  "sections": [
    {{
      "section_name": "Opening",
      "clip_id": 1,
      "clip_filename": "C0021.MP4",
      "start_time": 5.2,
      "end_time": 18.7,
      "notes": "Strong opening statement"
    }}
  ]
}}

Rules:
- Pick the best soundbites and create a narrative arc
- Total duration of all sections should be approximately {target_duration} seconds
- start_time and end_time must be within the clip's actual transcript timecodes
- Use the clip_id values provided above
- Ensure smooth flow between sections
- Each section should have a descriptive section_name
- Include at least 3 sections"""

    try:
        result = ai_request(prompt, temperature=0.5)

        # Parse JSON from response (strip markdown fences if present)
        cleaned = result.strip()
        if cleaned.startswith('```'):
            cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
            cleaned = re.sub(r'\s*```$', '', cleaned)

        edit_plan = json.loads(cleaned)

        # Create script and segments in DB (or use existing script_id)
        script_name = edit_plan.get('name', f'{style.title()} - {duration_desc}')
        if script_id:
            # Clear existing segments and update the script
            conn = db.get_db(DB_PATH)
            conn.execute("DELETE FROM script_segments WHERE script_id=?", (script_id,))
            conn.execute("UPDATE scripts SET name=?, description=?, target_duration_seconds=?, ai_prompt=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                        (script_name, style, target_duration, prompt[:500], script_id))
            conn.commit()
            conn.close()
        else:
            script_id = db.create_script(DB_PATH, script_name, style, target_duration,
                                          prompt[:500])

        sections = edit_plan.get('sections', [])
        for i, sec in enumerate(sections):
            clip_id = sec.get('clip_id')
            # If clip_id not provided, try to find by filename
            if not clip_id and sec.get('clip_filename'):
                clip_id = fname_to_id.get(sec['clip_filename'])
            if not clip_id:
                continue

            db.add_script_segment(
                DB_PATH, script_id, clip_id,
                sec.get('start_time', 0), sec.get('end_time', 10),
                sec.get('section_name', f'Section {i+1}'),
                i, sec.get('notes', ''), 'cut'
            )

        return {
            'script_id': script_id,
            'script_name': script_name,
            'sections': sections,
            'section_count': len(sections)
        }

    except json.JSONDecodeError as e:
        return {'error': f'Failed to parse AI response: {e}', 'raw': result}
    except Exception as e:
        return {'error': str(e)}


def do_ai_refine(script_id, user_feedback):
    """Refine an existing script using AI — pick better segments, improve coherence."""
    script_data = db.get_script(DB_PATH, script_id)
    if not script_data:
        return {'error': 'Script not found'}

    script = script_data['script']
    segments = script_data['segments']
    
    # Get ALL available transcripts for the AI to pick from
    all_segments = db.get_full_transcript(DB_PATH)
    all_clips = db.get_all_clips(DB_PATH)
    
    # Build current script text
    current_script = []
    for seg in segments:
        current_script.append(f"Section: {seg.get('section_name','')}\n"
                              f"Clip: {seg.get('filename','')} [{seg.get('start_time',0):.1f}s → {seg.get('end_time',0):.1f}s]\n"
                              f"Text: {seg.get('transcript_text','')}")
    
    # Build full available transcript
    clip_transcripts = {}
    for s in all_segments:
        cid = s['clip_id']
        if cid not in clip_transcripts:
            clip_transcripts[cid] = []
        clip_transcripts[cid].append(s)
    
    available_text = []
    fname_to_id = {}
    for c in all_clips:
        fname_to_id[c['filename']] = c['id']
        segs = clip_transcripts.get(c['id'], [])
        if segs:
            lines = [f"  [{s['start_time']:.1f}s-{s['end_time']:.1f}s] {s['text']}" for s in segs]
            available_text.append(f"Clip: {c['filename']} (ID: {c['id']}, Duration: {c.get('duration_seconds',0):.1f}s)\n" + "\n".join(lines))
    
    target_dur = script.get('target_duration_seconds', 60)
    
    prompt = f"""You are a professional video editor refining a rough edit. The current script has coherence issues.

CURRENT SCRIPT (needs improvement):
{chr(10).join(current_script)}

FULL AVAILABLE TRANSCRIPTS (you can pick different/better segments from these):
{chr(10).join(available_text)}

USER FEEDBACK: {user_feedback or "Make this script more coherent and flow better. Pick segments that connect naturally."}

TARGET DURATION: ~{target_dur} seconds

RULES:
- You can ONLY use text that exists in the transcripts above — never invent dialog
- Pick segments that flow naturally together and tell a coherent story
- You can use different segments, adjust start/end times, reorder sections
- Each segment must reference a real clip_id and real timecodes from the transcripts
- Keep approximately the same target duration

Return ONLY a JSON object (no markdown) with this structure:
{{
  "sections": [
    {{
      "section_name": "Opening",
      "clip_id": 24,
      "clip_filename": "C0021.MP4",
      "start_time": 5.2,
      "end_time": 18.7,
      "notes": "Why this segment works here"
    }}
  ]
}}"""

    try:
        result = ai_request(prompt, temperature=0.5)
        cleaned = result.strip()
        if cleaned.startswith('```'):
            cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
            cleaned = re.sub(r'\s*```$', '', cleaned)
        
        edit_plan = json.loads(cleaned)
        sections = edit_plan.get('sections', [])
        
        # Build set of valid clip IDs
        valid_ids = {c['id'] for c in all_clips}
        
        # Clear existing segments and replace with refined ones
        conn = db.get_db(DB_PATH)
        conn.execute("DELETE FROM script_segments WHERE script_id=?", (script_id,))
        conn.execute("UPDATE scripts SET updated_at=CURRENT_TIMESTAMP WHERE id=?", (script_id,))
        conn.commit()
        conn.close()
        
        for i, sec in enumerate(sections):
            clip_id = sec.get('clip_id')
            # Always try filename lookup (more reliable than AI-guessed IDs)
            if sec.get('clip_filename'):
                fname_id = fname_to_id.get(sec['clip_filename'])
                if fname_id:
                    clip_id = fname_id
            if not clip_id or clip_id not in valid_ids:
                continue
            db.add_script_segment(DB_PATH, script_id, clip_id,
                sec.get('start_time', 0), sec.get('end_time', 10),
                sec.get('section_name', f'Section {i+1}'),
                i, sec.get('notes', ''), 'cut')
        
        # Return the updated script
        return db.get_script(DB_PATH, script_id)
    
    except json.JSONDecodeError as e:
        return {'error': f'Failed to parse AI response: {e}', 'raw': result}
    except Exception as e:
        return {'error': str(e)}


def do_export_to_resolve(script_id):
    """Push a script to DaVinci Resolve as a new timeline."""
    resolve = get_resolve()
    if not resolve:
        return {'error': 'DaVinci Resolve not connected'}

    script_data = db.get_script(DB_PATH, script_id)
    if not script_data:
        return {'error': 'Script not found'}

    script = script_data['script']
    segments = script_data['segments']
    if not segments:
        return {'error': 'Script has no segments'}

    try:
        pm = resolve.GetProjectManager()
        proj = pm.GetCurrentProject()
        pool = proj.GetMediaPool()

        # Get media pool clips for filename matching
        resolve_clips = get_resolve_media_pool_clips()
        fname_to_mpi = {}
        for rc in resolve_clips:
            try:
                props = rc.GetClipProperty()
                if props:
                    fname_to_mpi[props.get('File Name', '')] = rc
            except Exception:
                pass

        # Create new empty timeline
        tl_name = script['name']
        pool.CreateEmptyTimeline(tl_name)
        new_tl = proj.GetCurrentTimeline()
        if not new_tl:
            return {'error': 'Failed to create timeline'}

        fps_str = new_tl.GetSetting('timelineFrameRate')
        fps = float(fps_str) if fps_str else 24.0

        added = 0
        for seg in segments:
            fname = seg.get('filename')
            if not fname or fname not in fname_to_mpi:
                continue

            mpi = fname_to_mpi[fname]
            start_frame = int(seg['start_time'] * fps)
            end_frame = int(seg['end_time'] * fps)

            try:
                result = pool.AppendToTimeline([{
                    "mediaPoolItem": mpi,
                    "startFrame": start_frame,
                    "endFrame": end_frame
                }])
                if result:
                    added += 1
            except Exception as e:
                print(f"  Error adding {fname} to timeline: {e}")

        return {
            'success': True,
            'timeline_name': tl_name,
            'segments_added': added,
            'total_segments': len(segments)
        }

    except Exception as e:
        return {'error': f'Resolve export failed: {e}'}


# ─── HTTP Handler ──────────────────────────────────────────────────────

class ResolveFlowHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def send_json(self, data, status=200):
        body = json.dumps(data, default=str).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(body))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def read_body(self):
        length = int(self.headers.get('Content-Length', 0))
        if length:
            return json.loads(self.rfile.read(length))
        return {}

    def route(self, method):
        path = urlparse(self.path).path.rstrip('/')

        # Serve UI
        if method == 'GET' and path in ('', '/'):
            with open(UI_PATH, 'rb') as f:
                html = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(html))
            self.end_headers()
            self.wfile.write(html)
            return

        # Thumbnail
        m = re.match(r'/api/thumbnails/(\d+)', path)
        if m and method == 'GET':
            clip = db.get_clip(DB_PATH, int(m.group(1)))
            if clip and clip.get('thumbnail_path') and os.path.exists(clip['thumbnail_path']):
                with open(clip['thumbnail_path'], 'rb') as f:
                    img = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'image/jpeg')
                self.send_header('Content-Length', len(img))
                self.end_headers()
                self.wfile.write(img)
                return
            self.send_json({'error': 'no thumbnail'}, 404)
            return

        # --- API Routes ---
        if path == '/api/project' and method == 'GET':
            clips = db.get_all_clips(DB_PATH)
            total_dur = sum(c.get('duration_seconds') or 0 for c in clips)
            self.send_json({
                'path': PROJECT_DIR,
                'name': os.path.basename(PROJECT_DIR),
                'clip_count': len(clips),
                'total_duration': total_dur
            })

        elif path == '/api/clips' and method == 'GET':
            clips_data = db.get_all_clips(DB_PATH)
            # Enrich with transcript status and Resolve status
            transcribed_ids = set()
            conn = db.get_db(DB_PATH)
            for row in conn.execute("SELECT clip_id FROM transcripts").fetchall():
                transcribed_ids.add(row[0])
            conn.close()

            resolve = get_resolve()
            resolve_status_map = {}
            if resolve:
                try:
                    for rc in get_resolve_media_pool_clips():
                        try:
                            props = rc.GetClipProperty()
                            if props:
                                resolve_status_map[props.get('File Name', '')] = props.get('Transcription Status', '')
                        except Exception:
                            pass
                except Exception:
                    pass

            # Get transcript previews
            preview_map = {}
            conn2 = db.get_db(DB_PATH)
            for row in conn2.execute("SELECT clip_id, full_text FROM transcripts").fetchall():
                txt = row['full_text'] or ''
                preview_map[row['clip_id']] = txt[:120] if txt else ''
            conn2.close()

            for c in clips_data:
                c['has_transcript'] = c['id'] in transcribed_ids
                c['resolve_transcription_status'] = resolve_status_map.get(c['filename'], '')
                c['transcript_preview'] = preview_map.get(c['id'], '')
            self.send_json(clips_data)

        elif re.match(r'/api/clip/(\d+)$', path) and method == 'GET':
            cid = int(re.match(r'/api/clip/(\d+)', path).group(1))
            clip = db.get_clip(DB_PATH, cid)
            self.send_json(clip if clip else {'error': 'not found'}, 200 if clip else 404)

        elif path == '/api/ingest' and method == 'POST':
            added = do_ingest()
            clips = db.get_all_clips(DB_PATH)
            self.send_json({'added': added, 'total': len(clips)})

        elif path == '/api/transcript/full' and method == 'GET':
            self.send_json(db.get_full_transcript(DB_PATH))

        elif re.match(r'/api/transcript/(\d+)$', path) and method == 'GET':
            cid = int(re.match(r'/api/transcript/(\d+)', path).group(1))
            t = db.get_clip_transcript(DB_PATH, cid)
            self.send_json(t if t else {'error': 'no transcript'}, 200 if t else 404)

        elif path == '/api/resolve/status' and method == 'GET':
            self.send_json(get_resolve_status())

        elif path == '/api/transcribe/progress' and method == 'GET':
            self.send_json(_transcription_progress)

        elif path == '/api/transcribe' and method == 'POST':
            body = self.read_body() if self.headers.get('Content-Length') else {}
            use_whisper = body.get('method') == 'whisper'
            if use_whisper:
                def run():
                    result = do_transcribe_whisper()
                    print(f"Whisper transcription complete: {result}")
                threading.Thread(target=run, daemon=True).start()
                remaining = len(db.get_untranscribed_clip_ids(DB_PATH))
                self.send_json({'status': 'started', 'method': 'whisper', 'clips_to_transcribe': remaining})
            else:
                def run():
                    result = do_transcribe_resolve()
                    print(f"Resolve transcription complete: {result}")
                threading.Thread(target=run, daemon=True).start()
                self.send_json({'status': 'started', 'method': 'resolve'})

        elif path == '/api/scripts' and method == 'GET':
            self.send_json(db.get_all_scripts(DB_PATH))

        elif path == '/api/scripts' and method == 'POST':
            body = self.read_body()
            sid = db.create_script(DB_PATH, body.get('name', 'Untitled'),
                                   body.get('description'), body.get('target_duration'), body.get('ai_prompt'))
            self.send_json({'id': sid})

        elif re.match(r'/api/script/(\d+)$', path) and method == 'GET':
            sid = int(re.match(r'/api/script/(\d+)', path).group(1))
            s = db.get_script(DB_PATH, sid)
            self.send_json(s if s else {'error': 'not found'}, 200 if s else 404)

        elif re.match(r'/api/script/(\d+)$', path) and method == 'PUT':
            sid = int(re.match(r'/api/script/(\d+)', path).group(1))
            body = self.read_body()
            db.update_script(DB_PATH, sid, **body)
            self.send_json({'ok': True})

        elif re.match(r'/api/script/(\d+)$', path) and method == 'DELETE':
            sid = int(re.match(r'/api/script/(\d+)', path).group(1))
            db.delete_script(DB_PATH, sid)
            self.send_json({'ok': True})

        elif re.match(r'/api/script/(\d+)/update-segments$', path) and method == 'POST':
            sid = int(re.match(r'/api/script/(\d+)', path).group(1))
            body = self.read_body()
            segments = body.get('segments', [])
            conn = db.get_db(DB_PATH)
            conn.execute("DELETE FROM script_segments WHERE script_id=?", (sid,))
            for seg in segments:
                conn.execute(
                    """INSERT INTO script_segments (script_id, clip_id, start_time, end_time, section_name, order_index, notes, transition)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (sid, seg['clip_id'], seg['start_time'], seg['end_time'],
                     seg.get('section_name', ''), seg.get('order_index', 0),
                     seg.get('notes', ''), seg.get('transition', 'cut'))
                )
            conn.execute("UPDATE scripts SET updated_at=CURRENT_TIMESTAMP WHERE id=?", (sid,))
            conn.commit()
            conn.close()
            self.send_json({'ok': True, 'segments': len(segments)})

        elif re.match(r'/api/script/(\d+)/segments$', path) and method == 'POST':
            sid = int(re.match(r'/api/script/(\d+)', path).group(1))
            body = self.read_body()
            seg_id = db.add_script_segment(DB_PATH, sid, body['clip_id'],
                                            body['start_time'], body['end_time'],
                                            body.get('section_name'), body.get('order_index'),
                                            body.get('notes'), body.get('transition', 'cut'))
            self.send_json({'id': seg_id})

        elif re.match(r'/api/script/(\d+)/segment/(\d+)$', path) and method == 'PUT':
            m2 = re.match(r'/api/script/(\d+)/segment/(\d+)', path)
            body = self.read_body()
            db.update_script_segment(DB_PATH, int(m2.group(1)), int(m2.group(2)), **body)
            self.send_json({'ok': True})

        elif re.match(r'/api/script/(\d+)/segment/(\d+)$', path) and method == 'DELETE':
            m2 = re.match(r'/api/script/(\d+)/segment/(\d+)', path)
            db.delete_script_segment(DB_PATH, int(m2.group(1)), int(m2.group(2)))
            self.send_json({'ok': True})

        elif path == '/api/ai/brainstorm' and method == 'POST':
            body = self.read_body()
            transcript = db.get_full_transcript(DB_PATH)
            transcript_text = "\n".join(f"[{s['filename']} {s['start_time']:.1f}s] {s['text']}" for s in transcript)
            prompt = f"Here is the transcript of video clips:\n\n{transcript_text}\n\nUser request: {body.get('prompt', 'Suggest an edit')}"
            try:
                result = ai_request(prompt)
                self.send_json({'suggestions': result})
            except Exception as e:
                self.send_json({'error': str(e)})

        elif path == '/api/ai/refine' and method == 'POST':
            body = self.read_body()
            script_id = body.get('script_id')
            user_feedback = body.get('feedback', '')
            if not script_id:
                self.send_json({'error': 'script_id required'})
                return
            result = do_ai_refine(script_id, user_feedback)
            self.send_json(result)

        elif path == '/api/ai/auto-edit' and method == 'POST':
            body = self.read_body()
            target_duration = body.get('target_duration', 120)
            style = body.get('style', 'highlight reel')
            clip_ids = body.get('clip_ids')
            script_id = body.get('script_id')
            result = do_ai_auto_edit(target_duration, style, clip_ids=clip_ids, script_id=script_id)
            self.send_json(result)

        elif re.match(r'/api/export/resolve/(\d+)$', path) and method == 'POST':
            sid = int(re.match(r'/api/export/resolve/(\d+)', path).group(1))
            result = do_export_to_resolve(sid)
            self.send_json(result)

        elif re.match(r'/api/export/edl/(\d+)$', path) and method == 'POST':
            sid = int(re.match(r'/api/export/edl/(\d+)', path).group(1))
            edl = db.export_as_edl(DB_PATH, sid)
            if edl:
                body = edl.encode()
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.send_header('Content-Disposition', f'attachment; filename="script_{sid}.edl"')
                self.send_header('Content-Length', len(body))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_json({'error': 'script not found'}, 404)

        else:
            self.send_json({'error': 'not found'}, 404)

    def do_GET(self):
        self.route('GET')

    def do_POST(self):
        self.route('POST')

    def do_PUT(self):
        self.route('PUT')

    def do_DELETE(self):
        self.route('DELETE')

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,PUT,DELETE,OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()


def main():
    global PROJECT_DIR, DB_PATH, RF_DIR, THUMB_DIR

    PROJECT_DIR = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else '.')
    if not os.path.isdir(PROJECT_DIR):
        print(f"Error: {PROJECT_DIR} is not a directory")
        sys.exit(1)

    RF_DIR = os.path.join(PROJECT_DIR, '.resolveflow')
    DB_PATH = os.path.join(RF_DIR, 'project.db')
    THUMB_DIR = os.path.join(RF_DIR, 'thumbnails')
    os.makedirs(THUMB_DIR, exist_ok=True)

    print(f"ResolveFlow v2 — {PROJECT_DIR}")
    print(f"Database: {DB_PATH}")

    db.init_db(DB_PATH)

    added = do_ingest()
    clips = db.get_all_clips(DB_PATH)
    print(f"Clips: {len(clips)} ({added} new)")
    total = sum(c.get('duration_seconds') or 0 for c in clips)
    print(f"Total duration: {total:.1f}s ({total/60:.1f}m)")

    resolve = connect_resolve()
    if resolve:
        status = get_resolve_status()
        print(f"DaVinci Resolve: Connected — {status.get('project', '?')}")
    else:
        print("DaVinci Resolve: Not connected (will retry on API calls)")

    port = int(os.environ.get('PORT', '8080'))
    no_browser = '--no-browser' in sys.argv

    class ReusableHTTPServer(HTTPServer):
        allow_reuse_address = True
        def server_bind(self):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            super().server_bind()

    server = ReusableHTTPServer(('0.0.0.0', port), ResolveFlowHandler)
    print(f"Server: http://localhost:{port}")

    if not no_browser:
        threading.Timer(1, lambda: webbrowser.open(f'http://localhost:{port}')).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()


if __name__ == '__main__':
    main()
