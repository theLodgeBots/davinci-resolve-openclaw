"""SQLite database manager for DaVinci Resolve OpenClaw project."""
import sqlite3
import json
import os
import glob
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'resolve_cache.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS clips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT UNIQUE NOT NULL,
            source_folder TEXT,
            duration_seconds REAL,
            camera TEXT,
            resolution TEXT,
            codec TEXT,
            file_size_bytes INTEGER,
            file_path TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS transcripts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            clip_id INTEGER NOT NULL REFERENCES clips(id),
            full_text TEXT,
            language TEXT,
            duration REAL,
            word_count INTEGER,
            whisper_response_json TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS transcript_words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transcript_id INTEGER NOT NULL REFERENCES transcripts(id),
            word TEXT,
            start_time REAL,
            end_time REAL
        );
        CREATE TABLE IF NOT EXISTS diarization (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            clip_id INTEGER NOT NULL REFERENCES clips(id),
            speaker_label TEXT,
            start_time REAL,
            end_time REAL,
            text TEXT
        );
        CREATE TABLE IF NOT EXISTS ai_edits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            prompt_used TEXT,
            edit_plan_json TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS ai_edit_segments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            edit_id INTEGER NOT NULL REFERENCES ai_edits(id) ON DELETE CASCADE,
            clip_id INTEGER REFERENCES clips(id),
            start_time REAL,
            end_time REAL,
            section_name TEXT,
            order_index INTEGER,
            notes TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_transcript_words_tid ON transcript_words(transcript_id);
        CREATE INDEX IF NOT EXISTS idx_transcripts_clip ON transcripts(clip_id);
        CREATE INDEX IF NOT EXISTS idx_diarization_clip ON diarization(clip_id);
        CREATE INDEX IF NOT EXISTS idx_edit_segments_edit ON ai_edit_segments(edit_id);
    """)
    conn.commit()
    conn.close()

def import_manifest(manifest_path):
    with open(manifest_path) as f:
        manifest = json.load(f)
    conn = get_db()
    for clip in manifest['clips']:
        resolution = f"{clip['video']['width']}x{clip['video']['height']}" if 'video' in clip else None
        codec = clip['video']['codec'] if 'video' in clip else None
        conn.execute("""
            INSERT OR REPLACE INTO clips (filename, source_folder, duration_seconds, camera, resolution, codec, file_size_bytes, file_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (clip['filename'], clip.get('source', ''), clip.get('duration_seconds'), clip.get('source'),
              resolution, codec, clip.get('size_bytes'), clip.get('path')))
    conn.commit()
    conn.close()
    print(f"Imported {len(manifest['clips'])} clips from manifest")

def import_transcripts(transcripts_dir):
    conn = get_db()
    files = sorted(glob.glob(os.path.join(transcripts_dir, '*.json')))
    count = 0
    for fp in files:
        basename = os.path.splitext(os.path.basename(fp))[0]
        # Find clip by filename containing basename
        clip = conn.execute("SELECT id FROM clips WHERE filename LIKE ?", (f"%{basename}%",)).fetchone()
        if not clip:
            print(f"  No clip found for {basename}, skipping")
            continue
        clip_id = clip['id']
        # Skip if already imported
        existing = conn.execute("SELECT id FROM transcripts WHERE clip_id = ?", (clip_id,)).fetchone()
        if existing:
            continue
        with open(fp) as f:
            data = json.load(f)
        full_text = data.get('text', '')
        words = data.get('words', [])
        word_count = len(words)
        tid = conn.execute("""
            INSERT INTO transcripts (clip_id, full_text, language, duration, word_count, whisper_response_json)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (clip_id, full_text, data.get('language', 'english'), data.get('duration'), word_count, json.dumps(data))).lastrowid
        # Insert words
        for w in words:
            conn.execute("INSERT INTO transcript_words (transcript_id, word, start_time, end_time) VALUES (?, ?, ?, ?)",
                         (tid, w.get('word', ''), w.get('start'), w.get('end')))
        count += 1
    conn.commit()
    conn.close()
    print(f"Imported {count} transcripts")

def import_diarization(project_dir):
    conn = get_db()
    files = sorted(glob.glob(os.path.join(project_dir, '*_diarization.json')))
    count = 0
    for fp in files:
        basename = os.path.basename(fp).replace('_diarization.json', '')
        clip = conn.execute("SELECT id FROM clips WHERE filename LIKE ?", (f"%{basename}%",)).fetchone()
        if not clip:
            print(f"  No clip found for {basename}, skipping")
            continue
        clip_id = clip['id']
        existing = conn.execute("SELECT id FROM diarization WHERE clip_id = ?", (clip_id,)).fetchone()
        if existing:
            continue
        with open(fp) as f:
            data = json.load(f)
        results = data.get('diarization_results', [])
        for seg in results:
            start_offset = seg.get('start_time', 0)
            trans = seg.get('transcription', {})
            segments = trans.get('segments', [])
            for s in segments:
                speaker = s.get('speaker', 'UNKNOWN')
                conn.execute("INSERT INTO diarization (clip_id, speaker_label, start_time, end_time, text) VALUES (?, ?, ?, ?, ?)",
                             (clip_id, speaker, start_offset + s.get('start', 0), start_offset + s.get('end', 0), s.get('text', '').strip()))
        count += 1
    conn.commit()
    conn.close()
    print(f"Imported diarization for {count} clips")

def get_full_transcript():
    conn = get_db()
    rows = conn.execute("""
        SELECT c.id as clip_id, c.filename, t.full_text, t.duration, t.id as transcript_id
        FROM clips c JOIN transcripts t ON t.clip_id = c.id
        ORDER BY c.filename
    """).fetchall()
    result = []
    for r in rows:
        words = conn.execute("SELECT word, start_time, end_time FROM transcript_words WHERE transcript_id = ? ORDER BY start_time", (r['transcript_id'],)).fetchall()
        diar = conn.execute("SELECT speaker_label, start_time, end_time, text FROM diarization WHERE clip_id = ? ORDER BY start_time", (r['clip_id'],)).fetchall()
        result.append({
            'clip_id': r['clip_id'],
            'filename': r['filename'],
            'full_text': r['full_text'],
            'duration': r['duration'],
            'words': [dict(w) for w in words],
            'diarization': [dict(d) for d in diar]
        })
    conn.close()
    return result

# CRUD for ai_edits
def create_ai_edit(name, description, prompt_used, edit_plan_json, segments=None):
    conn = get_db()
    eid = conn.execute("INSERT INTO ai_edits (name, description, prompt_used, edit_plan_json) VALUES (?, ?, ?, ?)",
                       (name, description, prompt_used, json.dumps(edit_plan_json))).lastrowid
    if segments:
        for s in segments:
            conn.execute("INSERT INTO ai_edit_segments (edit_id, clip_id, start_time, end_time, section_name, order_index, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
                         (eid, s.get('clip_id'), s.get('start_time'), s.get('end_time'), s.get('section_name'), s.get('order_index'), s.get('notes')))
    conn.commit()
    conn.close()
    return eid

def get_ai_edit(edit_id):
    conn = get_db()
    edit = conn.execute("SELECT * FROM ai_edits WHERE id = ?", (edit_id,)).fetchone()
    if not edit:
        conn.close()
        return None
    segments = conn.execute("SELECT * FROM ai_edit_segments WHERE edit_id = ? ORDER BY order_index", (edit_id,)).fetchall()
    conn.close()
    return {**dict(edit), 'segments': [dict(s) for s in segments]}

def list_ai_edits():
    conn = get_db()
    edits = conn.execute("SELECT * FROM ai_edits ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(e) for e in edits]

def update_ai_edit(edit_id, **kwargs):
    conn = get_db()
    fields = []
    values = []
    for k in ('name', 'description', 'prompt_used', 'edit_plan_json'):
        if k in kwargs:
            fields.append(f"{k} = ?")
            values.append(json.dumps(kwargs[k]) if k == 'edit_plan_json' else kwargs[k])
    fields.append("updated_at = datetime('now')")
    values.append(edit_id)
    conn.execute(f"UPDATE ai_edits SET {', '.join(fields)} WHERE id = ?", values)
    if 'segments' in kwargs:
        conn.execute("DELETE FROM ai_edit_segments WHERE edit_id = ?", (edit_id,))
        for s in kwargs['segments']:
            conn.execute("INSERT INTO ai_edit_segments (edit_id, clip_id, start_time, end_time, section_name, order_index, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
                         (edit_id, s.get('clip_id'), s.get('start_time'), s.get('end_time'), s.get('section_name'), s.get('order_index'), s.get('notes')))
    conn.commit()
    conn.close()

def delete_ai_edit(edit_id):
    conn = get_db()
    conn.execute("DELETE FROM ai_edits WHERE id = ?", (edit_id,))
    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print("Database initialized")
