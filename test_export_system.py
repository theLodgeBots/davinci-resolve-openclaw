#!/usr/bin/env python3
"""
🧪 Test Suite for Automated Social Export System
Validates the export system without requiring DaVinci Resolve connection.
"""

import json
import sys
from pathlib import Path
from datetime import datetime

def test_analysis_data_loading():
    """Test loading of analysis data"""
    print("🧪 Testing analysis data loading...")
    
    # Find most recent analysis folder
    social_clips_dir = Path("social_clips")
    if not social_clips_dir.exists():
        print("❌ No social_clips directory found")
        return False
        
    folders = [f for f in social_clips_dir.iterdir() if f.is_dir()]
    if not folders:
        print("❌ No analysis folders found")
        return False
        
    analysis_folder = max(folders, key=lambda x: x.stat().st_mtime)
    print(f"📁 Using: {analysis_folder}")
    
    # Test strategy loading
    strategy_path = analysis_folder / "export_strategy.json"
    if not strategy_path.exists():
        print("❌ Export strategy file missing")
        return False
        
    try:
        with open(strategy_path, 'r') as f:
            strategy = json.load(f)
        print(f"✅ Loaded export strategy: {strategy['total_export_jobs']} jobs")
    except Exception as e:
        print(f"❌ Error loading strategy: {e}")
        return False
    
    # Test presets loading  
    presets_path = analysis_folder / "render_presets_used.json"
    if not presets_path.exists():
        print("❌ Render presets file missing")
        return False
        
    try:
        with open(presets_path, 'r') as f:
            presets = json.load(f)
        print(f"✅ Loaded render presets: {len(presets['presets'])} presets")
    except Exception as e:
        print(f"❌ Error loading presets: {e}")
        return False
        
    return strategy, presets

def test_export_job_enumeration(strategy, presets):
    """Test export job enumeration and validation"""
    print("\n🧪 Testing export job enumeration...")
    
    total_jobs = 0
    valid_jobs = 0
    
    for clip in strategy["exports"]:
        if not clip["export_variants"]:
            print(f"⚠️  No variants for clip: {clip['clip_name']}")
            continue
            
        for variant in clip["export_variants"]:
            total_jobs += 1
            preset_name = variant["preset"]
            
            # Validate preset exists
            if preset_name not in presets["presets"]:
                print(f"❌ Missing preset: {preset_name}")
                continue
                
            preset_config = presets["presets"][preset_name]
            print(f"✅ Valid job: {clip['clip_name']} → {preset_config['name']}")
            valid_jobs += 1
    
    print(f"📊 Export Jobs: {valid_jobs}/{total_jobs} valid")
    return valid_jobs == total_jobs

def test_render_preset_structure(presets):
    """Test render preset structure and completeness"""
    print("\n🧪 Testing render preset structure...")
    
    required_fields = ["name", "format", "codec", "resolution", "framerate", "bitrate_video", "platforms"]
    
    for preset_name, preset_config in presets["presets"].items():
        print(f"🔍 Validating preset: {preset_name}")
        
        # Check required fields
        missing_fields = []
        for field in required_fields:
            if field not in preset_config:
                missing_fields.append(field)
                
        if missing_fields:
            print(f"❌ Missing fields in {preset_name}: {missing_fields}")
            return False
            
        # Check resolution structure
        if "resolution" in preset_config:
            if "width" not in preset_config["resolution"] or "height" not in preset_config["resolution"]:
                print(f"❌ Invalid resolution structure in {preset_name}")
                return False
                
        print(f"✅ {preset_name}: {preset_config['resolution']['width']}x{preset_config['resolution']['height']}")
    
    return True

def test_timeline_naming_convention(strategy):
    """Test timeline naming convention"""
    print("\n🧪 Testing timeline naming convention...")
    
    timeline_names = set()
    
    for clip in strategy["exports"]:
        for variant in clip["export_variants"]:
            timeline_name = f"Social - {clip['clip_name']} - {variant['preset']}"
            
            if timeline_name in timeline_names:
                print(f"❌ Duplicate timeline name: {timeline_name}")
                return False
                
            timeline_names.add(timeline_name)
            print(f"✅ Timeline: {timeline_name}")
    
    print(f"📊 Timeline Names: {len(timeline_names)} unique names generated")
    return True

def test_export_system_readiness():
    """Comprehensive test of export system readiness"""
    print("🎬 DaVinci Resolve OpenClaw - Export System Test Suite")
    print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Test 1: Analysis Data Loading
    result = test_analysis_data_loading()
    if not result:
        return False
        
    strategy, presets = result
    
    # Test 2: Export Job Enumeration
    if not test_export_job_enumeration(strategy, presets):
        return False
    
    # Test 3: Render Preset Structure
    if not test_render_preset_structure(presets):
        return False
        
    # Test 4: Timeline Naming Convention
    if not test_timeline_naming_convention(strategy):
        return False
    
    print("\n" + "=" * 60)
    print("🎯 TEST RESULTS SUMMARY")
    print("✅ All tests passed!")
    print("✅ Export system is ready for DaVinci Resolve API integration")
    print("✅ All presets validated and properly structured")
    print("✅ Timeline naming convention prevents conflicts")
    
    # Generate test report
    test_report = {
        "test_run": {
            "timestamp": datetime.now().isoformat(),
            "strategy_file": str(strategy.get("timeline_name", "Unknown")),
            "total_clips": len(strategy["exports"]),
            "total_export_jobs": strategy["total_export_jobs"],
            "total_presets": len(presets["presets"]),
            "all_tests_passed": True
        }
    }
    
    # Find analysis folder again for report
    social_clips_dir = Path("social_clips")
    folders = [f for f in social_clips_dir.iterdir() if f.is_dir()]
    analysis_folder = max(folders, key=lambda x: x.stat().st_mtime)
    
    report_path = analysis_folder / "export_system_test_report.json"
    with open(report_path, 'w') as f:
        json.dump(test_report, f, indent=2)
    
    print(f"📄 Test report saved: {report_path}")
    print("\n🚀 Ready for live testing with DaVinci Resolve!")
    
    return True

if __name__ == "__main__":
    success = test_export_system_readiness()
    sys.exit(0 if success else 1)