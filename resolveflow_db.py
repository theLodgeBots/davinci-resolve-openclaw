"""ResolveFlow database layer — SQLite storage for clips, transcripts, scripts."""

import sqlite3
import os
import json
from datetime import datetime

SCHEMA = """
CREATE TABLE IF NOT EXISTS clips (
    id INTEGER PRIMARY KEY,
    filename TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    full_path TEXT NOT NULL,
    duration_seconds REAL,
    camera TEXT,
    resolution TEXT,
    codec TEXT,
    fps REAL,
    file_size_bytes INTEGER,
    has_audio BOOLEAN DEFAULT 1,
    thumbnail_path TEXT,
    ai_title TEXT,
    ai_summary TEXT,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS transcripts (
    id INTEGER PRIMARY KEY,
    clip_id INTEGER NOT NULL REFERENCES clips(id),
    full_text TEXT,
    language TEXT DEFAULT 'en',
    duration REAL,
    word_count INTEGER,
    raw_response JSON,
    method TEXT DEFAULT 'resolve',
    transcribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS transcript_segments (
    id INTEGER PRIMARY KEY,
    transcript_id INTEGER NOT NULL REFERENCES transcripts(id),
    clip_id INTEGER NOT NULL REFERENCES clips(id),
    text TEXT NOT NULL,
    start_time REAL NOT NULL,
    end_time REAL NOT NULL,
    speaker TEXT,
    confidence REAL
);

CREATE TABLE IF NOT EXISTS scripts (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    target_duration_seconds REAL,
    ai_prompt TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS script_segments (
    id INTEGER PRIMARY KEY,
    script_id INTEGER NOT NULL REFERENCES scripts(id),
    clip_id INTEGER NOT NULL REFERENCES clips(id),
    start_time REAL NOT NULL,
    end_time REAL NOT NULL,
    section_name TEXT,
    order_index INTEGER NOT NULL,
    notes TEXT,
    transition TEXT DEFAULT 'cut'
);
"""


def get_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path):
    conn = get_db(db_path)
    conn.executescript(SCHEMA)
    # Migrations
    cols = {r[1] for r in conn.execute("PRAGMA table_info(clips)").fetchall()}
    if 'ai_title' not in cols:
        conn.execute("ALTER TABLE clips ADD COLUMN ai_title TEXT")
    if 'ai_summary' not in cols:
        conn.execute("ALTER TABLE clips ADD COLUMN ai_summary TEXT")
    seg_cols = {r[1] for r in conn.execute("PRAGMA table_info(script_segments)").fetchall()}
    if 'cut_words' not in seg_cols:
        conn.execute("ALTER TABLE script_segments ADD COLUMN cut_words TEXT DEFAULT '[]'")
    conn.commit()
    conn.close()


def import_clips_from_scan(db_path, clips_data):
    """Import scanned clips. clips_data is list of dicts with keys matching clips table.
    Skips clips already in DB by full_path."""
    conn = get_db(db_path)
    existing = {r[0] for r in conn.execute("SELECT full_path FROM clips").fetchall()}
    added = 0
    for c in clips_data:
        if c['full_path'] in existing:
            continue
        conn.execute(
            """INSERT INTO clips (filename, relative_path, full_path, duration_seconds,
               camera, resolution, codec, fps, file_size_bytes, has_audio, thumbnail_path)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (c['filename'], c['relative_path'], c['full_path'],
             c.get('duration_seconds'), c.get('camera'), c.get('resolution'),
             c.get('codec'), c.get('fps'), c.get('file_size_bytes'),
             c.get('has_audio', 1), c.get('thumbnail_path'))
        )
        added += 1
    conn.commit()
    conn.close()
    return added


def get_all_clips(db_path):
    conn = get_db(db_path)
    rows = conn.execute("SELECT * FROM clips ORDER BY filename").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_clip(db_path, clip_id):
    conn = get_db(db_path)
    row = conn.execute("SELECT * FROM clips WHERE id=?", (clip_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_untranscribed_clip_ids(db_path):
    conn = get_db(db_path)
    rows = conn.execute(
        "SELECT id FROM clips WHERE id NOT IN (SELECT clip_id FROM transcripts) AND has_audio=1"
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def save_transcript(db_path, clip_id, full_text, segments, raw_response, duration=None, language='en', method='whisper'):
    conn = get_db(db_path)
    word_count = len(full_text.split()) if full_text else 0
    cur = conn.execute(
        """INSERT INTO transcripts (clip_id, full_text, language, duration, word_count, raw_response, method)
           VALUES (?,?,?,?,?,?,?)""",
        (clip_id, full_text, language, duration, word_count, json.dumps(raw_response), method)
    )
    transcript_id = cur.lastrowid
    for seg in segments:
        conn.execute(
            """INSERT INTO transcript_segments (transcript_id, clip_id, text, start_time, end_time, speaker, confidence)
               VALUES (?,?,?,?,?,?,?)""",
            (transcript_id, clip_id, seg['text'], seg['start'], seg['end'],
             seg.get('speaker'), seg.get('confidence'))
        )
    conn.commit()
    conn.close()
    return transcript_id


def get_clip_transcript(db_path, clip_id):
    conn = get_db(db_path)
    t = conn.execute("SELECT * FROM transcripts WHERE clip_id=? ORDER BY id DESC LIMIT 1", (clip_id,)).fetchone()
    if not t:
        conn.close()
        return None
    segments = conn.execute(
        "SELECT * FROM transcript_segments WHERE transcript_id=? ORDER BY start_time", (t['id'],)
    ).fetchall()
    conn.close()
    return {'transcript': dict(t), 'segments': [dict(s) for s in segments]}


def get_full_transcript(db_path):
    conn = get_db(db_path)
    rows = conn.execute("""
        SELECT ts.*, c.filename FROM transcript_segments ts
        JOIN transcripts t ON ts.transcript_id = t.id
        JOIN clips c ON ts.clip_id = c.id
        ORDER BY c.filename, ts.start_time
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Scripts CRUD ---

def get_all_scripts(db_path):
    conn = get_db(db_path)
    rows = conn.execute("SELECT * FROM scripts ORDER BY updated_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_script(db_path, name, description=None, target_duration=None, ai_prompt=None):
    conn = get_db(db_path)
    cur = conn.execute(
        "INSERT INTO scripts (name, description, target_duration_seconds, ai_prompt) VALUES (?,?,?,?)",
        (name, description, target_duration, ai_prompt)
    )
    conn.commit()
    script_id = cur.lastrowid
    conn.close()
    return script_id


def get_script(db_path, script_id):
    conn = get_db(db_path)
    s = conn.execute("SELECT * FROM scripts WHERE id=?", (script_id,)).fetchone()
    if not s:
        conn.close()
        return None
    segments = conn.execute("""
        SELECT ss.*, c.filename FROM script_segments ss
        JOIN clips c ON ss.clip_id = c.id
        WHERE ss.script_id=? ORDER BY ss.order_index
    """, (script_id,)).fetchall()
    
    # Enrich each segment with actual transcript text from that time range
    result_segments = []
    for seg in segments:
        seg_dict = dict(seg)
        # Find transcript segments that overlap with this script segment's time range
        # Strict matching: transcript segment must have >50% of its duration inside the script range
        # This prevents same-clip segments from bleeding text across different time ranges
        seg_start = seg_dict['start_time']
        seg_end = seg_dict['end_time']
        ts = conn.execute("""
            SELECT text, start_time, end_time FROM transcript_segments
            WHERE clip_id=?
              AND start_time < ?
              AND end_time > ?
            ORDER BY start_time
        """, (seg_dict['clip_id'], seg_end, seg_start)).fetchall()
        # Filter: only include if >50% of the transcript segment overlaps with script range
        filtered = []
        for row in ts:
            t_start, t_end = row['start_time'], row['end_time']
            t_dur = t_end - t_start
            if t_dur <= 0:
                continue
            overlap_start = max(t_start, seg_start)
            overlap_end = min(t_end, seg_end)
            overlap = max(0, overlap_end - overlap_start)
            if overlap / t_dur >= 0.5:
                filtered.append(row)
        if filtered:
            seg_dict['transcript_text'] = ' '.join(row['text'] for row in filtered)
        else:
            # Fallback: midpoint overlap (less strict)
            ts_mid = conn.execute("""
                SELECT text, start_time, end_time FROM transcript_segments
                WHERE clip_id=? AND (start_time + end_time) / 2.0 >= ? AND (start_time + end_time) / 2.0 <= ?
                ORDER BY start_time
            """, (seg_dict['clip_id'], seg_start, seg_end)).fetchall()
            if ts_mid:
                seg_dict['transcript_text'] = ' '.join(row['text'] for row in ts_mid)
            else:
                # Last resort: full clip transcript
                t = conn.execute("SELECT full_text FROM transcripts WHERE clip_id=?", (seg_dict['clip_id'],)).fetchone()
                seg_dict['transcript_text'] = t['full_text'] if t else ''
        result_segments.append(seg_dict)
    
    conn.close()
    return {'script': dict(s), 'segments': result_segments}


def update_script(db_path, script_id, **kwargs):
    conn = get_db(db_path)
    allowed = {'name', 'description', 'target_duration_seconds', 'ai_prompt'}
    sets = []
    vals = []
    for k, v in kwargs.items():
        if k in allowed:
            sets.append(f"{k}=?")
            vals.append(v)
    if sets:
        sets.append("updated_at=CURRENT_TIMESTAMP")
        vals.append(script_id)
        conn.execute(f"UPDATE scripts SET {','.join(sets)} WHERE id=?", vals)
        conn.commit()
    conn.close()


def delete_script(db_path, script_id):
    conn = get_db(db_path)
    conn.execute("DELETE FROM script_segments WHERE script_id=?", (script_id,))
    conn.execute("DELETE FROM scripts WHERE id=?", (script_id,))
    conn.commit()
    conn.close()


def add_script_segment(db_path, script_id, clip_id, start_time, end_time,
                        section_name=None, order_index=None, notes=None, transition='cut'):
    conn = get_db(db_path)
    if order_index is None:
        row = conn.execute("SELECT COALESCE(MAX(order_index),0)+1 FROM script_segments WHERE script_id=?",
                           (script_id,)).fetchone()
        order_index = row[0]
    cur = conn.execute(
        """INSERT INTO script_segments (script_id, clip_id, start_time, end_time, section_name, order_index, notes, transition)
           VALUES (?,?,?,?,?,?,?,?)""",
        (script_id, clip_id, start_time, end_time, section_name, order_index, notes, transition)
    )
    conn.execute("UPDATE scripts SET updated_at=CURRENT_TIMESTAMP WHERE id=?", (script_id,))
    conn.commit()
    seg_id = cur.lastrowid
    conn.close()
    return seg_id


def update_script_segment(db_path, script_id, seg_id, **kwargs):
    conn = get_db(db_path)
    allowed = {'start_time', 'end_time', 'section_name', 'order_index', 'notes', 'transition', 'clip_id', 'cut_words'}
    sets = []
    vals = []
    for k, v in kwargs.items():
        if k in allowed:
            sets.append(f"{k}=?")
            vals.append(v)
    if sets:
        vals.extend([seg_id, script_id])
        conn.execute(f"UPDATE script_segments SET {','.join(sets)} WHERE id=? AND script_id=?", vals)
        conn.execute("UPDATE scripts SET updated_at=CURRENT_TIMESTAMP WHERE id=?", (script_id,))
        conn.commit()
    conn.close()


def delete_script_segment(db_path, script_id, seg_id):
    conn = get_db(db_path)
    conn.execute("DELETE FROM script_segments WHERE id=? AND script_id=?", (seg_id, script_id))
    conn.execute("UPDATE scripts SET updated_at=CURRENT_TIMESTAMP WHERE id=?", (script_id,))
    conn.commit()
    conn.close()


def export_as_edl(db_path, script_id, fps=24.0):
    """Export script as CMX 3600 EDL."""
    data = get_script(db_path, script_id)
    if not data:
        return None
    script = data['script']
    segments = data['segments']

    def tc(seconds, fps_val):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        f = int((seconds % 1) * fps_val)
        return f"{h:02d}:{m:02d}:{s:02d}:{f:02d}"

    lines = [f"TITLE: {script['name']}", f"FCM: NON-DROP FRAME", ""]
    rec_pos = 0.0
    for i, seg in enumerate(segments, 1):
        src_in = tc(seg['start_time'], fps)
        src_out = tc(seg['end_time'], fps)
        dur = seg['end_time'] - seg['start_time']
        rec_in = tc(rec_pos, fps)
        rec_out = tc(rec_pos + dur, fps)
        rec_pos += dur
        # Clean filename for reel name (max 8 chars)
        reel = os.path.splitext(seg['filename'])[0][:8].upper().ljust(8)
        lines.append(f"{i:03d}  {reel} V     C        {src_in} {src_out} {rec_in} {rec_out}")
        if seg.get('section_name'):
            lines.append(f"* COMMENT: {seg['section_name']}")
        lines.append(f"* FROM CLIP NAME: {seg['filename']}")
        lines.append("")

    return "\n".join(lines)
