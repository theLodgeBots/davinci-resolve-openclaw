#!/usr/bin/env python3
"""ResolveFlow — AI video script editor. Run: python3 resolveflow.py [directory]"""

import sys, os, json, subprocess, threading, webbrowser, re, tempfile, shutil
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path

import resolveflow_db as db

VIDEO_EXTS = {'.mp4', '.mov', '.mxf', '.mkv', '.avi'}
PROJECT_DIR = None
DB_PATH = None
RF_DIR = None
THUMB_DIR = None
UI_HTML = None

# Load UI HTML once
UI_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resolveflow_ui.html')


def scan_videos(directory):
    """Scan directory recursively for video files, return metadata list."""
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
            clips.append(meta)
    return clips


def probe_video(path):
    """Use ffprobe to get video metadata."""
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
                # Parse fps
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
    """Generate thumbnail for a clip."""
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


def do_ingest():
    """Scan and import clips, generate thumbnails."""
    clips = scan_videos(PROJECT_DIR)
    added = db.import_clips_from_scan(DB_PATH, clips)
    generate_all_thumbnails()
    return added


def do_transcribe():
    """Transcribe all untranscribed clips using OpenAI Whisper API."""
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        return {'error': 'OPENAI_API_KEY not set'}

    clip_ids = db.get_untranscribed_clip_ids(DB_PATH)
    results = []
    for cid in clip_ids:
        clip = db.get_clip(DB_PATH, cid)
        if not clip:
            continue
        try:
            # Extract audio
            tmp_wav = tempfile.mktemp(suffix='.wav')
            subprocess.run([
                'ffmpeg', '-y', '-i', clip['full_path'],
                '-ar', '16000', '-ac', '1', '-f', 'wav', tmp_wav
            ], capture_output=True, timeout=300)

            if not os.path.exists(tmp_wav):
                results.append({'clip_id': cid, 'error': 'audio extraction failed'})
                continue

            # Send to Whisper API
            import urllib.request
            boundary = '----ResolveFlowBoundary'
            body = b''
            # Add model field
            body += f'--{boundary}\r\nContent-Disposition: form-data; name="model"\r\n\r\nwhisper-1\r\n'.encode()
            # Add response_format
            body += f'--{boundary}\r\nContent-Disposition: form-data; name="response_format"\r\n\r\nverbose_json\r\n'.encode()
            # Add timestamp_granularities
            body += f'--{boundary}\r\nContent-Disposition: form-data; name="timestamp_granularities[]"\r\n\r\nword\r\n'.encode()
            body += f'--{boundary}\r\nContent-Disposition: form-data; name="timestamp_granularities[]"\r\n\r\nsegment\r\n'.encode()
            # Add file
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
            segments = []
            for seg in raw.get('segments', []):
                segments.append({
                    'text': seg.get('text', ''),
                    'start': seg.get('start', 0),
                    'end': seg.get('end', 0),
                    'confidence': seg.get('avg_logprob')
                })

            db.save_transcript(DB_PATH, cid, full_text, segments, raw,
                             duration=raw.get('duration'), language=raw.get('language', 'en'))
            results.append({'clip_id': cid, 'status': 'ok', 'words': len(full_text.split())})

            os.unlink(tmp_wav)
        except Exception as e:
            results.append({'clip_id': cid, 'error': str(e)})
            if os.path.exists(tmp_wav):
                os.unlink(tmp_wav)

    return {'transcribed': len([r for r in results if r.get('status') == 'ok']), 'results': results}


def ai_request(prompt, system="You are a video editor assistant."):
    """Make a request to OpenAI chat API."""
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        return {'error': 'OPENAI_API_KEY not set'}
    import urllib.request
    data = json.dumps({
        'model': 'gpt-4o-mini',
        'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': prompt}
        ],
        'temperature': 0.7
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


class ResolveFlowHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Quiet

    def send_json(self, data, status=200):
        body = json.dumps(data, default=str).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(body))
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

        # Thumbnail serving
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

        # API routes
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
            self.send_json(db.get_all_clips(DB_PATH))
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
        elif path == '/api/transcribe' and method == 'POST':
            def run():
                result = do_transcribe()
                print(f"Transcription complete: {result}")
            threading.Thread(target=run, daemon=True).start()
            remaining = len(db.get_untranscribed_clip_ids(DB_PATH))
            self.send_json({'status': 'started', 'clips_to_transcribe': remaining})
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
        elif re.match(r'/api/script/(\d+)/segments$', path) and method == 'POST':
            sid = int(re.match(r'/api/script/(\d+)', path).group(1))
            body = self.read_body()
            seg_id = db.add_script_segment(DB_PATH, sid, body['clip_id'],
                                            body['start_time'], body['end_time'],
                                            body.get('section_name'), body.get('order_index'),
                                            body.get('notes'), body.get('transition', 'cut'))
            self.send_json({'id': seg_id})
        elif re.match(r'/api/script/(\d+)/segment/(\d+)$', path) and method == 'PUT':
            m = re.match(r'/api/script/(\d+)/segment/(\d+)', path)
            body = self.read_body()
            db.update_script_segment(DB_PATH, int(m.group(1)), int(m.group(2)), **body)
            self.send_json({'ok': True})
        elif re.match(r'/api/script/(\d+)/segment/(\d+)$', path) and method == 'DELETE':
            m = re.match(r'/api/script/(\d+)/segment/(\d+)', path)
            db.delete_script_segment(DB_PATH, int(m.group(1)), int(m.group(2)))
            self.send_json({'ok': True})
        elif path == '/api/ai/brainstorm' and method == 'POST':
            body = self.read_body()
            transcript = db.get_full_transcript(DB_PATH)
            transcript_text = "\n".join(f"[{s['filename']} {s['start_time']:.1f}s] {s['text']}" for s in transcript)
            prompt = f"Here is the transcript of video clips:\n\n{transcript_text}\n\nUser request: {body.get('prompt', 'Suggest an edit')}"
            result = ai_request(prompt)
            self.send_json({'suggestions': result})
        elif path == '/api/ai/auto-edit' and method == 'POST':
            body = self.read_body()
            transcript = db.get_full_transcript(DB_PATH)
            clips = db.get_all_clips(DB_PATH)
            clip_info = "\n".join(f"Clip ID {c['id']}: {c['filename']} ({c.get('duration_seconds',0):.1f}s)" for c in clips)
            transcript_text = "\n".join(f"[Clip {s['clip_id']} {s['start_time']:.1f}-{s['end_time']:.1f}s] {s['text']}" for s in transcript)
            prompt = f"""Here are the available clips:
{clip_info}

Transcript:
{transcript_text}

User direction: {body.get('prompt', 'Create a compelling rough edit')}

Respond with a JSON array of segments, each with: clip_id, start_time, end_time, section_name
Example: [{{"clip_id": 1, "start_time": 0, "end_time": 10.5, "section_name": "Opening"}}]
Return ONLY the JSON array."""
            result = ai_request(prompt)
            # Try to parse JSON from response
            try:
                # Find JSON array in response
                match = re.search(r'\[.*\]', result, re.DOTALL)
                if match:
                    segments = json.loads(match.group())
                    self.send_json({'segments': segments, 'raw': result})
                else:
                    self.send_json({'error': 'Could not parse AI response', 'raw': result})
            except json.JSONDecodeError:
                self.send_json({'error': 'Invalid JSON from AI', 'raw': result})
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

    print(f"ResolveFlow — {PROJECT_DIR}")
    print(f"Database: {DB_PATH}")

    db.init_db(DB_PATH)

    # Initial ingest
    added = do_ingest()
    clips = db.get_all_clips(DB_PATH)
    print(f"Clips: {len(clips)} ({added} new)")
    total = sum(c.get('duration_seconds') or 0 for c in clips)
    print(f"Total duration: {total:.1f}s ({total/60:.1f}m)")

    port = int(os.environ.get('PORT', '8080'))
    import socket
    class ReusableHTTPServer(HTTPServer):
        allow_reuse_address = True
        def server_bind(self):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            super().server_bind()
    server = ReusableHTTPServer(('0.0.0.0', port), ResolveFlowHandler)
    print(f"Server: http://localhost:{port}")

    # Open browser
    threading.Timer(1, lambda: webbrowser.open(f'http://localhost:{port}')).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()


if __name__ == '__main__':
    main()
