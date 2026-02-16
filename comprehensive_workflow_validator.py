#!/usr/bin/env python3
"""
🔍 Comprehensive Workflow Validator for DaVinci Resolve OpenClaw
Provides end-to-end validation, performance metrics, and quality assurance.

This validator tests every component of the pipeline and provides detailed
reports for both technical validation and client demonstrations.
"""

import json
import os
import time
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass, asdict
import hashlib

@dataclass
class ValidationResult:
    """Single validation test result"""
    test_name: str
    category: str
    status: str  # "passed", "failed", "warning", "skipped"
    duration_ms: int
    message: str
    details: Optional[Dict[str, Any]] = None
    performance_metrics: Optional[Dict[str, Any]] = None

@dataclass
class WorkflowReport:
    """Complete workflow validation report"""
    timestamp: str
    total_tests: int
    passed: int
    failed: int
    warnings: int
    skipped: int
    total_duration_ms: int
    overall_status: str
    results: List[ValidationResult]
    performance_summary: Dict[str, Any]
    recommendations: List[str]

class ComprehensiveWorkflowValidator:
    def __init__(self):
        self.results = []
        self.start_time = time.time()
        self.performance_data = {}
        
    def run_timed_test(self, test_name: str, category: str, test_func, *args, **kwargs) -> ValidationResult:
        """Run a test with timing and error handling"""
        start_ms = int(time.time() * 1000)
        
        try:
            result = test_func(*args, **kwargs)
            end_ms = int(time.time() * 1000)
            duration = end_ms - start_ms
            
            if isinstance(result, tuple):
                status, message, details, perf_metrics = result
            else:
                status, message, details, perf_metrics = result, "Test completed", None, None
                
            return ValidationResult(
                test_name=test_name,
                category=category,
                status=status,
                duration_ms=duration,
                message=message,
                details=details,
                performance_metrics=perf_metrics
            )
            
        except Exception as e:
            end_ms = int(time.time() * 1000)
            duration = end_ms - start_ms
            
            return ValidationResult(
                test_name=test_name,
                category=category,
                status="failed",
                duration_ms=duration,
                message=f"Test failed with exception: {str(e)}",
                details={"exception": str(e), "type": type(e).__name__}
            )
    
    def validate_environment(self) -> Tuple[str, str, Dict, Dict]:
        """Validate Python environment and dependencies"""
        details = {}
        perf_metrics = {}
        
        # Check Python version
        import sys
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        details["python_version"] = python_version
        
        # Check critical modules
        critical_modules = ["json", "subprocess", "pathlib", "openai", "requests"]
        missing_modules = []
        
        for module in critical_modules:
            try:
                __import__(module)
                details[f"module_{module}"] = "available"
            except ImportError:
                missing_modules.append(module)
                details[f"module_{module}"] = "missing"
        
        if missing_modules:
            return "failed", f"Missing critical modules: {missing_modules}", details, perf_metrics
        else:
            return "passed", f"All {len(critical_modules)} critical modules available", details, perf_metrics
    
    def validate_external_tools(self) -> Tuple[str, str, Dict, Dict]:
        """Validate external tools and APIs"""
        details = {}
        perf_metrics = {}
        warnings = []
        
        # Check ffprobe
        try:
            result = subprocess.run(["ffprobe", "-version"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                details["ffprobe"] = "available"
                # Extract version from output
                version_line = result.stdout.split('\n')[0]
                details["ffprobe_version"] = version_line
            else:
                details["ffprobe"] = "error"
                warnings.append("ffprobe returned non-zero exit code")
        except Exception as e:
            details["ffprobe"] = f"unavailable: {str(e)}"
            warnings.append("ffprobe not accessible")
        
        # Check OpenAI API key
        api_key = os.environ.get('OPENAI_API_KEY')
        if api_key:
            details["openai_api_key"] = "configured"
            perf_metrics["api_key_length"] = len(api_key)
        else:
            details["openai_api_key"] = "missing"
            warnings.append("OpenAI API key not configured")
        
        status = "warning" if warnings else "passed"
        message = f"External tools check completed with {len(warnings)} warnings" if warnings else "All external tools available"
        
        if warnings:
            details["warnings"] = warnings
            
        return status, message, details, perf_metrics
    
    def validate_test_data(self) -> Tuple[str, str, Dict, Dict]:
        """Validate test data and footage availability"""
        details = {}
        perf_metrics = {}
        
        # Check test footage directory
        test_dir = Path("/Volumes/LaCie/VIDEO/nycap-portalcam/")
        if test_dir.exists():
            details["test_footage_dir"] = "available"
            
            # Count files and calculate total size
            video_files = list(test_dir.glob("*.mp4")) + list(test_dir.glob("*.mov"))
            details["video_file_count"] = len(video_files)
            
            total_size = sum(f.stat().st_size for f in video_files)
            details["total_footage_size_gb"] = round(total_size / (1024**3), 2)
            perf_metrics["footage_size_bytes"] = total_size
            
        else:
            details["test_footage_dir"] = "unavailable"
            return "failed", "Test footage directory not accessible", details, perf_metrics
        
        # Check project data files
        project_files = {
            "manifest.json": "manifest.json",
            "diarization": "project_diarization.json", 
            "scene_analysis": "scene_analysis.json",
            "color_grading": "nycap-portalcam_color_grading.json"
        }
        
        for file_type, filename in project_files.items():
            filepath = Path(filename)
            if filepath.exists():
                details[f"project_{file_type}"] = "available"
                # Validate JSON
                try:
                    with open(filepath) as f:
                        data = json.load(f)
                    details[f"{file_type}_entries"] = len(data) if isinstance(data, (list, dict)) else 1
                except json.JSONDecodeError:
                    details[f"project_{file_type}"] = "invalid_json"
            else:
                details[f"project_{file_type}"] = "missing"
        
        return "passed", "Test data validation completed", details, perf_metrics
    
    def validate_davinci_integration(self) -> Tuple[str, str, Dict, Dict]:
        """Validate DaVinci Resolve integration"""
        details = {}
        perf_metrics = {}
        
        try:
            # Time the import
            import_start = time.time()
            sys_path = "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Resources/DaVinciResolve_Python"
            if sys_path not in os.sys.path:
                os.sys.path.append(sys_path)
                
            import DaVinciResolveScript as dvr_script
            import_duration = (time.time() - import_start) * 1000
            perf_metrics["import_duration_ms"] = import_duration
            
            # Test connection
            connection_start = time.time()
            resolve = dvr_script.scriptapp("Resolve")
            connection_duration = (time.time() - connection_start) * 1000
            perf_metrics["connection_duration_ms"] = connection_duration
            
            if resolve:
                details["davinci_connection"] = "successful"
                
                # Test project access
                project_manager = resolve.GetProjectManager()
                current_project = project_manager.GetCurrentProject()
                
                if current_project:
                    details["current_project"] = current_project.GetName()
                    
                    # Test timeline access
                    timeline_count = current_project.GetTimelineCount()
                    details["timeline_count"] = timeline_count
                    perf_metrics["timeline_count"] = timeline_count
                    
                    if timeline_count > 0:
                        current_timeline = current_project.GetCurrentTimeline()
                        if current_timeline:
                            details["current_timeline"] = current_timeline.GetName()
                            
                            # Test basic timeline operations
                            timeline_start = time.time()
                            timeline_duration = current_timeline.GetEndFrame()
                            timeline_fps = current_timeline.GetSetting("timelineFrameRate")
                            operation_duration = (time.time() - timeline_start) * 1000
                            
                            details["timeline_duration_frames"] = timeline_duration
                            details["timeline_fps"] = timeline_fps
                            perf_metrics["timeline_operation_ms"] = operation_duration
                        else:
                            details["current_timeline"] = "none_selected"
                    else:
                        details["timeline_count"] = 0
                else:
                    return "failed", "No project loaded in DaVinci Resolve", details, perf_metrics
            else:
                return "failed", "Unable to connect to DaVinci Resolve", details, perf_metrics
                
            return "passed", "DaVinci Resolve integration successful", details, perf_metrics
            
        except Exception as e:
            details["error"] = str(e)
            return "failed", f"DaVinci integration failed: {str(e)}", details, perf_metrics
    
    def validate_pipeline_components(self) -> Tuple[str, str, Dict, Dict]:
        """Validate all pipeline component scripts"""
        details = {}
        perf_metrics = {}
        warnings = []
        
        # Core pipeline scripts
        core_scripts = {
            "ingest": "ingest.py",
            "transcribe": "transcribe.py", 
            "script_engine": "script_engine_ai.py",
            "timeline_builder": "timeline_builder.py",
            "color_grading": "color_grading.py"
        }
        
        # Social media scripts
        social_scripts = {
            "social_clipper": "social_media_clipper.py",
            "automated_export": "automated_social_export.py",
            "streamlined_workflow": "streamlined_social_workflow.py",
            "enhanced_render": "enhanced_social_render.py"
        }
        
        # Web interface scripts
        web_scripts = {
            "dashboard_data": "dashboard_data.py",
            "health_check": "health_check.py"
        }
        
        all_scripts = {**core_scripts, **social_scripts, **web_scripts}
        
        for component, filename in all_scripts.items():
            filepath = Path(filename)
            if filepath.exists():
                details[f"{component}_file"] = "exists"
                
                # Check if executable
                if os.access(filepath, os.X_OK):
                    details[f"{component}_executable"] = "yes"
                else:
                    details[f"{component}_executable"] = "no"
                
                # Basic syntax check (Python compilation)
                try:
                    compile_start = time.time()
                    with open(filepath) as f:
                        compile(f.read(), filepath, 'exec')
                    compile_duration = (time.time() - compile_start) * 1000
                    perf_metrics[f"{component}_compile_ms"] = compile_duration
                    details[f"{component}_syntax"] = "valid"
                except SyntaxError as e:
                    details[f"{component}_syntax"] = f"error: {e}"
                    warnings.append(f"Syntax error in {filename}")
                
                # File size
                file_size = filepath.stat().st_size
                details[f"{component}_size_kb"] = round(file_size / 1024, 2)
                perf_metrics[f"{component}_size_bytes"] = file_size
                
            else:
                details[f"{component}_file"] = "missing"
                warnings.append(f"Missing component: {filename}")
        
        status = "warning" if warnings else "passed"
        message = f"Pipeline components validated with {len(warnings)} warnings" if warnings else f"All {len(all_scripts)} pipeline components validated"
        
        if warnings:
            details["warnings"] = warnings
        
        return status, message, details, perf_metrics
    
    def validate_output_quality(self) -> Tuple[str, str, Dict, Dict]:
        """Validate existing render outputs for quality metrics"""
        details = {}
        perf_metrics = {}
        
        renders_dir = Path("renders")
        if not renders_dir.exists():
            return "skipped", "No renders directory found", details, perf_metrics
        
        video_files = list(renders_dir.glob("*.mp4")) + list(renders_dir.glob("*.mov"))
        
        if not video_files:
            return "warning", "No video files found in renders directory", details, perf_metrics
        
        details["video_file_count"] = len(video_files)
        total_size = 0
        quality_metrics = {}
        
        for video_file in video_files:
            file_size = video_file.stat().st_size
            total_size += file_size
            
            # Get video info using ffprobe if available
            try:
                cmd = [
                    "ffprobe", "-v", "quiet", "-print_format", "json",
                    "-show_format", "-show_streams", str(video_file)
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    probe_data = json.loads(result.stdout)
                    
                    # Extract video stream info
                    video_stream = next((s for s in probe_data["streams"] if s["codec_type"] == "video"), None)
                    if video_stream:
                        file_metrics = {
                            "resolution": f"{video_stream.get('width', 0)}x{video_stream.get('height', 0)}",
                            "fps": eval(video_stream.get('avg_frame_rate', '0/1')),
                            "duration": float(probe_data["format"].get("duration", 0)),
                            "bitrate": int(probe_data["format"].get("bit_rate", 0)),
                            "codec": video_stream.get("codec_name", "unknown")
                        }
                        quality_metrics[video_file.name] = file_metrics
                        
            except Exception as e:
                details[f"{video_file.name}_probe_error"] = str(e)
        
        details["total_render_size_mb"] = round(total_size / (1024**2), 2)
        perf_metrics["total_render_size_bytes"] = total_size
        perf_metrics["average_file_size_mb"] = round((total_size / len(video_files)) / (1024**2), 2)
        
        if quality_metrics:
            details["quality_analysis"] = quality_metrics
            
            # Calculate quality scores
            resolutions = [m.get('resolution', '') for m in quality_metrics.values()]
            hd_count = len([r for r in resolutions if '1920x1080' in r or '1080x1920' in r])
            uhd_count = len([r for r in resolutions if '3840x2160' in r])
            
            perf_metrics["hd_video_count"] = hd_count
            perf_metrics["uhd_video_count"] = uhd_count
            perf_metrics["quality_score"] = round((hd_count * 1 + uhd_count * 2) / len(video_files), 2)
        
        return "passed", f"Quality validation completed for {len(video_files)} videos", details, perf_metrics
    
    def validate_social_workflow(self) -> Tuple[str, str, Dict, Dict]:
        """Test the social media workflow end-to-end"""
        details = {}
        perf_metrics = {}
        
        # Test streamlined workflow generation
        try:
            workflow_start = time.time()
            result = subprocess.run([
                "python3", "streamlined_social_workflow.py"
            ], capture_output=True, text=True, timeout=30)
            workflow_duration = (time.time() - workflow_start) * 1000
            perf_metrics["workflow_generation_ms"] = workflow_duration
            
            if result.returncode == 0:
                details["workflow_generation"] = "successful"
                
                # Find the generated directory
                workflow_dirs = list(Path("streamlined_workflow").glob("*"))
                if workflow_dirs:
                    latest_dir = max(workflow_dirs, key=lambda p: p.stat().st_mtime)
                    details["latest_workflow_dir"] = str(latest_dir)
                    
                    # Check generated files
                    expected_files = [
                        "precision_manual_guide.json",
                        "client_demo_script.md", 
                        "optimal_social_clips.json"
                    ]
                    
                    for expected_file in expected_files:
                        file_path = latest_dir / expected_file
                        if file_path.exists():
                            details[f"generated_{expected_file}"] = "exists"
                            file_size = file_path.stat().st_size
                            perf_metrics[f"{expected_file}_size_bytes"] = file_size
                        else:
                            details[f"generated_{expected_file}"] = "missing"
                else:
                    details["workflow_output"] = "no_directory_created"
            else:
                details["workflow_generation"] = "failed"
                details["workflow_error"] = result.stderr
                return "failed", "Social workflow generation failed", details, perf_metrics
                
        except Exception as e:
            details["workflow_exception"] = str(e)
            return "failed", f"Social workflow test failed: {str(e)}", details, perf_metrics
        
        return "passed", "Social workflow validation successful", details, perf_metrics
    
    def generate_performance_summary(self) -> Dict[str, Any]:
        """Generate performance summary from all test results"""
        summary = {
            "test_execution": {
                "total_tests": len(self.results),
                "total_duration_ms": int((time.time() - self.start_time) * 1000),
                "average_test_duration_ms": 0,
                "slowest_test": "",
                "fastest_test": ""
            },
            "system_performance": {},
            "quality_metrics": {},
            "resource_usage": {}
        }
        
        if self.results:
            durations = [r.duration_ms for r in self.results]
            summary["test_execution"]["average_test_duration_ms"] = sum(durations) // len(durations)
            
            slowest = max(self.results, key=lambda r: r.duration_ms)
            fastest = min(self.results, key=lambda r: r.duration_ms)
            
            summary["test_execution"]["slowest_test"] = f"{slowest.test_name} ({slowest.duration_ms}ms)"
            summary["test_execution"]["fastest_test"] = f"{fastest.test_name} ({fastest.duration_ms}ms)"
            
            # Aggregate performance metrics
            for result in self.results:
                if result.performance_metrics:
                    for key, value in result.performance_metrics.items():
                        if key not in summary["system_performance"]:
                            summary["system_performance"][key] = value
        
        return summary
    
    def generate_recommendations(self) -> List[str]:
        """Generate recommendations based on test results"""
        recommendations = []
        
        # Check for failed tests
        failed_tests = [r for r in self.results if r.status == "failed"]
        if failed_tests:
            recommendations.append(f"Address {len(failed_tests)} failed tests before production deployment")
        
        # Check for warnings
        warning_tests = [r for r in self.results if r.status == "warning"]
        if warning_tests:
            recommendations.append(f"Review {len(warning_tests)} warning conditions for optimal performance")
        
        # Performance recommendations
        slow_tests = [r for r in self.results if r.duration_ms > 5000]  # 5+ seconds
        if slow_tests:
            recommendations.append(f"Optimize {len(slow_tests)} slow-performing components")
        
        # Quality recommendations
        output_results = [r for r in self.results if r.test_name == "Output Quality Validation"]
        if output_results and output_results[0].performance_metrics:
            quality_score = output_results[0].performance_metrics.get("quality_score", 0)
            if quality_score < 1.5:
                recommendations.append("Consider increasing output quality settings for better results")
        
        # If no issues found
        if not recommendations:
            recommendations.append("System performing optimally - ready for production deployment")
            recommendations.append("Consider implementing automated monitoring for continued performance")
            recommendations.append("Regular validation runs recommended before client demonstrations")
        
        return recommendations
    
    def run_comprehensive_validation(self) -> WorkflowReport:
        """Run all validation tests and generate comprehensive report"""
        print("🔍 Starting Comprehensive Workflow Validation")
        print("=" * 60)
        
        # Define all validation tests
        validation_tests = [
            ("Environment Validation", "Environment", self.validate_environment),
            ("External Tools Check", "External", self.validate_external_tools),
            ("Test Data Validation", "Data", self.validate_test_data),
            ("DaVinci Integration Test", "Integration", self.validate_davinci_integration),
            ("Pipeline Components Check", "Pipeline", self.validate_pipeline_components),
            ("Output Quality Validation", "Quality", self.validate_output_quality),
            ("Social Workflow Test", "Workflow", self.validate_social_workflow)
        ]
        
        # Run each test
        for test_name, category, test_func in validation_tests:
            print(f"📋 Running: {test_name}")
            result = self.run_timed_test(test_name, category, test_func)
            self.results.append(result)
            
            # Print immediate result
            status_emoji = {"passed": "✅", "failed": "❌", "warning": "⚠️", "skipped": "⏭️"}
            emoji = status_emoji.get(result.status, "❓")
            print(f"   {emoji} {result.status.upper()}: {result.message} ({result.duration_ms}ms)")
        
        # Generate summary statistics
        total_tests = len(self.results)
        passed = len([r for r in self.results if r.status == "passed"])
        failed = len([r for r in self.results if r.status == "failed"])
        warnings = len([r for r in self.results if r.status == "warning"])
        skipped = len([r for r in self.results if r.status == "skipped"])
        
        # Determine overall status
        if failed > 0:
            overall_status = "FAILED"
        elif warnings > 0:
            overall_status = "WARNING"
        else:
            overall_status = "PASSED"
        
        # Generate performance summary and recommendations
        performance_summary = self.generate_performance_summary()
        recommendations = self.generate_recommendations()
        
        # Create comprehensive report
        report = WorkflowReport(
            timestamp=datetime.now().isoformat(),
            total_tests=total_tests,
            passed=passed,
            failed=failed,
            warnings=warnings,
            skipped=skipped,
            total_duration_ms=int((time.time() - self.start_time) * 1000),
            overall_status=overall_status,
            results=self.results,
            performance_summary=performance_summary,
            recommendations=recommendations
        )
        
        return report
    
    def save_report(self, report: WorkflowReport, filename: str = None) -> str:
        """Save validation report to JSON file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"workflow_validation_report_{timestamp}.json"
        
        # Convert report to dict for JSON serialization
        report_dict = asdict(report)
        
        with open(filename, 'w') as f:
            json.dump(report_dict, f, indent=2)
        
        return filename
    
    def print_summary_report(self, report: WorkflowReport):
        """Print formatted summary report to console"""
        print("\n" + "=" * 60)
        print("🎬 COMPREHENSIVE WORKFLOW VALIDATION REPORT")
        print("=" * 60)
        print(f"⏰ Completed: {report.timestamp}")
        print(f"🎯 Overall Status: {report.overall_status}")
        print(f"📊 Tests: {report.passed}✅ {report.warnings}⚠️ {report.failed}❌ {report.skipped}⏭️")
        print(f"⌱ Duration: {report.total_duration_ms}ms")
        
        print("\n📋 TEST RESULTS BY CATEGORY:")
        categories = {}
        for result in report.results:
            if result.category not in categories:
                categories[result.category] = {"passed": 0, "failed": 0, "warnings": 0, "skipped": 0}
            categories[result.category][result.status] += 1
        
        for category, stats in categories.items():
            total = sum(stats.values())
            print(f"   {category}: {stats['passed']}/{total} passed, {stats['warnings']} warnings, {stats['failed']} failed")
        
        print(f"\n🚀 PERFORMANCE METRICS:")
        perf = report.performance_summary["test_execution"]
        print(f"   Average test time: {perf['average_test_duration_ms']}ms")
        print(f"   Slowest: {perf['slowest_test']}")
        print(f"   Fastest: {perf['fastest_test']}")
        
        print(f"\n💡 RECOMMENDATIONS:")
        for i, rec in enumerate(report.recommendations, 1):
            print(f"   {i}. {rec}")
        
        print("\n" + "=" * 60)
        print(f"🎯 Status: {report.overall_status} - Validation Complete")
        print("=" * 60)

def main():
    """Run comprehensive validation and generate report"""
    validator = ComprehensiveWorkflowValidator()
    
    # Run validation
    report = validator.run_comprehensive_validation()
    
    # Print summary
    validator.print_summary_report(report)
    
    # Save detailed report
    report_file = validator.save_report(report)
    print(f"\n📄 Detailed report saved: {report_file}")
    
    # Exit with appropriate code
    if report.overall_status == "FAILED":
        exit(1)
    elif report.overall_status == "WARNING":
        exit(2)  
    else:
        exit(0)

if __name__ == "__main__":
    main()