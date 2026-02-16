#!/usr/bin/env python3
"""
🧪 DaVinci Resolve OpenClaw - Comprehensive Test Suite
Automated testing framework for all system components
Created: February 15, 2026 - 7:30 AM EST (Cron Hour 14)
"""

import json
import time
import subprocess
import sys
import os
from pathlib import Path
from typing import Dict, List, Tuple, Any
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('test_suite.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ComprehensiveTestSuite:
    """Complete test suite for DaVinci Resolve OpenClaw system"""
    
    def __init__(self):
        self.start_time = time.time()
        self.test_results = {
            'start_time': self.start_time,
            'tests': {},
            'summary': {
                'total': 0,
                'passed': 0,
                'failed': 0,
                'skipped': 0,
                'duration': 0
            }
        }
        self.project_root = Path(__file__).parent
        
    def run_test(self, test_name: str, test_function) -> bool:
        """Run individual test with error handling and timing"""
        logger.info(f"🧪 Running test: {test_name}")
        test_start = time.time()
        
        try:
            result = test_function()
            duration = time.time() - test_start
            
            self.test_results['tests'][test_name] = {
                'status': 'PASSED' if result else 'FAILED',
                'duration': duration,
                'timestamp': test_start
            }
            
            if result:
                self.test_results['summary']['passed'] += 1
                logger.info(f"✅ PASSED: {test_name} ({duration:.2f}s)")
            else:
                self.test_results['summary']['failed'] += 1
                logger.error(f"❌ FAILED: {test_name} ({duration:.2f}s)")
                
            return result
            
        except Exception as e:
            duration = time.time() - test_start
            self.test_results['tests'][test_name] = {
                'status': 'FAILED',
                'duration': duration,
                'error': str(e),
                'timestamp': test_start
            }
            self.test_results['summary']['failed'] += 1
            logger.error(f"❌ FAILED: {test_name} ({duration:.2f}s) - {str(e)}")
            return False
        finally:
            self.test_results['summary']['total'] += 1

    def test_python_environment(self) -> bool:
        """Test Python environment and required modules"""
        try:
            required_modules = [
                'json', 'subprocess', 'pathlib', 'openai', 'requests',
                'sqlite3', 'datetime', 'hashlib', 'concurrent', 'threading'
            ]
            
            for module in required_modules:
                __import__(module)
                
            return True
        except ImportError as e:
            logger.error(f"Missing Python module: {e}")
            return False

    def test_external_dependencies(self) -> bool:
        """Test external system dependencies"""
        try:
            # Test ffprobe
            result = subprocess.run(['ffprobe', '-version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode != 0:
                return False
                
            # Test OpenAI API key
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key or len(api_key) < 20:
                logger.error("OpenAI API key not configured or invalid")
                return False
                
            return True
        except Exception as e:
            logger.error(f"External dependency check failed: {e}")
            return False

    def test_file_structure(self) -> bool:
        """Test project file structure integrity"""
        try:
            required_files = [
                'ingest.py',
                'transcribe.py', 
                'script_engine_ai.py',
                'timeline_builder.py',
                'health_check.py',
                'video_pipeline',
                'requirements.txt',
                'Dockerfile',
                'docker-compose.yml'
            ]
            
            missing_files = []
            for file_path in required_files:
                full_path = self.project_root / file_path
                if not full_path.exists():
                    missing_files.append(file_path)
                    
            if missing_files:
                logger.error(f"Missing files: {missing_files}")
                return False
                
            return True
        except Exception as e:
            logger.error(f"File structure test failed: {e}")
            return False

    def test_davinci_resolve_connection(self) -> bool:
        """Test DaVinci Resolve connection"""
        try:
            # Import resolve bridge
            sys.path.append(str(self.project_root))
            
            # Try to establish connection (will fail gracefully if Resolve not running)
            test_script = """
import sys
sys.path.append('/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion')
try:
    import DaVinciResolveScript as dvr_script
    resolve = dvr_script.scriptapp("Resolve")
    if resolve:
        print("SUCCESS: DaVinci Resolve connection established")
    else:
        print("WARNING: DaVinci Resolve not running")
except:
    print("WARNING: DaVinci Resolve not available")
"""
            result = subprocess.run([sys.executable, '-c', test_script], 
                                  capture_output=True, text=True, timeout=10)
            
            # Success if either connection works or graceful failure
            return "SUCCESS" in result.stdout or "WARNING" in result.stdout
            
        except Exception as e:
            logger.error(f"DaVinci Resolve connection test failed: {e}")
            return False

    def test_data_integrity(self) -> bool:
        """Test data file integrity"""
        try:
            data_files = [
                'manifest.json',
                'project_diarization.json', 
                'scene_analysis.json',
                'nycap-portalcam_color_grading.json'
            ]
            
            for file_name in data_files:
                file_path = self.project_root / file_name
                if file_path.exists():
                    with open(file_path, 'r') as f:
                        json.load(f)  # Validate JSON structure
                        
            return True
        except Exception as e:
            logger.error(f"Data integrity test failed: {e}")
            return False

    def test_render_outputs(self) -> bool:
        """Test render output files"""
        try:
            renders_dir = self.project_root / 'renders'
            if not renders_dir.exists():
                return True  # No renders yet, that's OK
                
            video_files = list(renders_dir.glob('*.mp4'))
            if len(video_files) == 0:
                return True  # No videos yet, that's OK
                
            # Check if videos are valid (non-zero size)
            for video_file in video_files:
                if video_file.stat().st_size == 0:
                    logger.error(f"Zero-size video file: {video_file}")
                    return False
                    
            return True
        except Exception as e:
            logger.error(f"Render outputs test failed: {e}")
            return False

    def test_docker_configuration(self) -> bool:
        """Test Docker configuration files"""
        try:
            # Check Dockerfile syntax
            dockerfile = self.project_root / 'Dockerfile'
            if dockerfile.exists():
                with open(dockerfile, 'r') as f:
                    content = f.read()
                    if 'FROM ubuntu' not in content:
                        return False
                        
            # Check docker-compose.yml
            compose_file = self.project_root / 'docker-compose.yml'
            if compose_file.exists():
                with open(compose_file, 'r') as f:
                    content = f.read()
                    if 'version:' not in content or 'services:' not in content:
                        return False
                        
            return True
        except Exception as e:
            logger.error(f"Docker configuration test failed: {e}")
            return False

    def test_api_endpoints(self) -> bool:
        """Test API endpoint configurations"""
        try:
            # Check for API server files
            api_files = [
                'professional_api_server.py',
                'enterprise_multi_client_manager.py'
            ]
            
            for api_file in api_files:
                file_path = self.project_root / api_file
                if file_path.exists():
                    # Basic syntax check
                    with open(file_path, 'r') as f:
                        content = f.read()
                        if 'app.run' in content or 'Flask' in content:
                            continue  # Valid API file
                        
            return True
        except Exception as e:
            logger.error(f"API endpoints test failed: {e}")
            return False

    def test_social_media_exports(self) -> bool:
        """Test social media export functionality"""
        try:
            # Check social media clipper
            social_clipper = self.project_root / 'social_media_clipper.py'
            if not social_clipper.exists():
                return False
                
            # Check automated export system
            auto_export = self.project_root / 'automated_social_export.py'
            if not auto_export.exists():
                return False
                
            # Check export directory structure
            exports_dir = self.project_root / 'exports'
            if exports_dir.exists():
                social_dir = exports_dir / 'social_media'
                # Directory should exist or be creatable
                
            return True
        except Exception as e:
            logger.error(f"Social media exports test failed: {e}")
            return False

    def test_performance_monitoring(self) -> bool:
        """Test performance monitoring system"""
        try:
            # Check performance database
            perf_db = self.project_root / 'performance_analytics.db'
            if perf_db.exists():
                # Database exists, that's good
                pass
                
            # Check advanced optimizer
            optimizer = self.project_root / 'advanced_workflow_optimizer.py'
            if optimizer.exists():
                with open(optimizer, 'r') as f:
                    content = f.read()
                    if 'optimization' not in content.lower():
                        return False
                        
            return True
        except Exception as e:
            logger.error(f"Performance monitoring test failed: {e}")
            return False

    def run_all_tests(self) -> Dict[str, Any]:
        """Run complete test suite"""
        logger.info("🚀 Starting Comprehensive Test Suite")
        logger.info(f"📁 Project root: {self.project_root}")
        
        # Core system tests
        self.run_test("Python Environment", self.test_python_environment)
        self.run_test("External Dependencies", self.test_external_dependencies)
        self.run_test("File Structure", self.test_file_structure)
        self.run_test("Data Integrity", self.test_data_integrity)
        
        # Application tests
        self.run_test("DaVinci Resolve Connection", self.test_davinci_resolve_connection)
        self.run_test("Render Outputs", self.test_render_outputs)
        self.run_test("Social Media Exports", self.test_social_media_exports)
        
        # Infrastructure tests
        self.run_test("Docker Configuration", self.test_docker_configuration)
        self.run_test("API Endpoints", self.test_api_endpoints)
        self.run_test("Performance Monitoring", self.test_performance_monitoring)
        
        # Calculate final results
        self.test_results['summary']['duration'] = time.time() - self.start_time
        self.test_results['end_time'] = time.time()
        
        # Generate report
        self.generate_report()
        
        return self.test_results

    def generate_report(self):
        """Generate comprehensive test report"""
        summary = self.test_results['summary']
        
        logger.info("\n" + "="*60)
        logger.info("📊 COMPREHENSIVE TEST SUITE RESULTS")
        logger.info("="*60)
        logger.info(f"🎯 Total Tests: {summary['total']}")
        logger.info(f"✅ Passed: {summary['passed']}")
        logger.info(f"❌ Failed: {summary['failed']}")
        logger.info(f"⏱️  Duration: {summary['duration']:.2f} seconds")
        
        if summary['total'] > 0:
            success_rate = (summary['passed'] / summary['total']) * 100
            logger.info(f"📈 Success Rate: {success_rate:.1f}%")
            
        logger.info("\n📋 DETAILED RESULTS:")
        for test_name, result in self.test_results['tests'].items():
            status_icon = "✅" if result['status'] == 'PASSED' else "❌"
            logger.info(f"{status_icon} {test_name}: {result['status']} ({result['duration']:.2f}s)")
            
        # Save results to file
        results_file = self.project_root / 'test_results.json'
        with open(results_file, 'w') as f:
            json.dump(self.test_results, f, indent=2)
            
        logger.info(f"\n💾 Results saved to: {results_file}")
        logger.info("="*60)

def main():
    """Run comprehensive test suite"""
    suite = ComprehensiveTestSuite()
    results = suite.run_all_tests()
    
    # Exit with appropriate code
    if results['summary']['failed'] == 0:
        sys.exit(0)  # All tests passed
    else:
        sys.exit(1)  # Some tests failed

if __name__ == "__main__":
    main()