#!/usr/bin/env python3
"""
DaVinci Resolve Storyboard Server
Trello-style rough-cut editor with scene detection, transcript summaries,
drag-and-drop arrangement, and title card brainstorming.
"""

import json
import os
import sys
import time
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

# Resolve scripting setup
RESOLVE_SCRIPT_API = "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting"
RESOLVE_SCRIPT_LIB = "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so"
os.environ["RESOLVE_SCRIPT_API"] = RESOLVE_SCRIPT_API
os.environ["RESOLVE_SCRIPT_LIB"] = RESOLVE_SCRIPT_LIB
if f"{RESOLVE_SCRIPT_API}/Modules/" not in sys.path:
    sys.path.append(f"{RESOLVE_SCRIPT_API}/Modules/")

import DaVinciResolveScript as dvr_script

# State
PROJECT_DIR = "/Volumes/LaCie/VIDEO/nycap-portalcam"
TRANSCRIPTS_DIR = os.path.join(PROJECT_DIR, "_transcripts")
STATE_FILE = os.path.join(PROJECT_DIR, "_storyboard_state.json")


def get_resolve():
    return dvr_script.scriptapp("Resolve")


def load_clips_with_transcripts():
    """Load all clips with their transcripts and metadata."""
    manifest_path = os.path.join(PROJECT_DIR, "manifest.json")
    if not os.path.exists(manifest_path):
        return []

    manifest = json.load(open(manifest_path))
    clips = []

    for clip in manifest["clips"]:
        stem = os.path.splitext(clip["filename"])[0]
        tf = os.path.join(TRANSCRIPTS_DIR, f"{stem}.json")

        entry = {
            "id": stem,
            "filename": clip["filename"],
            "source": clip.get("source", ""),
            "duration": round(clip.get("duration_seconds", 0), 1),
            "size_mb": clip.get("size_mb", 0),
            "resolution": f"{clip.get('video', {}).get('width', '?')}x{clip.get('video', {}).get('height', '?')}",
            "fps": clip.get("video", {}).get("fps", ""),
            "transcript": "",
            "summary": "",
            "has_speech": False,
            "word_count": 0,
            "scene_type": "unknown",
        }

        if os.path.exists(tf):
            t = json.load(open(tf))
            text = t.get("text", "").strip()
            entry["transcript"] = text
            entry["has_speech"] = len(text) > 20
            entry["word_count"] = len(text.split()) if text else 0

            # Auto-detect scene type from content
            lower = text.lower()
            if any(w in lower for w in ["start over", "redo", "one two three"]):
                entry["scene_type"] = "outtake"
            elif any(w in lower for w in ["hi i'm", "welcome to", "hey so we're"]):
                entry["scene_type"] = "intro"
            elif any(w in lower for w in ["scan", "scanning", "portal cam", "portalcam"]):
                entry["scene_type"] = "demo"
            elif any(w in lower for w in ["price", "cost", "$", "thousand", "affordable"]):
                entry["scene_type"] = "pricing"
            elif any(w in lower for w in ["quality", "accuracy", "detail", "impressive"]):
                entry["scene_type"] = "quality"
            elif any(w in lower for w in ["thanks", "thumbs up", "overall"]):
                entry["scene_type"] = "conclusion"
            elif entry["has_speech"]:
                entry["scene_type"] = "interview"

            if not entry["has_speech"]:
                entry["scene_type"] = "broll"

        clips.append(entry)

    return clips


def summarize_transcripts_ai(clips):
    """Use OpenAI to summarize each clip's transcript."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return clips

    to_summarize = [c for c in clips if c["has_speech"] and not c.get("summary")]
    if not to_summarize:
        return clips

    # Batch summarize
    texts = []
    for c in to_summarize:
        texts.append(f"[{c['id']}] ({c['duration']}s): {c['transcript'][:500]}")

    prompt = f"""Summarize each video clip transcript in 1-2 sentences. Focus on the KEY content — what's being said/shown.
Format: one line per clip, starting with the ID in brackets.

{chr(10).join(texts)}"""

    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
                "max_tokens": 2000,
            },
            timeout=30,
        )
        if response.status_code == 200:
            content = response.json()["choices"][0]["message"]["content"]
            # Parse summaries
            for line in content.strip().split("\n"):
                line = line.strip()
                if line.startswith("["):
                    bracket_end = line.find("]")
                    if bracket_end > 0:
                        clip_id = line[1:bracket_end]
                        summary = line[bracket_end + 1:].strip().lstrip(":-– ")
                        for c in clips:
                            if c["id"] == clip_id:
                                c["summary"] = summary
    except Exception as e:
        print(f"Summarize error: {e}")

    return clips


def load_state():
    """Load saved storyboard state (arrangement, title cards, notes)."""
    if os.path.exists(STATE_FILE):
        return json.load(open(STATE_FILE))
    return {
        "arrangement": [],  # ordered list of {type: "clip"|"title", id/text, ...}
        "notes": "",
        "title": "Untitled Edit",
    }


def save_state(state):
    """Save storyboard state."""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


# ========== HTML ==========

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DaVinci Resolve — Storyboard</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, system-ui, sans-serif; background: #0d1117; color: #c9d1d9; }

/* Header */
.header { background: #161b22; border-bottom: 1px solid #30363d; padding: 12px 20px; display: flex; align-items: center; gap: 12px; }
.header h1 { font-size: 18px; color: #f0f6fc; }
.header .dot { width: 8px; height: 8px; border-radius: 50%; background: #3fb950; display: inline-block; }
.header .info { color: #8b949e; font-size: 13px; margin-left: auto; }
.btn { background: #21262d; border: 1px solid #30363d; color: #c9d1d9; padding: 6px 12px; border-radius: 6px; cursor: pointer; font-size: 13px; }
.btn:hover { background: #30363d; }
.btn.primary { background: #238636; border-color: #2ea043; color: #fff; }
.btn.primary:hover { background: #2ea043; }

/* Layout */
.layout { display: flex; height: calc(100vh - 52px); }

/* Sidebar: Source Clips */
.sidebar { width: 340px; background: #161b22; border-right: 1px solid #30363d; display: flex; flex-direction: column; flex-shrink: 0; }
.sidebar-header { padding: 12px; border-bottom: 1px solid #30363d; display: flex; align-items: center; gap: 8px; }
.sidebar-header h2 { font-size: 14px; color: #f0f6fc; }
.sidebar-header .count { background: #30363d; font-size: 11px; padding: 2px 6px; border-radius: 8px; color: #8b949e; }
.filter-bar { padding: 8px 12px; border-bottom: 1px solid #21262d; display: flex; gap: 4px; flex-wrap: wrap; }
.filter-btn { font-size: 11px; padding: 3px 8px; border-radius: 12px; border: 1px solid #30363d; background: transparent; color: #8b949e; cursor: pointer; }
.filter-btn.active { background: #1f6feb; border-color: #1f6feb; color: #fff; }
.clip-list { flex: 1; overflow-y: auto; padding: 8px; }

.clip-card { background: #0d1117; border: 1px solid #30363d; border-radius: 6px; padding: 10px; margin-bottom: 6px; cursor: grab; transition: all 0.15s; border-left: 3px solid #30363d; }
.clip-card:hover { border-color: #58a6ff; }
.clip-card.dragging { opacity: 0.5; }
.clip-card .clip-name { font-size: 13px; font-weight: 600; color: #f0f6fc; margin-bottom: 4px; }
.clip-card .clip-meta { font-size: 11px; color: #8b949e; display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 4px; }
.clip-card .clip-summary { font-size: 12px; color: #b1bac4; line-height: 1.4; }
.clip-card .clip-transcript { font-size: 11px; color: #8b949e; max-height: 0; overflow: hidden; transition: max-height 0.2s; line-height: 1.4; margin-top: 4px; }
.clip-card .clip-transcript.open { max-height: 200px; overflow-y: auto; }

/* Scene type colors */
.clip-card[data-type="intro"] { border-left-color: #58a6ff; }
.clip-card[data-type="demo"] { border-left-color: #3fb950; }
.clip-card[data-type="pricing"] { border-left-color: #d29922; }
.clip-card[data-type="quality"] { border-left-color: #bc8cff; }
.clip-card[data-type="interview"] { border-left-color: #79c0ff; }
.clip-card[data-type="conclusion"] { border-left-color: #f778ba; }
.clip-card[data-type="broll"] { border-left-color: #484f58; }
.clip-card[data-type="outtake"] { border-left-color: #f85149; }

.tag { font-size: 10px; padding: 1px 5px; border-radius: 3px; background: #21262d; }
.tag.intro { background: #1a3a5c; color: #58a6ff; }
.tag.demo { background: #1a3d2e; color: #3fb950; }
.tag.pricing { background: #3d2e1a; color: #d29922; }
.tag.quality { background: #2d1a3d; color: #bc8cff; }
.tag.interview { background: #1a2d3d; color: #79c0ff; }
.tag.conclusion { background: #3d1a2d; color: #f778ba; }
.tag.broll { background: #1a1a1a; color: #484f58; }
.tag.outtake { background: #3d1a1a; color: #f85149; }

/* Main: Storyboard */
.main { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.main-header { padding: 12px 16px; border-bottom: 1px solid #30363d; display: flex; align-items: center; gap: 12px; }
.main-header input { background: #0d1117; border: 1px solid #30363d; color: #f0f6fc; padding: 6px 10px; border-radius: 4px; font-size: 16px; font-weight: 600; flex: 1; }

.storyboard { flex: 1; overflow-y: auto; padding: 16px; }

/* Arrangement cards */
.arrange-item { background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 12px; margin-bottom: 8px; position: relative; display: flex; gap: 12px; align-items: flex-start; }
.arrange-item.drop-target { border-color: #58a6ff; background: #0d1117; }
.arrange-item .drag-handle { cursor: grab; color: #484f58; font-size: 16px; padding: 4px; user-select: none; }
.arrange-item .arrange-content { flex: 1; }
.arrange-item .arrange-name { font-size: 14px; font-weight: 600; color: #f0f6fc; }
.arrange-item .arrange-summary { font-size: 12px; color: #8b949e; margin-top: 4px; }
.arrange-item .arrange-actions { display: flex; gap: 4px; margin-top: 6px; }
.arrange-item .remove-btn { font-size: 11px; color: #f85149; cursor: pointer; }

/* Title card in arrangement */
.arrange-item.title-card { border-left: 3px solid #d29922; background: #1a1a0d; }
.arrange-item.title-card textarea { background: #0d1117; border: 1px solid #30363d; color: #f0f6fc; padding: 8px; border-radius: 4px; width: 100%; font-size: 16px; font-weight: 600; resize: vertical; min-height: 40px; font-family: inherit; }
.arrange-item.title-card .subtitle-input { font-size: 13px; font-weight: normal; margin-top: 4px; min-height: 30px; }

/* Notes panel */
.notes-panel { border-top: 1px solid #30363d; padding: 12px 16px; background: #161b22; }
.notes-panel textarea { width: 100%; background: #0d1117; border: 1px solid #30363d; color: #c9d1d9; padding: 8px; border-radius: 4px; font-size: 13px; min-height: 60px; resize: vertical; font-family: inherit; }
.notes-panel label { font-size: 12px; color: #8b949e; margin-bottom: 4px; display: block; }

/* Drop zone */
.drop-zone { border: 2px dashed #30363d; border-radius: 6px; padding: 24px; text-align: center; color: #484f58; font-size: 13px; margin-bottom: 8px; transition: all 0.15s; }
.drop-zone.active { border-color: #58a6ff; color: #58a6ff; background: rgba(31,111,235,0.05); }

/* Summary bar */
.summary-bar { padding: 8px 16px; background: #161b22; border-top: 1px solid #30363d; display: flex; gap: 16px; font-size: 12px; color: #8b949e; }
.summary-bar span { display: flex; align-items: center; gap: 4px; }
</style>
</head>
<body>

<div class="header">
  <span class="dot" id="statusDot"></span>
  <h1>🎬 Storyboard</h1>
  <span class="info" id="resolveInfo"></span>
  <button class="btn" onclick="loadData()">⟳ Refresh</button>
  <button class="btn" onclick="addTitleCard()">+ Title Card</button>
  <button class="btn" onclick="aiSuggest()">🤖 AI Arrange</button>
  <button class="btn primary" onclick="buildTimeline()">▶ Build in Resolve</button>
</div>

<div class="layout">
  <!-- Sidebar: Source Clips -->
  <div class="sidebar">
    <div class="sidebar-header">
      <h2>Source Clips</h2>
      <span class="count" id="clipCount">0</span>
    </div>
    <div class="filter-bar" id="filterBar"></div>
    <div class="clip-list" id="clipList"></div>
  </div>

  <!-- Main: Storyboard Arrangement -->
  <div class="main">
    <div class="main-header">
      <input type="text" id="editTitle" value="Untitled Edit" placeholder="Edit title..." oninput="saveState()">
    </div>

    <div class="storyboard" id="storyboard">
      <div class="drop-zone" id="dropZone"
           ondragover="handleDragOver(event)"
           ondragleave="handleDragLeave(event)"
           ondrop="handleDrop(event)">
        Drag clips here to build your rough cut
      </div>
    </div>

    <div class="notes-panel">
      <label>Notes / Script Ideas</label>
      <textarea id="editNotes" placeholder="Jot down ideas, script notes, structure thoughts..." oninput="saveState()"></textarea>
    </div>

    <div class="summary-bar">
      <span>📎 <strong id="arrangeCount">0</strong> items</span>
      <span>⏱ <strong id="totalDuration">0:00</strong> estimated</span>
      <span>🎬 <strong id="clipCountArrange">0</strong> clips</span>
      <span>📝 <strong id="titleCount">0</strong> title cards</span>
    </div>
  </div>
</div>

<script>
let allClips = [];
let arrangement = [];
let activeFilter = 'all';
let draggedClipId = null;
let draggedArrangeIdx = null;

async function loadData() {
  try {
    const res = await fetch('/api/clips');
    allClips = await res.json();
    document.getElementById('clipCount').textContent = allClips.length;
    
    const statusRes = await fetch('/api/status');
    const status = await statusRes.json();
    document.getElementById('resolveInfo').textContent = 
      status.connected ? `${status.product} ${status.version}` : 'Disconnected';
    document.getElementById('statusDot').style.background = status.connected ? '#3fb950' : '#f85149';
    
    // Load saved state
    const stateRes = await fetch('/api/state');
    const state = await stateRes.json();
    arrangement = state.arrangement || [];
    document.getElementById('editTitle').value = state.title || 'Untitled Edit';
    document.getElementById('editNotes').value = state.notes || '';
    
    buildFilters();
    renderClips();
    renderArrangement();
  } catch(e) {
    console.error(e);
  }
}

function buildFilters() {
  const types = new Set(allClips.map(c => c.scene_type));
  const bar = document.getElementById('filterBar');
  bar.innerHTML = '';
  
  const allBtn = el('button', {class: `filter-btn ${activeFilter === 'all' ? 'active' : ''}`, onclick: () => { activeFilter = 'all'; buildFilters(); renderClips(); }}, 'All');
  bar.appendChild(allBtn);
  
  const speechBtn = el('button', {class: `filter-btn ${activeFilter === 'speech' ? 'active' : ''}`, onclick: () => { activeFilter = 'speech'; buildFilters(); renderClips(); }}, '🗣 Has Speech');
  bar.appendChild(speechBtn);
  
  for (const t of ['intro','demo','pricing','quality','interview','conclusion','broll','outtake']) {
    if (!types.has(t)) continue;
    const btn = el('button', {class: `filter-btn ${activeFilter === t ? 'active' : ''} ${t}`, onclick: () => { activeFilter = t; buildFilters(); renderClips(); }}, t);
    bar.appendChild(btn);
  }
}

function renderClips() {
  const list = document.getElementById('clipList');
  list.innerHTML = '';
  
  let filtered = allClips;
  if (activeFilter === 'speech') filtered = allClips.filter(c => c.has_speech);
  else if (activeFilter !== 'all') filtered = allClips.filter(c => c.scene_type === activeFilter);
  
  for (const clip of filtered) {
    const card = document.createElement('div');
    card.className = 'clip-card';
    card.setAttribute('data-type', clip.scene_type);
    card.draggable = true;
    card.ondragstart = (e) => { draggedClipId = clip.id; e.dataTransfer.effectAllowed = 'copy'; card.classList.add('dragging'); };
    card.ondragend = () => { card.classList.remove('dragging'); };
    
    const dur = formatDuration(clip.duration);
    card.innerHTML = `
      <div class="clip-name">${clip.filename}</div>
      <div class="clip-meta">
        <span class="tag ${clip.scene_type}">${clip.scene_type}</span>
        <span>${dur}</span>
        <span>${clip.source}</span>
        <span>${clip.resolution}</span>
        ${clip.word_count ? `<span>${clip.word_count} words</span>` : ''}
      </div>
      ${clip.summary ? `<div class="clip-summary">${clip.summary}</div>` : ''}
      ${clip.transcript ? `
        <div class="clip-transcript" id="trans-${clip.id}">${clip.transcript}</div>
        <span style="font-size:11px;color:#58a6ff;cursor:pointer" onclick="toggleTranscript('${clip.id}')">▶ transcript</span>
      ` : ''}
    `;
    
    // Double click to add to arrangement
    card.ondblclick = () => addClipToArrangement(clip.id);
    
    list.appendChild(card);
  }
}

function toggleTranscript(id) {
  const el = document.getElementById('trans-' + id);
  el.classList.toggle('open');
}

function addClipToArrangement(clipId) {
  const clip = allClips.find(c => c.id === clipId);
  if (!clip) return;
  arrangement.push({
    type: 'clip',
    clipId: clip.id,
    filename: clip.filename,
    duration: clip.duration,
    summary: clip.summary || clip.transcript?.substring(0, 100) || '',
    scene_type: clip.scene_type,
    note: '',
  });
  renderArrangement();
  saveState();
}

function addTitleCard() {
  arrangement.push({
    type: 'title',
    text: 'Title Card',
    subtitle: '',
    duration: 3,
  });
  renderArrangement();
  saveState();
}

function renderArrangement() {
  const board = document.getElementById('storyboard');
  board.innerHTML = '';
  
  if (arrangement.length === 0) {
    board.innerHTML = `<div class="drop-zone" id="dropZone"
      ondragover="handleDragOver(event)" ondragleave="handleDragLeave(event)" ondrop="handleDrop(event)">
      Drag clips here or double-click to add • Click "+ Title Card" for section headers
    </div>`;
  }
  
  for (let i = 0; i < arrangement.length; i++) {
    const item = arrangement[i];
    
    // Drop zone between items
    const dz = document.createElement('div');
    dz.className = 'drop-zone';
    dz.style.padding = '4px';
    dz.style.margin = '2px 0';
    dz.style.border = '2px dashed transparent';
    dz.style.minHeight = '8px';
    dz.ondragover = (e) => { e.preventDefault(); dz.style.borderColor = '#58a6ff'; };
    dz.ondragleave = () => { dz.style.borderColor = 'transparent'; };
    dz.ondrop = (e) => { e.preventDefault(); dz.style.borderColor = 'transparent'; handleDropAt(i); };
    board.appendChild(dz);
    
    const el = document.createElement('div');
    el.className = `arrange-item ${item.type === 'title' ? 'title-card' : ''}`;
    el.draggable = true;
    el.ondragstart = (e) => { draggedArrangeIdx = i; draggedClipId = null; };
    el.ondragend = () => { draggedArrangeIdx = null; };
    
    if (item.type === 'title') {
      el.innerHTML = `
        <span class="drag-handle">⠿</span>
        <div class="arrange-content">
          <textarea placeholder="Title text..." oninput="arrangement[${i}].text=this.value;saveState()">${item.text}</textarea>
          <textarea class="subtitle-input" placeholder="Subtitle (optional)..." oninput="arrangement[${i}].subtitle=this.value;saveState()">${item.subtitle || ''}</textarea>
          <div class="arrange-actions">
            <span class="tag pricing">TITLE CARD</span>
            <span class="tag">${item.duration}s</span>
            <span class="remove-btn" onclick="removeItem(${i})">✕ remove</span>
          </div>
        </div>
      `;
    } else {
      const clip = allClips.find(c => c.id === item.clipId);
      const typeClass = item.scene_type || 'unknown';
      el.innerHTML = `
        <span class="drag-handle">⠿</span>
        <div class="arrange-content">
          <div class="arrange-name">${item.filename}</div>
          <div class="arrange-summary">${item.summary || item.filename}</div>
          <div class="arrange-actions">
            <span class="tag ${typeClass}">${typeClass}</span>
            <span class="tag">${formatDuration(item.duration)}</span>
            <span class="remove-btn" onclick="removeItem(${i})">✕ remove</span>
          </div>
        </div>
      `;
    }
    
    board.appendChild(el);
  }
  
  // Final drop zone
  if (arrangement.length > 0) {
    const finalDz = document.createElement('div');
    finalDz.className = 'drop-zone';
    finalDz.textContent = '+ Drop here to add to end';
    finalDz.style.padding = '12px';
    finalDz.ondragover = (e) => { e.preventDefault(); finalDz.classList.add('active'); };
    finalDz.ondragleave = () => finalDz.classList.remove('active');
    finalDz.ondrop = (e) => { e.preventDefault(); finalDz.classList.remove('active'); handleDropAt(arrangement.length); };
    board.appendChild(finalDz);
  }
  
  // Update summary
  const clips = arrangement.filter(a => a.type === 'clip');
  const titles = arrangement.filter(a => a.type === 'title');
  const totalSec = arrangement.reduce((a, i) => a + (i.duration || 0), 0);
  document.getElementById('arrangeCount').textContent = arrangement.length;
  document.getElementById('totalDuration').textContent = formatDuration(totalSec);
  document.getElementById('clipCountArrange').textContent = clips.length;
  document.getElementById('titleCount').textContent = titles.length;
}

function handleDragOver(e) { e.preventDefault(); e.currentTarget.classList.add('active'); }
function handleDragLeave(e) { e.currentTarget.classList.remove('active'); }
function handleDrop(e) {
  e.preventDefault();
  e.currentTarget.classList.remove('active');
  handleDropAt(arrangement.length);
}

function handleDropAt(index) {
  if (draggedArrangeIdx !== null) {
    // Reorder within arrangement
    const item = arrangement.splice(draggedArrangeIdx, 1)[0];
    if (draggedArrangeIdx < index) index--;
    arrangement.splice(index, 0, item);
    draggedArrangeIdx = null;
  } else if (draggedClipId) {
    // Add from sidebar
    const clip = allClips.find(c => c.id === draggedClipId);
    if (clip) {
      arrangement.splice(index, 0, {
        type: 'clip',
        clipId: clip.id,
        filename: clip.filename,
        duration: clip.duration,
        summary: clip.summary || clip.transcript?.substring(0, 100) || '',
        scene_type: clip.scene_type,
      });
    }
    draggedClipId = null;
  }
  renderArrangement();
  saveState();
}

function removeItem(idx) {
  arrangement.splice(idx, 1);
  renderArrangement();
  saveState();
}

async function saveState() {
  const state = {
    arrangement,
    title: document.getElementById('editTitle').value,
    notes: document.getElementById('editNotes').value,
  };
  await fetch('/api/state', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(state),
  });
}

async function aiSuggest() {
  if (!confirm('Let AI arrange clips into a suggested rough cut?')) return;
  const res = await fetch('/api/ai-arrange', {method: 'POST'});
  const data = await res.json();
  if (data.arrangement) {
    arrangement = data.arrangement;
    renderArrangement();
    saveState();
  }
}

async function buildTimeline() {
  if (arrangement.length === 0) return alert('Add some clips first!');
  if (!confirm('Build this arrangement as a new timeline in DaVinci Resolve?')) return;
  const res = await fetch('/api/build-timeline', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      title: document.getElementById('editTitle').value,
      arrangement,
    }),
  });
  const data = await res.json();
  alert(data.message || JSON.stringify(data));
}

function formatDuration(sec) {
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

function el(tag, attrs, text) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'onclick') e.onclick = v;
    else e.setAttribute(k, v);
  }
  if (text) e.textContent = text;
  return e;
}

loadData();
</script>
</body>
</html>"""


class StoryboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path in ("/", "/dashboard"):
            self._html(DASHBOARD_HTML)

        elif parsed.path == "/api/clips":
            clips = load_clips_with_transcripts()
            clips = summarize_transcripts_ai(clips)
            self._json(clips)

        elif parsed.path == "/api/status":
            resolve = get_resolve()
            self._json({
                "connected": resolve is not None,
                "product": resolve.GetProductName() if resolve else None,
                "version": resolve.GetVersionString() if resolve else None,
            })

        elif parsed.path == "/api/state":
            self._json(load_state())

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        body = self._read_body()

        if parsed.path == "/api/state":
            save_state(body)
            self._json({"ok": True})

        elif parsed.path == "/api/ai-arrange":
            clips = load_clips_with_transcripts()
            arrangement = ai_auto_arrange(clips)
            self._json({"arrangement": arrangement})

        elif parsed.path == "/api/build-timeline":
            result = build_resolve_timeline(body)
            self._json(result)

        else:
            self.send_response(404)
            self.end_headers()

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length:
            return json.loads(self.rfile.read(length))
        return {}

    def _json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode())

    def _html(self, html):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode())

    def log_message(self, format, *args):
        pass


def ai_auto_arrange(clips):
    """Use AI to suggest an arrangement."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return []

    speech_clips = [c for c in clips if c["has_speech"] and c["scene_type"] != "outtake"]
    context = json.dumps([{
        "id": c["id"],
        "filename": c["filename"],
        "duration": c["duration"],
        "scene_type": c["scene_type"],
        "summary": c.get("summary", ""),
        "transcript": c["transcript"][:200],
    } for c in speech_clips], indent=2)

    prompt = f"""Given these video clips from a PortalCam product review shoot, arrange them into a compelling rough cut with title cards.

Clips:
{context}

Return a JSON array of items in order. Each item is either:
- {{"type": "title", "text": "Section Title", "subtitle": "optional", "duration": 3}}
- {{"type": "clip", "clipId": "clip_id", "filename": "file.MP4", "duration": N, "summary": "why", "scene_type": "type"}}

Structure as: intro → what it does → pricing → demo → results → conclusion
Skip outtakes. Include 5-6 title cards between sections. Use only clips from the list above."""

    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": "Output only valid JSON array."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 3000,
            },
            timeout=60,
        )
        content = response.json()["choices"][0]["message"]["content"]
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(content)
    except Exception as e:
        print(f"AI arrange error: {e}")
        return []


def build_resolve_timeline(data):
    """Build a DaVinci Resolve timeline from the storyboard arrangement."""
    resolve = get_resolve()
    if not resolve:
        return {"error": "Cannot connect to DaVinci Resolve"}

    pm = resolve.GetProjectManager()
    project = pm.LoadProject("nycap-portalcam")
    if not project:
        return {"error": "Cannot load project"}

    media_pool = project.GetMediaPool()
    root = media_pool.GetRootFolder()

    # Collect pool items
    pool = {}
    def collect(folder):
        for c in folder.GetClipList():
            pool[c.GetName()] = c
        for s in folder.GetSubFolderList():
            collect(s)
    collect(root)

    title = data.get("title", "Storyboard Edit")
    arrangement = data.get("arrangement", [])

    # Create timeline
    resolve.OpenPage("edit")
    time.sleep(0.5)
    timeline = media_pool.CreateEmptyTimeline(title)
    if not timeline:
        return {"error": "Could not create timeline"}
    project.SetCurrentTimeline(timeline)

    placed = 0
    for item in arrangement:
        if item["type"] == "title":
            ti = timeline.InsertFusionTitleIntoTimeline("Text+")
            if ti:
                placed += 1
        elif item["type"] == "clip":
            pool_item = pool.get(item.get("filename"))
            if pool_item:
                result = media_pool.AppendToTimeline([pool_item])
                if result:
                    placed += 1

    pm.SaveProject()
    return {
        "message": f"Built timeline '{title}' with {placed}/{len(arrangement)} items in Resolve!",
        "placed": placed,
        "total": len(arrangement),
    }


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    print(f"Storyboard: http://localhost:{port}")
    server = HTTPServer(("0.0.0.0", port), StoryboardHandler)
    server.serve_forever()
