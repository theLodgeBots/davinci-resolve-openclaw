#!/usr/bin/env python3
"""
DaVinci Resolve OpenClaw - System Health Check
Comprehensive status verification for production deployment
"""

import json
import os
import sys
import subprocess
from pathlib import Path
import time
from datetime import datetime

class SystemHealthChecker:
    def __init__(self):
        self.checks_passed = 0
        self.checks_failed = 0
        self.warnings = 0
        
    def print_header(self, title):
        print(f"\n{'=' * 50}")
        print(f"🔍 {title}")
        print(f"{'=' * 50}")
        
    def check_pass(self, message):
        print(f"✅ {message}")
        self.checks_passed += 1
        
    def check_fail(self, message):
        print(f"❌ {message}")
        self.checks_failed += 1
        
    def check_warn(self, message):
        print(f"⚠️  {message}")
        self.warnings += 1
        
    def check_davinci_resolve(self):
        """Verify DaVinci Resolve connection and project status"""
        self.print_header("DaVinci Resolve Integration")
        
        try:
            result = subprocess.run(['python3', 'resolve_bridge.py'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                output = result.stdout
                if "DaVinci Resolve Studio" in output:
                    self.check_pass("DaVinci Resolve connected successfully")
                    if "nycap-portalcam" in output:
                        self.check_pass("Test project (nycap-portalcam) loaded")
                    else:
                        self.check_warn("Test project not currently loaded")
                else:
                    self.check_fail("DaVinci Resolve connection unstable")
            else:
                self.check_fail(f"DaVinci Resolve connection failed: {result.stderr}")
        except subprocess.TimeoutExpired:
            self.check_fail("DaVinci Resolve connection timeout")
        except Exception as e:
            self.check_fail(f"DaVinci Resolve test error: {str(e)}")
    
    def check_test_data(self):
        """Verify test footage and processing results"""
        self.print_header("Test Data Verification")
        
        test_dir = Path("/Volumes/LaCie/VIDEO/nycap-portalcam")
        
        # Check if test directory exists
        if not test_dir.exists():
            self.check_fail("Test footage directory not found")
            return
        else:
            self.check_pass("Test footage directory accessible")
        
        # Check core data files
        core_files = [
            "manifest.json",
            "project_diarization.json", 
            "scene_analysis.json",
            "nycap-portalcam_color_grading.json"
        ]
        
        for file_name in core_files:
            file_path = test_dir / file_name
            if file_path.exists():
                try:
                    with open(file_path, 'r') as f:
                        json.load(f)  # Verify valid JSON
                    self.check_pass(f"{file_name} - Valid")
                except json.JSONDecodeError:
                    self.check_fail(f"{file_name} - Corrupted JSON")
            else:
                self.check_fail(f"{file_name} - Missing")
        
        # Check transcript files
        transcript_dir = test_dir / "_transcripts"
        if transcript_dir.exists():
            transcripts = list(transcript_dir.glob("*.json"))
            if len(transcripts) >= 20:  # Should have ~26
                self.check_pass(f"Transcripts: {len(transcripts)} files (good coverage)")
            elif len(transcripts) >= 10:
                self.check_warn(f"Transcripts: {len(transcripts)} files (partial coverage)")
            else:
                self.check_fail(f"Transcripts: {len(transcripts)} files (poor coverage)")
        else:
            self.check_fail("Transcript directory missing")
    
    def check_render_outputs(self):
        """Verify rendered video outputs"""
        self.print_header("Render Output Verification")
        
        render_dir = Path("renders")
        if not render_dir.exists():
            self.check_fail("Renders directory not found")
            return
        
        video_files = list(render_dir.glob("*.mp4"))
        if len(video_files) >= 3:
            self.check_pass(f"Video outputs: {len(video_files)} files generated")
        elif len(video_files) >= 1:
            self.check_warn(f"Video outputs: {len(video_files)} files (minimal)")
        else:
            self.check_fail("No video outputs found")
        
        # Check file sizes (should be reasonable)
        for video_file in video_files:
            size_mb = video_file.stat().st_size / (1024 * 1024)
            if size_mb > 1:  # At least 1MB
                self.check_pass(f"{video_file.name}: {size_mb:.1f} MB")
            else:
                self.check_warn(f"{video_file.name}: {size_mb:.1f} MB (very small)")
        
        # Check for HTML gallery
        gallery_file = render_dir / "index.html"
        if gallery_file.exists():
            self.check_pass("Video gallery (index.html) available")
        else:
            self.check_warn("Video gallery not generated")
    
    def check_python_environment(self):
        """Verify Python environment and dependencies"""
        self.print_header("Python Environment")
        
        # Check Python version
        py_version = sys.version_info
        if py_version.major == 3 and py_version.minor >= 8:
            self.check_pass(f"Python {py_version.major}.{py_version.minor} (compatible)")
        else:
            self.check_fail(f"Python {py_version.major}.{py_version.minor} (needs 3.8+)")
        
        # Check key imports
        required_modules = [
            'json', 'subprocess', 'pathlib', 'openai', 'requests'
        ]
        
        for module in required_modules:
            try:
                __import__(module)
                self.check_pass(f"Module '{module}' imported successfully")
            except ImportError:
                self.check_fail(f"Module '{module}' missing")
    
    def check_external_dependencies(self):
        """Check external tools and APIs"""
        self.print_header("External Dependencies")
        
        # Check ffprobe (for video metadata)
        try:
            result = subprocess.run(['ffprobe', '-version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                self.check_pass("ffprobe available")
            else:
                self.check_fail("ffprobe not working")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            self.check_fail("ffprobe not found (install FFmpeg)")
        
        # Check OpenAI API key (without making actual call)
        openai_key = os.getenv('OPENAI_API_KEY')
        if openai_key:
            if openai_key.startswith('sk-'):
                self.check_pass("OpenAI API key configured")
            else:
                self.check_warn("OpenAI API key format looks incorrect")
        else:
            self.check_fail("OpenAI API key not set (OPENAI_API_KEY)")
    
    def check_system_resources(self):
        """Check disk space and system resources"""
        self.print_header("System Resources")
        
        # Check current directory disk space
        try:
            statvfs = os.statvfs('.')
            free_gb = (statvfs.f_frsize * statvfs.f_available) / (1024**3)
            if free_gb > 10:
                self.check_pass(f"Disk space: {free_gb:.1f} GB free")
            elif free_gb > 5:
                self.check_warn(f"Disk space: {free_gb:.1f} GB free (getting low)")
            else:
                self.check_fail(f"Disk space: {free_gb:.1f} GB free (critically low)")
        except Exception:
            self.check_warn("Could not check disk space")
        
        # Check for LaCie drive (where test footage lives)
        lacie_path = Path("/Volumes/LaCie")
        if lacie_path.exists():
            self.check_pass("LaCie drive mounted")
        else:
            self.check_warn("LaCie drive not mounted (test footage inaccessible)")
    
    def run_full_check(self):
        """Run comprehensive system health check"""
        print(f"🎬 DaVinci Resolve OpenClaw - System Health Check")
        print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📁 Working Directory: {os.getcwd()}")
        
        # Run all checks
        self.check_python_environment()
        self.check_external_dependencies()
        self.check_system_resources()
        self.check_davinci_resolve()
        self.check_test_data()
        self.check_render_outputs()
        
        # Summary
        self.print_header("HEALTH CHECK SUMMARY")
        total_checks = self.checks_passed + self.checks_failed + self.warnings
        
        print(f"✅ Passed: {self.checks_passed}")
        print(f"⚠️  Warnings: {self.warnings}")
        print(f"❌ Failed: {self.checks_failed}")
        print(f"📊 Total: {total_checks} checks")
        
        if self.checks_failed == 0:
            if self.warnings == 0:
                print(f"\n🎉 SYSTEM STATUS: EXCELLENT")
                print("All systems operational - ready for production!")
                return 0
            else:
                print(f"\n✅ SYSTEM STATUS: GOOD")
                print("System functional with minor warnings - production ready!")
                return 1
        else:
            print(f"\n⚠️  SYSTEM STATUS: ISSUES DETECTED")
            print(f"System has {self.checks_failed} critical issues that need attention.")
            return 2

def main():
    checker = SystemHealthChecker()
    return checker.run_full_check()

if __name__ == "__main__":
    sys.exit(main())