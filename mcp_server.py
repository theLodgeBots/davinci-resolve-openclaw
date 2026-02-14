#!/usr/bin/env python3
"""MCP Server for DaVinci Resolve OpenClaw Integration.

Exposes video editing pipeline as tools for OpenClaw agents.
"""

import json
import os
import sys
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional

# MCP imports (placeholder - would need actual MCP SDK)
# from mcp import Server, Tool, types

from ingest import scan_folder, save_manifest
from transcribe import transcribe_project
from script_engine import generate_edit_plan
from script_engine_enhanced import generate_enhanced_edit_plan
from timeline_builder import build_timeline_from_plan
from analyze_usage import analyze_clip_usage
from resolve_bridge import get_resolve, get_project_manager


class DaVinciResolveMCP:
    """MCP Server for DaVinci Resolve video editing operations."""
    
    def __init__(self):
        self.name = "davinci-resolve"
        self.version = "1.0.0"
        self.description = "AI video editing pipeline with DaVinci Resolve integration"
        
    async def list_tools(self) -> List[Dict[str, Any]]:
        """Return available tools."""
        return [
            {
                "name": "ingest_footage",
                "description": "Scan a folder and extract metadata from video files",
                "inputSchema": {
                    "type": "object", 
                    "properties": {
                        "folder_path": {
                            "type": "string",
                            "description": "Path to folder containing video files"
                        }
                    },
                    "required": ["folder_path"]
                }
            },
            {
                "name": "transcribe_footage", 
                "description": "Extract audio and generate transcripts for all clips",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "manifest_path": {
                            "type": "string", 
                            "description": "Path to manifest.json file"
                        }
                    },
                    "required": ["manifest_path"]
                }
            },
            {
                "name": "generate_edit_script",
                "description": "Create an AI-generated edit plan from transcripts",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "manifest_path": {"type": "string", "description": "Path to manifest.json"},
                        "transcripts_dir": {"type": "string", "description": "Directory with transcript files"},
                        "style": {"type": "string", "enum": ["basic", "enhanced"], "default": "enhanced"},
                        "output_path": {"type": "string", "description": "Output path for edit plan (optional)"}
                    },
                    "required": ["manifest_path", "transcripts_dir"]
                }
            },
            {
                "name": "build_timeline",
                "description": "Build a DaVinci Resolve timeline from an edit plan", 
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "edit_plan_path": {"type": "string", "description": "Path to edit_plan.json"},
                        "manifest_path": {"type": "string", "description": "Path to manifest.json"},
                        "project_name": {"type": "string", "description": "Custom project name (optional)"}
                    },
                    "required": ["edit_plan_path", "manifest_path"]
                }
            },
            {
                "name": "analyze_footage_usage",
                "description": "Analyze which clips are used vs available in an edit plan",
                "inputSchema": {
                    "type": "object", 
                    "properties": {
                        "manifest_path": {"type": "string", "description": "Path to manifest.json"},
                        "edit_plan_path": {"type": "string", "description": "Path to edit_plan.json"}
                    },
                    "required": ["manifest_path", "edit_plan_path"]
                }
            },
            {
                "name": "list_resolve_projects",
                "description": "List available DaVinci Resolve projects",
                "inputSchema": {"type": "object", "properties": {}}
            },
            {
                "name": "get_project_status", 
                "description": "Get timeline and media information for a project",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project_name": {"type": "string", "description": "DaVinci Resolve project name"}
                    },
                    "required": ["project_name"]
                }
            },
            {
                "name": "run_full_pipeline",
                "description": "Complete video editing pipeline: ingest → transcribe → script → timeline",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "folder_path": {"type": "string", "description": "Folder with video files"},
                        "style": {"type": "string", "enum": ["basic", "enhanced"], "default": "enhanced"},
                        "project_name": {"type": "string", "description": "Custom project name (optional)"}
                    },
                    "required": ["folder_path"]
                }
            }
        ]
    
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool call."""
        try:
            if name == "ingest_footage":
                return await self._ingest_footage(arguments)
            elif name == "transcribe_footage":
                return await self._transcribe_footage(arguments)
            elif name == "generate_edit_script":
                return await self._generate_edit_script(arguments)
            elif name == "build_timeline": 
                return await self._build_timeline(arguments)
            elif name == "analyze_footage_usage":
                return await self._analyze_footage_usage(arguments)
            elif name == "list_resolve_projects":
                return await self._list_resolve_projects(arguments)
            elif name == "get_project_status":
                return await self._get_project_status(arguments)
            elif name == "run_full_pipeline":
                return await self._run_full_pipeline(arguments)
            else:
                return {"error": f"Unknown tool: {name}"}
                
        except Exception as e:
            return {"error": f"Tool execution failed: {str(e)}"}
    
    async def _ingest_footage(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Ingest footage from a folder."""
        folder_path = args["folder_path"]
        if not os.path.exists(folder_path):
            return {"error": f"Folder does not exist: {folder_path}"}
        
        manifest = scan_folder(folder_path)
        manifest_path = os.path.join(folder_path, "manifest.json")
        save_manifest(manifest, manifest_path)
        
        return {
            "success": True,
            "manifest_path": manifest_path,
            "total_clips": manifest["total_clips"],
            "total_duration_minutes": manifest["total_duration_minutes"],
            "sources": manifest["sources"]
        }
    
    async def _transcribe_footage(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Transcribe footage using Whisper API."""
        manifest_path = args["manifest_path"]
        if not os.path.exists(manifest_path):
            return {"error": f"Manifest not found: {manifest_path}"}
            
        transcripts = transcribe_project(manifest_path)
        transcripts_dir = os.path.join(os.path.dirname(manifest_path), "_transcripts")
        
        return {
            "success": True,
            "transcripts_count": len(transcripts),
            "transcripts_dir": transcripts_dir,
            "transcribed_clips": list(transcripts.keys())
        }
    
    async def _generate_edit_script(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Generate an edit script with AI."""
        manifest_path = args["manifest_path"]
        transcripts_dir = args["transcripts_dir"] 
        style = args.get("style", "enhanced")
        output_path = args.get("output_path")
        
        if style == "enhanced":
            edit_plan = generate_enhanced_edit_plan(manifest_path, transcripts_dir, output_path)
        else:
            edit_plan = generate_edit_plan(manifest_path, transcripts_dir, output_path)
            
        if not edit_plan:
            return {"error": "Failed to generate edit plan"}
        
        sections = len(edit_plan.get("sections", []))
        total_clips = sum(len(s.get("clips", [])) for s in edit_plan.get("sections", []))
        broll_clips = sum(1 for s in edit_plan.get("sections", []) for c in s.get("clips", []) if c.get("role") == "broll")
        
        return {
            "success": True,
            "title": edit_plan.get("title", "Untitled"),
            "sections": sections,
            "total_clips": total_clips,
            "broll_clips": broll_clips,
            "broll_percentage": round(broll_clips/total_clips*100, 1) if total_clips > 0 else 0,
            "estimated_duration_seconds": edit_plan.get("estimated_duration_seconds"),
            "edit_plan_path": output_path or os.path.join(os.path.dirname(manifest_path), f"edit_plan{'_enhanced' if style=='enhanced' else ''}.json")
        }
    
    async def _build_timeline(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Build a timeline in DaVinci Resolve."""
        edit_plan_path = args["edit_plan_path"]
        manifest_path = args["manifest_path"]
        project_name = args.get("project_name")
        
        # Test Resolve connection first
        resolve = get_resolve()
        if not resolve:
            return {"error": "Cannot connect to DaVinci Resolve. Is it running?"}
        
        try:
            timeline = build_timeline_from_plan(edit_plan_path, manifest_path, project_name)
            if timeline:
                return {
                    "success": True,
                    "timeline_name": timeline.GetName(),
                    "video_tracks": timeline.GetTrackCount('video'),
                    "audio_tracks": timeline.GetTrackCount('audio'),
                    "project_saved": True
                }
            else:
                return {"error": "Failed to create timeline"}
        except Exception as e:
            return {"error": f"Timeline creation failed: {str(e)}"}
    
    async def _analyze_footage_usage(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze footage usage."""
        # This would need to capture the output from analyze_usage.py
        # For now, return basic analysis
        try:
            with open(args["manifest_path"]) as f:
                manifest = json.load(f)
            with open(args["edit_plan_path"]) as f:
                plan = json.load(f)
            
            all_clips = len(manifest["clips"])
            used_clips = set()
            for section in plan.get("sections", []):
                for clip_info in section.get("clips", []):
                    used_clips.add(clip_info["filename"])
            
            return {
                "success": True,
                "total_clips": all_clips,
                "used_clips": len(used_clips),
                "unused_clips": all_clips - len(used_clips),
                "usage_percentage": round(len(used_clips)/all_clips*100, 1)
            }
        except Exception as e:
            return {"error": f"Analysis failed: {str(e)}"}
    
    async def _list_resolve_projects(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List DaVinci Resolve projects."""
        resolve = get_resolve()
        if not resolve:
            return {"error": "Cannot connect to DaVinci Resolve"}
        
        try:
            pm = get_project_manager(resolve)
            # Note: Resolve API doesn't have a direct "list all projects" method
            # This would need to be implemented by trying to load known projects
            # or using database queries
            return {
                "success": True,
                "note": "Project listing requires manual implementation - Resolve API limitation",
                "current_project": resolve.GetProjectManager().GetCurrentProject().GetName() if resolve.GetProjectManager().GetCurrentProject() else None
            }
        except Exception as e:
            return {"error": f"Failed to list projects: {str(e)}"}
    
    async def _get_project_status(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get project status information."""
        resolve = get_resolve()
        if not resolve:
            return {"error": "Cannot connect to DaVinci Resolve"}
        
        try:
            pm = get_project_manager(resolve)
            project = pm.LoadProject(args["project_name"])
            if not project:
                return {"error": f"Project not found: {args['project_name']}"}
            
            timeline_count = project.GetTimelineCount()
            timelines = []
            for i in range(1, timeline_count + 1):
                tl = project.GetTimelineByIndex(i)
                if tl:
                    timelines.append({
                        "name": tl.GetName(),
                        "video_tracks": tl.GetTrackCount('video'),
                        "audio_tracks": tl.GetTrackCount('audio')
                    })
            
            return {
                "success": True,
                "project_name": project.GetName(),
                "timeline_count": timeline_count,
                "timelines": timelines
            }
        except Exception as e:
            return {"error": f"Failed to get project status: {str(e)}"}
    
    async def _run_full_pipeline(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Run the complete editing pipeline."""
        folder_path = args["folder_path"]
        style = args.get("style", "enhanced")
        project_name = args.get("project_name")
        
        results = {}
        
        # Step 1: Ingest
        ingest_result = await self._ingest_footage({"folder_path": folder_path})
        if "error" in ingest_result:
            return ingest_result
        results["ingest"] = ingest_result
        
        # Step 2: Transcribe
        transcribe_result = await self._transcribe_footage({
            "manifest_path": ingest_result["manifest_path"]
        })
        if "error" in transcribe_result:
            return transcribe_result
        results["transcribe"] = transcribe_result
        
        # Step 3: Generate edit script
        script_result = await self._generate_edit_script({
            "manifest_path": ingest_result["manifest_path"],
            "transcripts_dir": transcribe_result["transcripts_dir"],
            "style": style
        })
        if "error" in script_result:
            return script_result
        results["script"] = script_result
        
        # Step 4: Build timeline
        timeline_result = await self._build_timeline({
            "edit_plan_path": script_result["edit_plan_path"],
            "manifest_path": ingest_result["manifest_path"],
            "project_name": project_name
        })
        if "error" in timeline_result:
            return timeline_result
        results["timeline"] = timeline_result
        
        return {
            "success": True,
            "pipeline": "complete",
            "folder": os.path.basename(folder_path),
            "clips": ingest_result["total_clips"],
            "duration_minutes": ingest_result["total_duration_minutes"],
            "edit_style": style,
            "timeline_name": timeline_result["timeline_name"],
            "results": results
        }


# MCP Server startup (would need actual MCP framework)
async def main():
    """Start the MCP server."""
    server = DaVinciResolveMCP()
    print(f"🎬 {server.name} v{server.version}")
    print(f"   {server.description}")
    print(f"   Available tools: {len(await server.list_tools())}")
    print("   Ready for OpenClaw integration!")
    
    # In a real MCP implementation, this would start the server
    # and listen for tool calls from OpenClaw
    
if __name__ == "__main__":
    asyncio.run(main())