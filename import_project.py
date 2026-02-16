#!/usr/bin/env python3
"""Import all project data from LaCie drive into SQLite cache."""
import db_manager
import os

PROJECT_DIR = '/Volumes/LaCie/VIDEO/nycap-portalcam'
MANIFEST = os.path.join(PROJECT_DIR, 'manifest.json')
TRANSCRIPTS_DIR = os.path.join(PROJECT_DIR, '_transcripts')

def main():
    print("Initializing database...")
    db_manager.init_db()

    if not os.path.exists(PROJECT_DIR):
        print(f"ERROR: {PROJECT_DIR} not found. Is the LaCie drive mounted?")
        return

    print("\n1. Importing manifest...")
    db_manager.import_manifest(MANIFEST)

    print("\n2. Importing transcripts...")
    db_manager.import_transcripts(TRANSCRIPTS_DIR)

    print("\n3. Importing diarization...")
    db_manager.import_diarization(PROJECT_DIR)

    # Summary
    conn = db_manager.get_db()
    clips = conn.execute("SELECT COUNT(*) as c FROM clips").fetchone()['c']
    transcripts = conn.execute("SELECT COUNT(*) as c FROM transcripts").fetchone()['c']
    words = conn.execute("SELECT COUNT(*) as c FROM transcript_words").fetchone()['c']
    diar = conn.execute("SELECT COUNT(*) as c FROM diarization").fetchone()['c']
    conn.close()

    print(f"\n✅ Import complete!")
    print(f"   Clips: {clips}")
    print(f"   Transcripts: {transcripts}")
    print(f"   Words: {words}")
    print(f"   Diarization segments: {diar}")

if __name__ == '__main__':
    main()
