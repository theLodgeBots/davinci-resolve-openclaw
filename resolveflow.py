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
PROJECT_READY = False  # True once a project dir is loaded

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
            if any(root.startswith(os.path.join(directory, skip)) for skip in ['_ai-video-helper']):
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


def open_project(directory):
    """Initialize (or switch to) a project directory at runtime."""
    global PROJECT_DIR, DB_PATH, RF_DIR, THUMB_DIR, PROJECT_READY
    directory = os.path.abspath(directory)
    if not os.path.isdir(directory):
        return {'error': f'Not a directory: {directory}'}

    # Check it has video files
    has_video = False
    for root, _, files in os.walk(directory):
        for f in files:
            if os.path.splitext(f)[1].lower() in VIDEO_EXTS:
                has_video = True
                break
        if has_video:
            break
    if not has_video:
        return {'error': 'No video files found in this folder'}

    PROJECT_DIR = directory
    RF_DIR = os.path.join(PROJECT_DIR, '.resolveflow')
    DB_PATH = os.path.join(RF_DIR, 'project.db')
    THUMB_DIR = os.path.join(RF_DIR, 'thumbnails')
    os.makedirs(THUMB_DIR, exist_ok=True)

    db.init_db(DB_PATH)
    added = do_ingest()
    clips = db.get_all_clips(DB_PATH)
    threading.Thread(target=generate_all_thumbnails, daemon=True).start()
    PROJECT_READY = True
    print(f"Project opened: {PROJECT_DIR} ({len(clips)} clips, {added} new)")

    # Save to recents
    _save_recent(PROJECT_DIR)

    return {
        'path': PROJECT_DIR,
        'name': os.path.basename(PROJECT_DIR),
        'clip_count': len(clips),
        'added': added
    }


def _save_recent(directory):
    """Save directory to recents list."""
    recents_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.resolveflow_recents.json')
    recents = []
    try:
        with open(recents_file) as f:
            recents = json.load(f)
    except Exception:
        pass
    entry = {'path': directory, 'name': os.path.basename(directory), 'opened_at': time.time()}
    recents = [r for r in recents if r['path'] != directory]
    recents.insert(0, entry)
    recents = recents[:10]  # Keep last 10
    try:
        with open(recents_file, 'w') as f:
            json.dump(recents, f)
    except Exception:
        pass


def browse_dirs(path=None):
    """List subdirectories of a given path for the folder picker."""
    if path is None:
        path = os.path.expanduser('~')
    path = os.path.abspath(path)
    if not os.path.isdir(path):
        return {'error': 'Not a directory', 'path': path, 'dirs': []}

    dirs = []
    try:
        for entry in sorted(os.scandir(path), key=lambda e: e.name.lower()):
            if entry.name.startswith('.'):
                continue
            if entry.is_dir(follow_symlinks=False):
                # Check if it has video files (shallow check for speed)
                has_video = False
                try:
                    for sub_entry in os.scandir(entry.path):
                        if sub_entry.is_file() and os.path.splitext(sub_entry.name)[1].lower() in VIDEO_EXTS:
                            has_video = True
                            break
                        if sub_entry.is_dir(follow_symlinks=False):
                            # Check one level deeper
                            try:
                                for sub2 in os.scandir(sub_entry.path):
                                    if sub2.is_file() and os.path.splitext(sub2.name)[1].lower() in VIDEO_EXTS:
                                        has_video = True
                                        break
                            except PermissionError:
                                pass
                        if has_video:
                            break
                except PermissionError:
                    pass
                dirs.append({
                    'name': entry.name,
                    'path': entry.path,
                    'has_video': has_video
                })
    except PermissionError:
        return {'error': 'Permission denied', 'path': path, 'dirs': []}

    # Include parent
    parent = os.path.dirname(path)
    return {
        'path': path,
        'parent': parent if parent != path else None,
        'dirs': dirs
    }


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

    # Generate AI titles and summaries for newly transcribed clips
    _transcription_progress['current'] = 'Generating AI summaries...'
    try:
        _generate_clip_ai_metadata()
    except Exception as e:
        print(f"  AI metadata generation error: {e}", flush=True)

    return {
        'transcribed': saved,
        'total_clips': len(clips_to_process),
        'errors': _transcription_progress['errors']
    }


def _generate_clip_ai_metadata():
    """Generate AI title and summary for clips that have transcripts but no ai_title yet."""
    conn = db.get_db(DB_PATH)
    rows = conn.execute("""
        SELECT c.id, c.filename, c.duration_seconds, t.full_text
        FROM clips c
        JOIN transcripts t ON t.clip_id = c.id
        WHERE (c.ai_title IS NULL OR c.ai_title = '') AND t.full_text != ''
    """).fetchall()
    conn.close()

    if not rows:
        return

    # Batch all clips into one AI call for efficiency
    clip_texts = []
    for r in rows:
        dur = f"{r['duration_seconds']:.0f}s" if r['duration_seconds'] else '?'
        text_preview = (r['full_text'] or '')[:500]
        clip_texts.append(f"CLIP {r['id']} ({r['filename']}, {dur}):\n{text_preview}")

    prompt = f"""For each video clip below, provide:
1. A short descriptive title (3-8 words, no quotes)
2. A one-sentence summary of what's being discussed

Respond in JSON format: [{{"id": <clip_id>, "title": "...", "summary": "..."}}]

{chr(10).join(clip_texts)}"""

    try:
        result = ai_request(prompt, system="You are a video librarian. Be concise and descriptive.", temperature=0.3)
        # Parse JSON from response
        # Handle markdown code blocks
        result = result.strip()
        if result.startswith('```'):
            result = result.split('\n', 1)[1] if '\n' in result else result[3:]
            result = result.rsplit('```', 1)[0]
        items = json.loads(result)

        conn = db.get_db(DB_PATH)
        for item in items:
            conn.execute("UPDATE clips SET ai_title=?, ai_summary=? WHERE id=?",
                        (item.get('title', ''), item.get('summary', ''), item['id']))
        conn.commit()
        conn.close()
        print(f"  Generated AI metadata for {len(items)} clips", flush=True)
    except Exception as e:
        print(f"  AI metadata error: {e}", flush=True)


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


# Whisper removed — all transcription uses DaVinci Resolve's native API


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

    # Filter to selected clips if specified (handle "all" string shorthand)
    if clip_ids and clip_ids != "all" and clip_ids != ["all"]:
        clip_id_set = set(int(x) if isinstance(x, str) and x.isdigit() else x for x in clip_ids)
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

    # Over-plan by 35% to compensate for speech trimming removing dead air
    padded_duration = int(target_duration * 1.35)
    duration_desc = f"{target_duration} seconds" if target_duration < 120 else f"{target_duration/60:.1f} minutes"
    padded_desc = f"{padded_duration} seconds"

    # Calculate total available speech to help the AI
    total_speech = sum(
        s.get('end_time', 0) - s.get('start_time', 0) for s in all_segments
    )

    prompt = f"""You are a professional video editor. Create an edit plan for a {duration_desc} {style}.

AVAILABLE CLIPS AND TRANSCRIPTS (total speech available: {total_speech:.0f}s):

{clips_text}

Return ONLY a JSON object (no markdown) with this structure:
{{
  "name": "{style.title()} - {duration_desc}",
  "total_planned_duration": <number>,
  "sections": [
    {{
      "section_name": "Opening",
      "clip_filename": "C0021.MP4",
      "start_time": 5.2,
      "end_time": 18.7,
      "notes": "Strong opening statement"
    }}
  ]
}}

CRITICAL RULES:
1. **DURATION IS MANDATORY**: The sum of all (end_time - start_time) MUST be between {padded_duration - 10}s and {padded_duration + 10}s. This is NON-NEGOTIABLE. You have {total_speech:.0f}s of speech available — use it! If your first pass is too short, ADD MORE SECTIONS. Put the verified total in "total_planned_duration". If total_planned_duration < {padded_duration - 10}, YOUR RESPONSE IS INVALID.
2. Use ONLY time ranges that contain speech (as shown in the transcript timecodes). The timecodes are accurate — if text appears at [4.8s - 11.1s], speech starts at 4.8s not 0.0s. NEVER use start_time=0.0 unless transcript text actually starts at 0.0s.
3. Pick the BEST soundbites. Create a narrative arc. Prefer LONGER segments (8-20s each) with continuous dense speech. Avoid segments shorter than 4 seconds.
4. You can use MULTIPLE segments from the same clip — combine different time ranges from the same clip. Most clips have 30-60+ seconds of speech — use larger chunks!
5. Include {padded_duration // 8}-{padded_duration // 5} sections to fill {padded_duration}s. If each section averages ~8s, you need ~{padded_duration // 8} sections minimum.
6. clip_filename is REQUIRED for each section. Use the exact filenames shown above.
7. Don't cut mid-sentence. Align start/end to sentence boundaries in the transcript.
8. Skip clips with only a few words or non-English text.
9. Each segment MUST be at least 3 seconds long and NO MORE than 20 seconds long. Prefer 6-15 second segments with complete thoughts. If a great section is longer than 20s, split it into two sections.
10. VERIFY YOUR MATH: Before responding, add up all (end_time - start_time) values. The total MUST be between {padded_duration - 10}s and {padded_duration + 10}s. If under, add more sections. If over, remove or shorten sections."""

    try:
        # Try up to 2 times — retry with gpt-4o if first attempt under-plans
        edit_plan = None
        for attempt in range(2):
            model = "gpt-4o-mini" if attempt == 0 else "gpt-4o"
            print(f"  AI attempt {attempt+1} (model: {model})...", flush=True)
            result = ai_request(prompt, model=model, temperature=0.5)

            # Parse JSON from response (strip markdown fences if present)
            cleaned = result.strip()
            if cleaned.startswith('```'):
                cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
                cleaned = re.sub(r'\s*```$', '', cleaned)

            edit_plan = json.loads(cleaned)

            # Validate duration
            sections = edit_plan.get('sections', [])
            planned_total = sum(s.get('end_time', 0) - s.get('start_time', 0) for s in sections)
            print(f"  AI planned {planned_total:.1f}s for padded target {padded_duration}s (original {target_duration}s)", flush=True)

            if planned_total >= padded_duration * 0.75:
                break  # Good enough
            print(f"  ⚠️ Under-planned ({planned_total:.1f}s vs {padded_duration}s). {'Retrying with gpt-4o...' if attempt == 0 else 'Proceeding anyway.'}", flush=True)

        # Filter out micro-segments (< 2s) and cap long segments at 20s
        valid_sections = []
        for s in sections:
            dur = s.get('end_time', 0) - s.get('start_time', 0)
            if dur < 2.0:
                continue
            if dur > 20.0:
                # Trim to 20s from start
                s['end_time'] = s['start_time'] + 20.0
                print(f"  Capped segment '{s.get('section_name','')}' from {dur:.1f}s to 20.0s", flush=True)
            valid_sections.append(s)
        sections = valid_sections
        edit_plan['sections'] = sections

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
            # Always resolve by filename first (AI often confuses clip IDs)
            clip_id = None
            if sec.get('clip_filename'):
                clip_id = fname_to_id.get(sec['clip_filename'])
            if not clip_id:
                clip_id = sec.get('clip_id')
                # Verify this clip_id actually exists
                if clip_id and not any(c['id'] == clip_id for c in all_clips):
                    clip_id = None
            if not clip_id:
                print(f"  Skipping section '{sec.get('section_name')}': unknown clip", flush=True)
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


def _detect_speech_bounds(clip_path, start_time, end_time, noise_db=-30, min_silence=0.4):
    """Use ffmpeg silencedetect to find actual speech start/end within a time range.
    Returns (speech_start, speech_end) trimmed to actual speech, or None if detection fails."""
    duration = end_time - start_time
    if duration < 0.5:
        return None

    try:
        cmd = [
            'ffmpeg', '-ss', str(max(0, start_time - 0.1)), '-t', str(duration + 0.2),
            '-i', clip_path,
            '-af', f'silencedetect=noise={noise_db}dB:d={min_silence}',
            '-f', 'null', '-'
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        stderr = r.stderr

        # Parse silence periods
        silences = []
        import re as _re
        starts = _re.findall(r'silence_start:\s*([\d.]+)', stderr)
        ends = _re.findall(r'silence_end:\s*([\d.]+)', stderr)

        # Convert to absolute times (ffmpeg -ss offsets the timestamps)
        offset = max(0, start_time - 0.1)
        silence_ranges = []
        for i in range(len(starts)):
            s = float(starts[i]) + offset
            e = float(ends[i]) + offset if i < len(ends) else end_time
            silence_ranges.append((s, e))

        # Find first speech start (after any leading silence)
        speech_start = start_time
        for s, e in silence_ranges:
            if s <= start_time + 0.1:  # Leading silence
                speech_start = max(speech_start, e)
            else:
                break

        # Find last speech end (before any trailing silence)
        speech_end = end_time
        for s, e in reversed(silence_ranges):
            if e >= end_time - 0.1:  # Trailing silence
                speech_end = min(speech_end, s)
            else:
                break

        # Add small padding (0.15s) for natural feel
        speech_start = max(start_time, speech_start - 0.15)
        speech_end = min(end_time, speech_end + 0.15)

        # Only return if we actually trimmed something significant (>0.3s)
        if (speech_start - start_time > 0.3) or (end_time - speech_end > 0.3):
            if speech_end - speech_start > 0.5:  # Ensure remaining segment is meaningful
                return (round(speech_start, 2), round(speech_end, 2))

        return None
    except Exception:
        return None


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

        # Create new timeline with unique name (avoid appending to existing)
        tl_name = script['name']
        existing_names = set()
        for i in range(1, proj.GetTimelineCount() + 1):
            tl = proj.GetTimelineByIndex(i)
            if tl:
                existing_names.add(tl.GetName())

        final_name = tl_name
        counter = 2
        while final_name in existing_names:
            final_name = f"{tl_name} ({counter})"
            counter += 1

        pool.CreateEmptyTimeline(final_name)
        new_tl = proj.GetCurrentTimeline()
        if not new_tl or new_tl.GetName() != final_name:
            return {'error': 'Failed to create timeline'}

        # Get source FPS for each clip
        clip_fps = {}
        for rc in resolve_clips:
            try:
                props = rc.GetClipProperty()
                if props:
                    fname = props.get('File Name', '')
                    fps_val = props.get('FPS', '24')
                    try:
                        clip_fps[fname] = float(str(fps_val).replace(';',''))
                    except:
                        clip_fps[fname] = 24.0
            except:
                pass

        added = 0
        for seg in segments:
            fname = seg.get('filename')
            if not fname or fname not in fname_to_mpi:
                print(f"  Skip: {fname} not in media pool", flush=True)
                continue

            mpi = fname_to_mpi[fname]

            # Use ffmpeg silence detection to find actual speech boundaries
            start_time = seg['start_time']
            end_time = seg['end_time']
            clip_path = seg.get('full_path', '')
            if not clip_path:
                # Look up from DB
                clip_data = db.get_clip(DB_PATH, seg['clip_id'])
                clip_path = clip_data['full_path'] if clip_data else ''

            if clip_path and os.path.exists(clip_path):
                try:
                    tight = _detect_speech_bounds(clip_path, start_time, end_time)
                    if tight:
                        new_start, new_end = tight
                        if new_start != start_time or new_end != end_time:
                            print(f"  Speech trim {fname}: {start_time:.1f}-{end_time:.1f} → {new_start:.1f}-{new_end:.1f}", flush=True)
                        start_time = new_start
                        end_time = new_end
                except Exception as e:
                    print(f"  Speech detection failed for {fname}: {e}", flush=True)

            src_fps = clip_fps.get(fname, 24.0)
            start_frame = int(start_time * src_fps)
            end_frame = int(end_time * src_fps)

            print(f"  Adding {fname}: {start_time:.1f}s-{end_time:.1f}s (frames {start_frame}-{end_frame} @ {src_fps}fps)", flush=True)

            try:
                result = pool.AppendToTimeline([{
                    "mediaPoolItem": mpi,
                    "startFrame": start_frame,
                    "endFrame": end_frame
                }])
                if result:
                    added += 1
                else:
                    print(f"  Warning: AppendToTimeline returned falsy for {fname}", flush=True)
            except Exception as e:
                print(f"  Error adding {fname} to timeline: {e}", flush=True)

        # Transcribe the new timeline so subtitles appear in Resolve
        print(f"  Timeline created with {added} segments. Triggering transcription...", flush=True)
        try:
            new_tl.CreateSubtitlesFromAudio()
            print(f"  Transcription started for timeline '{final_name}'", flush=True)
        except Exception as e:
            print(f"  Could not start timeline transcription: {e}", flush=True)

        return {
            'success': True,
            'timeline_name': final_name,
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

        # Browse directories (no project needed)
        if path == '/api/browse' and method == 'GET':
            params = parse_qs(urlparse(self.path).query)
            browse_path = params.get('path', [None])[0]
            self.send_json(browse_dirs(browse_path))
            return

        # Open a project folder
        if path == '/api/project/open' and method == 'POST':
            body = self.read_body()
            folder = body.get('path', '')
            if not folder:
                self.send_json({'error': 'path is required'}, 400)
                return
            result = open_project(folder)
            if 'error' in result:
                self.send_json(result, 400)
            else:
                self.send_json(result)
            return

        # Recent projects list
        if path == '/api/projects/recent' and method == 'GET':
            recents_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.resolveflow_recents.json')
            try:
                with open(recents_file) as f:
                    self.send_json(json.load(f))
            except Exception:
                self.send_json([])
            return

        # All other API routes require an active project
        if not PROJECT_READY and path.startswith('/api/'):
            self.send_json({'error': 'no_project', 'message': 'No project open. Use /api/project/open first.'}, 400)
            return

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

        elif re.match(r'/api/clip/(\d+)$', path) and method == 'PUT':
            cid = int(re.match(r'/api/clip/(\d+)', path).group(1))
            body = self.read_body()
            conn = db.get_db(DB_PATH)
            if 'ai_title' in body:
                conn.execute("UPDATE clips SET ai_title=? WHERE id=?", (body['ai_title'], cid))
            if 'ai_summary' in body:
                conn.execute("UPDATE clips SET ai_summary=? WHERE id=?", (body['ai_summary'], cid))
            conn.commit()
            conn.close()
            self.send_json({'ok': True})

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

        elif re.match(r'/api/resolve/timeline-subtitles(?:/(.+))?$', path) and method == 'GET':
            # Read subtitles from a Resolve timeline. Optional timeline name param.
            m = re.match(r'/api/resolve/timeline-subtitles(?:/(.+))?$', path)
            tl_name = m.group(1) if m.group(1) else None
            resolve = get_resolve()
            if not resolve:
                self.send_json({'error': 'Resolve not connected'}, 503)
            else:
                try:
                    pm = resolve.GetProjectManager()
                    proj = pm.GetCurrentProject()
                    tl = None
                    if tl_name:
                        from urllib.parse import unquote
                        tl_name = unquote(tl_name)
                        for i in range(1, proj.GetTimelineCount() + 1):
                            t = proj.GetTimelineByIndex(i)
                            if t and t.GetName() == tl_name:
                                tl = t
                                break
                    else:
                        tl = proj.GetCurrentTimeline()
                    if not tl:
                        self.send_json({'error': f'Timeline not found: {tl_name or "current"}'}, 404)
                    else:
                        track_count = tl.GetTrackCount('subtitle')
                        subs = []
                        if track_count > 0:
                            items = tl.GetItemListInTrack('subtitle', 1)
                            if items:
                                fps = float(tl.GetSetting('timelineFrameRate') or 24)
                                for item in items:
                                    subs.append({
                                        'text': item.GetName(),
                                        'start_frame': item.GetStart(),
                                        'end_frame': item.GetEnd(),
                                        'duration_frames': item.GetDuration()
                                    })
                        full_text = ' '.join(s['text'] for s in subs)
                        self.send_json({
                            'timeline': tl.GetName(),
                            'subtitle_count': len(subs),
                            'subtitles': subs,
                            'full_text': full_text
                        })
                except Exception as e:
                    self.send_json({'error': str(e)}, 500)

        elif path == '/api/transcribe/progress' and method == 'GET':
            self.send_json(_transcription_progress)

        elif path == '/api/transcribe' and method == 'POST':
            # Always uses DaVinci Resolve's native transcription API
            def run():
                result = do_transcribe_resolve()
                print(f"Resolve transcription complete: {result}", flush=True)
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
    global PROJECT_DIR, DB_PATH, RF_DIR, THUMB_DIR, PROJECT_READY

    # Project dir is now optional — if provided, open it immediately
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if args:
        initial_dir = os.path.abspath(args[0])
        if not os.path.isdir(initial_dir):
            print(f"Error: {initial_dir} is not a directory")
            sys.exit(1)
        result = open_project(initial_dir)
        if 'error' in result:
            print(f"Error: {result['error']}")
            sys.exit(1)
        clips = db.get_all_clips(DB_PATH)
        total = sum(c.get('duration_seconds') or 0 for c in clips)
        print(f"ResolveFlow — {PROJECT_DIR}", flush=True)
        print(f"Clips: {len(clips)}, Duration: {total:.1f}s ({total/60:.1f}m)", flush=True)
    else:
        print("ResolveFlow — No project (select a folder in the UI)", flush=True)

    # Connect to Resolve in background to avoid blocking startup
    def _connect_bg():
        resolve = connect_resolve()
        if resolve:
            status = get_resolve_status()
            print(f"DaVinci Resolve: Connected — {status.get('project', '?')}", flush=True)
        else:
            print("DaVinci Resolve: Not connected (will retry on API calls)", flush=True)
    threading.Thread(target=_connect_bg, daemon=True).start()

    port = int(os.environ.get('PORT', '8080'))
    no_browser = '--no-browser' in sys.argv

    class ReusableHTTPServer(HTTPServer):
        allow_reuse_address = True
        def server_bind(self):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            super().server_bind()

    server = ReusableHTTPServer(('0.0.0.0', port), ResolveFlowHandler)
    print(f"Server: http://localhost:{port}", flush=True)

    if not no_browser:
        threading.Timer(1, lambda: webbrowser.open(f'http://localhost:{port}')).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()


if __name__ == '__main__':
    main()
