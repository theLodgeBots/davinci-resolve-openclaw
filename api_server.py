#!/usr/bin/env python3
"""Lightweight API server for the Resolve dashboard (port 8081)."""
import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import db_manager

class APIHandler(BaseHTTPRequestHandler):
    def _json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _read_body(self):
        length = int(self.headers.get('Content-Length', 0))
        return json.loads(self.rfile.read(length)) if length else {}

    def do_OPTIONS(self):
        self._json({})

    def do_GET(self):
        path = urlparse(self.path).path.rstrip('/')

        if path == '/api/clips':
            conn = db_manager.get_db()
            clips = conn.execute("SELECT * FROM clips ORDER BY filename").fetchall()
            conn.close()
            self._json([dict(c) for c in clips])

        elif path == '/api/transcript/full':
            self._json(db_manager.get_full_transcript())

        elif path.startswith('/api/transcript/'):
            clip_id = path.split('/')[-1]
            conn = db_manager.get_db()
            t = conn.execute("SELECT * FROM transcripts WHERE clip_id = ?", (clip_id,)).fetchone()
            if not t:
                self._json({'error': 'not found'}, 404)
                conn.close()
                return
            words = conn.execute("SELECT word, start_time, end_time FROM transcript_words WHERE transcript_id = ? ORDER BY start_time", (t['id'],)).fetchall()
            conn.close()
            self._json({**dict(t), 'words': [dict(w) for w in words], 'whisper_response_json': None})

        elif path.startswith('/api/diarization/'):
            clip_id = path.split('/')[-1]
            conn = db_manager.get_db()
            rows = conn.execute("SELECT * FROM diarization WHERE clip_id = ? ORDER BY start_time", (clip_id,)).fetchall()
            conn.close()
            self._json([dict(r) for r in rows])

        elif path == '/api/ai-edits':
            self._json(db_manager.list_ai_edits())

        elif path.startswith('/api/ai-edit/'):
            edit_id = path.split('/')[-1]
            edit = db_manager.get_ai_edit(int(edit_id))
            if edit:
                self._json(edit)
            else:
                self._json({'error': 'not found'}, 404)
        else:
            self._json({'error': 'not found'}, 404)

    def do_POST(self):
        path = urlparse(self.path).path.rstrip('/')
        if path == '/api/ai-edit':
            body = self._read_body()
            name = body.get('name', 'Untitled Edit')
            description = body.get('description', '')
            custom_prompt = body.get('prompt', '')

            # Get full transcript
            transcript = db_manager.get_full_transcript()
            combined_text = "\n\n".join([f"[{t['filename']}]\n{t['full_text']}" for t in transcript])

            prompt = custom_prompt or f"""You are a video editor AI. Analyze this transcript from a multi-clip video shoot and create a structured edit plan.

The transcript contains {len(transcript)} clips. Create a compelling edit that:
1. Identifies the best segments to keep
2. Organizes them into logical sections
3. Suggests transitions and pacing

Return a JSON object with this structure:
{{
  "title": "Edit title",
  "sections": [
    {{
      "section_name": "Section Name",
      "clips": [
        {{
          "filename": "clip filename",
          "start_time": 0.0,
          "end_time": 30.0,
          "reason": "Why this segment"
        }}
      ],
      "transition": "cut/dissolve/etc",
      "notes": "Editorial notes"
    }}
  ],
  "total_estimated_duration": 120.0,
  "reasoning": "Overall edit reasoning"
}}

TRANSCRIPT:
{combined_text}"""

            # Call OpenAI
            api_key = os.environ.get('OPENAI_API_KEY')
            if not api_key:
                self._json({'error': 'OPENAI_API_KEY not set'}, 500)
                return

            try:
                import urllib.request
                req = urllib.request.Request(
                    'https://api.openai.com/v1/chat/completions',
                    data=json.dumps({
                        'model': 'gpt-4o',
                        'messages': [{'role': 'user', 'content': prompt}],
                        'temperature': 0.7,
                        'response_format': {'type': 'json_object'}
                    }).encode(),
                    headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
                )
                with urllib.request.urlopen(req, timeout=120) as resp:
                    result = json.loads(resp.read())
                edit_plan = json.loads(result['choices'][0]['message']['content'])
            except Exception as e:
                self._json({'error': f'OpenAI API error: {str(e)}'}, 500)
                return

            # Save to DB
            conn = db_manager.get_db()
            segments = []
            for i, section in enumerate(edit_plan.get('sections', [])):
                for clip_ref in section.get('clips', []):
                    clip_row = conn.execute("SELECT id FROM clips WHERE filename LIKE ?", (f"%{clip_ref.get('filename', '')}%",)).fetchone()
                    segments.append({
                        'clip_id': clip_row['id'] if clip_row else None,
                        'start_time': clip_ref.get('start_time'),
                        'end_time': clip_ref.get('end_time'),
                        'section_name': section.get('section_name', ''),
                        'order_index': i,
                        'notes': clip_ref.get('reason', '')
                    })
            conn.close()

            edit_id = db_manager.create_ai_edit(name, description, prompt, edit_plan, segments)
            self._json(db_manager.get_ai_edit(edit_id))
        else:
            self._json({'error': 'not found'}, 404)

    def do_PUT(self):
        path = urlparse(self.path).path.rstrip('/')
        if path.startswith('/api/ai-edit/'):
            edit_id = int(path.split('/')[-1])
            body = self._read_body()
            db_manager.update_ai_edit(edit_id, **body)
            self._json(db_manager.get_ai_edit(edit_id))
        else:
            self._json({'error': 'not found'}, 404)

    def do_DELETE(self):
        path = urlparse(self.path).path.rstrip('/')
        if path.startswith('/api/ai-edit/'):
            edit_id = int(path.split('/')[-1])
            db_manager.delete_ai_edit(edit_id)
            self._json({'ok': True})
        else:
            self._json({'error': 'not found'}, 404)

    def log_message(self, format, *args):
        print(f"[API] {args[0]}" if args else "")

if __name__ == '__main__':
    db_manager.init_db()
    server = HTTPServer(('0.0.0.0', 8081), APIHandler)
    print("API server running on http://localhost:8081")
    server.serve_forever()
