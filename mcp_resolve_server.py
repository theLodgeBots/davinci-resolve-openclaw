#!/usr/bin/env python3
"""
DaVinci Resolve MCP Server
Exposes Resolve's database and operations as MCP tools.
Also serves a Trello-style web dashboard on :8080.
"""

import json
import os
import sys
import time
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Resolve scripting setup
RESOLVE_SCRIPT_API = "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting"
RESOLVE_SCRIPT_LIB = "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so"
os.environ["RESOLVE_SCRIPT_API"] = RESOLVE_SCRIPT_API
os.environ["RESOLVE_SCRIPT_LIB"] = RESOLVE_SCRIPT_LIB
if f"{RESOLVE_SCRIPT_API}/Modules/" not in sys.path:
    sys.path.append(f"{RESOLVE_SCRIPT_API}/Modules/")

import DaVinciResolveScript as dvr_script


def get_resolve():
    resolve = dvr_script.scriptapp("Resolve")
    return resolve


def get_full_database():
    """Read the entire Resolve database into a JSON-serializable structure."""
    resolve = get_resolve()
    if not resolve:
        return {"error": "Cannot connect to DaVinci Resolve. Is it running?"}

    data = {
        "product": resolve.GetProductName(),
        "version": resolve.GetVersionString(),
        "currentPage": resolve.GetCurrentPage(),
        "databases": [],
        "projects": [],
    }

    pm = resolve.GetProjectManager()
    
    # Databases
    for db in pm.GetDatabaseList():
        data["databases"].append(db)
    data["currentDatabase"] = pm.GetCurrentDatabase()

    # Projects
    pm.GotoRootFolder()
    project_names = pm.GetProjectListInCurrentFolder()
    current_project = pm.GetCurrentProject()
    current_project_name = current_project.GetName() if current_project else None

    for pname in project_names:
        proj_data = {
            "name": pname,
            "isCurrent": pname == current_project_name,
            "timelines": [],
            "mediaPool": {"folders": [], "clipCount": 0},
            "renderJobs": [],
        }

        # Load project (skip if it's already current)
        if pname == current_project_name:
            project = current_project
        else:
            project = pm.LoadProject(pname)

        if project:
            # Timelines
            for i in range(1, project.GetTimelineCount() + 1):
                tl = project.GetTimelineByIndex(i)
                if tl:
                    tl_data = {
                        "name": tl.GetName(),
                        "index": i,
                        "startFrame": tl.GetStartFrame(),
                        "endFrame": tl.GetEndFrame(),
                        "videoTracks": tl.GetTrackCount("video"),
                        "audioTracks": tl.GetTrackCount("audio"),
                        "subtitleTracks": tl.GetTrackCount("subtitle"),
                        "clips": [],
                        "markers": {},
                    }
                    
                    # Duration
                    fps_str = tl.GetSetting("timelineFrameRate") or "24"
                    try:
                        fps = float(fps_str)
                    except:
                        fps = 24.0
                    frames = tl.GetEndFrame() - tl.GetStartFrame()
                    tl_data["durationSeconds"] = round(frames / fps, 1)
                    tl_data["fps"] = fps
                    
                    # Clips on V1
                    items = tl.GetItemListInTrack("video", 1) or []
                    for item in items:
                        clip_data = {
                            "name": item.GetName(),
                            "start": item.GetStart(),
                            "end": item.GetEnd(),
                            "duration": item.GetDuration(),
                            "enabled": item.GetClipEnabled(),
                            "color": item.GetClipColor(),
                        }
                        tl_data["clips"].append(clip_data)
                    
                    # Markers
                    try:
                        markers = tl.GetMarkers()
                        if markers:
                            tl_data["markers"] = {
                                str(k): v for k, v in markers.items()
                            }
                    except:
                        pass

                    proj_data["timelines"].append(tl_data)

            # Media Pool
            mp = project.GetMediaPool()
            root = mp.GetRootFolder()
            
            def scan_folder(folder, depth=0):
                folder_data = {
                    "name": folder.GetName(),
                    "clips": [],
                    "subfolders": [],
                }
                for clip in folder.GetClipList():
                    clip_info = {
                        "name": clip.GetName(),
                        "mediaId": clip.GetMediaId(),
                    }
                    try:
                        props = clip.GetClipProperty()
                        if props:
                            clip_info["duration"] = props.get("Duration", "")
                            clip_info["fps"] = props.get("FPS", "")
                            clip_info["resolution"] = props.get("Resolution", "")
                            clip_info["codec"] = props.get("Video Codec", "")
                            clip_info["filePath"] = props.get("File Path", "")
                    except:
                        pass
                    folder_data["clips"].append(clip_info)
                    proj_data["mediaPool"]["clipCount"] += 1

                if depth < 3:  # prevent infinite recursion
                    for sub in folder.GetSubFolderList():
                        folder_data["subfolders"].append(scan_folder(sub, depth + 1))
                
                return folder_data

            proj_data["mediaPool"]["folders"] = [scan_folder(root)]

            # Render Jobs
            for job in (project.GetRenderJobList() or []):
                proj_data["renderJobs"].append(job)

            # Close project if we opened it (reload current)
            if pname != current_project_name:
                pm.LoadProject(current_project_name)

        data["projects"].append(proj_data)

    return data


# === Web Server ===

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DaVinci Resolve — Dashboard</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, system-ui, sans-serif; background: #0d1117; color: #c9d1d9; }
.header { background: #161b22; border-bottom: 1px solid #30363d; padding: 16px 24px; display: flex; align-items: center; gap: 16px; }
.header h1 { font-size: 20px; color: #f0f6fc; }
.header .version { color: #8b949e; font-size: 14px; }
.header .status { margin-left: auto; display: flex; align-items: center; gap: 8px; }
.header .dot { width: 8px; height: 8px; border-radius: 50%; background: #3fb950; }
.header .dot.off { background: #f85149; }
.board { display: flex; gap: 16px; padding: 24px; overflow-x: auto; min-height: calc(100vh - 64px); align-items: flex-start; }
.column { background: #161b22; border: 1px solid #30363d; border-radius: 8px; min-width: 320px; max-width: 380px; flex-shrink: 0; }
.column-header { padding: 12px 16px; border-bottom: 1px solid #30363d; display: flex; align-items: center; gap: 8px; }
.column-header h2 { font-size: 14px; font-weight: 600; color: #f0f6fc; }
.column-header .count { background: #30363d; color: #8b949e; font-size: 12px; padding: 2px 8px; border-radius: 10px; }
.column-body { padding: 8px; max-height: calc(100vh - 140px); overflow-y: auto; }
.card { background: #0d1117; border: 1px solid #30363d; border-radius: 6px; padding: 12px; margin-bottom: 8px; cursor: pointer; transition: border-color 0.15s; }
.card:hover { border-color: #58a6ff; }
.card-title { font-size: 14px; font-weight: 600; color: #f0f6fc; margin-bottom: 6px; }
.card-meta { font-size: 12px; color: #8b949e; display: flex; flex-wrap: wrap; gap: 8px; }
.card-meta .tag { background: #1f2937; padding: 2px 6px; border-radius: 4px; }
.card-meta .tag.blue { background: #1a3a5c; color: #58a6ff; }
.card-meta .tag.green { background: #1a3d2e; color: #3fb950; }
.card-meta .tag.orange { background: #3d2e1a; color: #d29922; }
.card-meta .tag.red { background: #3d1a1a; color: #f85149; }
.card-meta .tag.purple { background: #2d1a3d; color: #bc8cff; }
.card .clips-list { margin-top: 8px; font-size: 12px; }
.card .clips-list .clip { padding: 4px 0; border-top: 1px solid #21262d; display: flex; justify-content: space-between; }
.card .clips-list .clip:first-child { border-top: none; }
.expand-btn { font-size: 11px; color: #58a6ff; cursor: pointer; margin-top: 4px; }
.project-card { border-left: 3px solid #58a6ff; }
.timeline-card { border-left: 3px solid #3fb950; }
.media-card { border-left: 3px solid #d29922; }
.render-card { border-left: 3px solid #bc8cff; }
.empty { color: #484f58; font-size: 13px; padding: 16px; text-align: center; }
.refresh-btn { background: #21262d; border: 1px solid #30363d; color: #c9d1d9; padding: 6px 12px; border-radius: 6px; cursor: pointer; font-size: 13px; }
.refresh-btn:hover { background: #30363d; }
#loading { display: none; position: fixed; top: 50%; left: 50%; transform: translate(-50%,-50%); background: #161b22; border: 1px solid #30363d; padding: 24px; border-radius: 8px; z-index: 100; }
</style>
</head>
<body>
<div class="header">
  <h1>🎬 DaVinci Resolve</h1>
  <span class="version" id="version"></span>
  <div class="status">
    <div class="dot" id="statusDot"></div>
    <span id="statusText" style="font-size:13px;">Connected</span>
    <button class="refresh-btn" onclick="loadData()">⟳ Refresh</button>
  </div>
</div>

<div id="loading">Loading from Resolve...</div>

<div class="board" id="board"></div>

<script>
let resolveData = null;

async function loadData() {
  document.getElementById('loading').style.display = 'block';
  try {
    const res = await fetch('/api/database');
    resolveData = await res.json();
    render();
    document.getElementById('statusDot').className = 'dot';
    document.getElementById('statusText').textContent = 'Connected';
  } catch(e) {
    document.getElementById('statusDot').className = 'dot off';
    document.getElementById('statusText').textContent = 'Disconnected';
  }
  document.getElementById('loading').style.display = 'none';
}

function render() {
  if (!resolveData) return;
  
  document.getElementById('version').textContent = 
    resolveData.product + ' ' + resolveData.version + ' — Page: ' + (resolveData.currentPage || 'N/A');
  
  const board = document.getElementById('board');
  board.innerHTML = '';
  
  // Column 1: Projects
  const projCol = makeColumn('Projects', resolveData.projects.length);
  for (const proj of resolveData.projects) {
    const card = document.createElement('div');
    card.className = 'card project-card';
    card.innerHTML = `
      <div class="card-title">${proj.isCurrent ? '▶ ' : ''}${proj.name}</div>
      <div class="card-meta">
        <span class="tag blue">${proj.timelines.length} timeline${proj.timelines.length !== 1 ? 's' : ''}</span>
        <span class="tag orange">${proj.mediaPool.clipCount} clips</span>
        <span class="tag purple">${proj.renderJobs.length} render jobs</span>
        ${proj.isCurrent ? '<span class="tag green">Active</span>' : ''}
      </div>
    `;
    projCol.body.appendChild(card);
  }
  board.appendChild(projCol.el);
  
  // Column 2: Timelines (from current/all projects)
  const allTimelines = [];
  for (const proj of resolveData.projects) {
    for (const tl of proj.timelines) {
      allTimelines.push({...tl, projectName: proj.name});
    }
  }
  
  const tlCol = makeColumn('Timelines', allTimelines.length);
  for (const tl of allTimelines) {
    const card = document.createElement('div');
    card.className = 'card timeline-card';
    const mins = Math.floor(tl.durationSeconds / 60);
    const secs = Math.round(tl.durationSeconds % 60);
    card.innerHTML = `
      <div class="card-title">${tl.name}</div>
      <div class="card-meta">
        <span class="tag">${tl.projectName}</span>
        <span class="tag green">${mins}:${secs.toString().padStart(2,'0')}</span>
        <span class="tag">V${tl.videoTracks} A${tl.audioTracks}</span>
        <span class="tag blue">${tl.clips.length} clips</span>
        <span class="tag">${tl.fps} fps</span>
      </div>
      ${tl.clips.length > 0 ? `
      <div class="clips-list" id="tl-${tl.index}" style="display:none">
        ${tl.clips.map(c => `
          <div class="clip">
            <span>${c.name}</span>
            <span style="color:#8b949e">${c.duration}f</span>
          </div>
        `).join('')}
      </div>
      <div class="expand-btn" onclick="toggle('tl-${tl.index}',this)">▶ Show clips</div>
      ` : ''}
    `;
    tlCol.body.appendChild(card);
  }
  board.appendChild(tlCol.el);
  
  // Column 3: Media Pool
  const mediaCol = makeColumn('Media Pool', 0);
  for (const proj of resolveData.projects) {
    if (!proj.mediaPool.folders.length) continue;
    renderFolder(proj.mediaPool.folders[0], mediaCol.body, proj.name);
  }
  // Update count
  mediaCol.el.querySelector('.count').textContent = 
    resolveData.projects.reduce((a, p) => a + p.mediaPool.clipCount, 0);
  board.appendChild(mediaCol.el);
  
  // Column 4: Render Jobs
  const allJobs = [];
  for (const proj of resolveData.projects) {
    for (const job of proj.renderJobs) {
      allJobs.push({...job, projectName: proj.name});
    }
  }
  
  const rjCol = makeColumn('Render Jobs', allJobs.length);
  if (allJobs.length === 0) {
    rjCol.body.innerHTML = '<div class="empty">No render jobs queued</div>';
  }
  for (const job of allJobs) {
    const card = document.createElement('div');
    card.className = 'card render-card';
    const status = job.JobStatus || 'Unknown';
    const pct = job.CompletionPercentage || 0;
    const statusClass = status === 'Complete' ? 'green' : status === 'Failed' ? 'red' : 'blue';
    card.innerHTML = `
      <div class="card-title">${job.TargetDir ? job.TargetDir.split('/').pop() : 'Render Job'}</div>
      <div class="card-meta">
        <span class="tag">${job.projectName}</span>
        <span class="tag ${statusClass}">${status} ${pct}%</span>
        ${job.FormatWidth ? `<span class="tag">${job.FormatWidth}x${job.FormatHeight}</span>` : ''}
        ${job.RenderJobName ? `<span class="tag">${job.RenderJobName}</span>` : ''}
      </div>
    `;
    rjCol.body.appendChild(card);
  }
  board.appendChild(rjCol.el);
}

function renderFolder(folder, container, projectName) {
  // Render clips in this folder
  if (folder.clips && folder.clips.length > 0) {
    const card = document.createElement('div');
    card.className = 'card media-card';
    card.innerHTML = `
      <div class="card-title">📁 ${folder.name || 'Root'} <span style="color:#8b949e;font-weight:normal;font-size:12px">(${projectName})</span></div>
      <div class="card-meta">
        <span class="tag orange">${folder.clips.length} clips</span>
      </div>
      <div class="clips-list">
        ${folder.clips.slice(0, 5).map(c => `
          <div class="clip">
            <span>${c.name}</span>
            <span style="color:#8b949e">${c.resolution || ''}</span>
          </div>
        `).join('')}
        ${folder.clips.length > 5 ? `<div style="color:#8b949e;font-size:11px;padding-top:4px">+ ${folder.clips.length - 5} more</div>` : ''}
      </div>
    `;
    container.appendChild(card);
  }
  
  // Recurse into subfolders
  if (folder.subfolders) {
    for (const sub of folder.subfolders) {
      renderFolder(sub, container, projectName);
    }
  }
}

function makeColumn(title, count) {
  const el = document.createElement('div');
  el.className = 'column';
  el.innerHTML = `
    <div class="column-header">
      <h2>${title}</h2>
      <span class="count">${count}</span>
    </div>
  `;
  const body = document.createElement('div');
  body.className = 'column-body';
  el.appendChild(body);
  return { el, body };
}

function toggle(id, btn) {
  const el = document.getElementById(id);
  if (el.style.display === 'none') {
    el.style.display = 'block';
    btn.textContent = '▼ Hide clips';
  } else {
    el.style.display = 'none';
    btn.textContent = '▶ Show clips';
  }
}

// Auto-refresh every 30s
loadData();
setInterval(loadData, 30000);
</script>
</body>
</html>"""


class ResolveHandler(SimpleHTTPRequestHandler):
    """HTTP handler that serves the dashboard and API."""

    def do_GET(self):
        parsed = urlparse(self.path)
        
        if parsed.path == "/" or parsed.path == "/dashboard":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(DASHBOARD_HTML.encode())
        
        elif parsed.path == "/api/database":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            data = get_full_database()
            self.wfile.write(json.dumps(data, indent=2, default=str).encode())
        
        elif parsed.path == "/api/status":
            resolve = get_resolve()
            status = {
                "connected": resolve is not None,
                "product": resolve.GetProductName() if resolve else None,
                "version": resolve.GetVersionString() if resolve else None,
                "page": resolve.GetCurrentPage() if resolve else None,
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(status).encode())
        
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found")

    def log_message(self, format, *args):
        # Quiet logging
        pass


def run_server(port=8080):
    server = HTTPServer(("0.0.0.0", port), ResolveHandler)
    print(f"Dashboard: http://localhost:{port}")
    print(f"API:       http://localhost:{port}/api/database")
    server.serve_forever()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    run_server(port)
