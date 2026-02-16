#!/usr/bin/env python3
"""
Multi-Project Batch Processor for DaVinci Resolve OpenClaw
Advanced feature implementation for handling multiple video projects simultaneously

Features:
- Parallel processing of multiple video directories
- Intelligent resource management and scheduling
- Progress tracking and reporting across projects
- Consolidated output organization
- Quality metrics aggregation
"""

import json
import os
import time
import concurrent.futures
import threading
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging
import subprocess
import shutil

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MultiProjectProcessor:
    def __init__(self, max_workers: int = 3):
        """Initialize multi-project processor with resource limits"""
        self.max_workers = max_workers
        self.projects = []
        self.results = {}
        self.start_time = None
        self.project_lock = threading.Lock()
        
        # Create batch output directory
        self.batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.batch_dir = Path(f"batch_processing_{self.batch_id}")
        self.batch_dir.mkdir(exist_ok=True)
        
        # Status tracking
        self.project_status = {}
        self.overall_stats = {
            'total_projects': 0,
            'completed_projects': 0,
            'failed_projects': 0,
            'total_processing_time': 0,
            'total_videos_generated': 0,
            'total_output_size': 0
        }
    
    def add_project(self, project_path: str, project_name: Optional[str] = None) -> bool:
        """Add a video project directory for batch processing"""
        project_path = Path(project_path)
        
        if not project_path.exists():
            logger.error(f"Project path does not exist: {project_path}")
            return False
        
        # Auto-generate project name if not provided
        if not project_name:
            project_name = project_path.name
        
        # Validate project has video files
        video_files = list(project_path.glob("*.mp4")) + list(project_path.glob("*.mov"))
        if not video_files:
            logger.warning(f"No video files found in {project_path}")
            return False
        
        project_info = {
            'name': project_name,
            'path': str(project_path),
            'video_count': len(video_files),
            'estimated_duration': self._estimate_project_duration(video_files),
            'added_at': datetime.now().isoformat()
        }
        
        self.projects.append(project_info)
        self.project_status[project_name] = 'pending'
        logger.info(f"Added project: {project_name} ({len(video_files)} videos)")
        return True
    
    def _estimate_project_duration(self, video_files: List[Path]) -> float:
        """Estimate project processing duration based on video files"""
        total_duration = 0
        for video_file in video_files[:3]:  # Sample first 3 files
            try:
                result = subprocess.run([
                    'ffprobe', '-v', 'quiet', '-show_entries', 
                    'format=duration', '-of', 'csv=p=0', str(video_file)
                ], capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    duration = float(result.stdout.strip())
                    total_duration += duration
            except (subprocess.TimeoutExpired, ValueError):
                # Fallback estimate: 2 minutes per video
                total_duration += 120
        
        # Estimate total duration if we only sampled
        if len(video_files) > 3:
            avg_duration = total_duration / min(3, len(video_files))
            total_duration = avg_duration * len(video_files)
        
        return total_duration
    
    def process_project(self, project_info: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single project with the video pipeline"""
        project_name = project_info['name']
        project_path = project_info['path']
        
        logger.info(f"🎬 Starting project: {project_name}")
        
        # Update status
        with self.project_lock:
            self.project_status[project_name] = 'processing'
        
        # Create project output directory
        project_output = self.batch_dir / project_name
        project_output.mkdir(exist_ok=True)
        
        project_start = time.time()
        result = {
            'project_name': project_name,
            'project_path': project_path,
            'start_time': project_start,
            'success': False,
            'error': None,
            'videos_generated': 0,
            'output_size_mb': 0,
            'processing_time': 0,
            'quality_score': 0.0
        }
        
        try:
            # Run the advanced workflow optimizer on this project
            cmd = [
                'python3', 'advanced_workflow_optimizer.py',
                '--input-dir', project_path,
                '--output-dir', str(project_output),
                '--batch-mode'
            ]
            
            logger.info(f"Executing: {' '.join(cmd)}")
            process_result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=1800  # 30 minute timeout
            )
            
            if process_result.returncode == 0:
                result['success'] = True
                
                # Parse output for metrics
                if project_output.exists():
                    # Count generated videos
                    video_outputs = list(project_output.glob("*.mp4"))
                    result['videos_generated'] = len(video_outputs)
                    
                    # Calculate total output size
                    total_size = 0
                    for video in video_outputs:
                        total_size += video.stat().st_size
                    result['output_size_mb'] = total_size / (1024 * 1024)
                
                # Generate quality score based on completion metrics
                result['quality_score'] = self._calculate_quality_score(result)
                
                logger.info(f"✅ Project completed: {project_name}")
                
            else:
                result['error'] = process_result.stderr
                logger.error(f"❌ Project failed: {project_name} - {process_result.stderr}")
        
        except subprocess.TimeoutExpired:
            result['error'] = "Processing timeout exceeded (30 minutes)"
            logger.error(f"⏰ Project timed out: {project_name}")
        
        except Exception as e:
            result['error'] = str(e)
            logger.error(f"💥 Project error: {project_name} - {e}")
        
        finally:
            result['processing_time'] = time.time() - project_start
            
            # Update status
            with self.project_lock:
                self.project_status[project_name] = 'completed' if result['success'] else 'failed'
                
                # Update overall stats
                if result['success']:
                    self.overall_stats['completed_projects'] += 1
                else:
                    self.overall_stats['failed_projects'] += 1
                
                self.overall_stats['total_processing_time'] += result['processing_time']
                self.overall_stats['total_videos_generated'] += result['videos_generated']
                self.overall_stats['total_output_size'] += result['output_size_mb']
        
        return result
    
    def _calculate_quality_score(self, result: Dict[str, Any]) -> float:
        """Calculate quality score based on project completion metrics"""
        score = 0.0
        
        # Base score for successful completion
        if result['success']:
            score += 0.5
        
        # Score for video generation
        if result['videos_generated'] > 0:
            score += 0.3
            
        # Bonus for multiple outputs (social media variations)
        if result['videos_generated'] >= 3:
            score += 0.1
            
        # Bonus for reasonable processing time (under 10 minutes)
        if result['processing_time'] < 600:
            score += 0.1
        
        return min(score, 1.0)
    
    def run_batch_processing(self) -> Dict[str, Any]:
        """Execute batch processing of all added projects"""
        if not self.projects:
            logger.warning("No projects to process")
            return {'error': 'No projects added'}
        
        self.start_time = time.time()
        self.overall_stats['total_projects'] = len(self.projects)
        
        logger.info(f"🚀 Starting batch processing of {len(self.projects)} projects")
        logger.info(f"📁 Output directory: {self.batch_dir}")
        logger.info(f"👥 Max workers: {self.max_workers}")
        
        # Process projects in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all projects for processing
            future_to_project = {
                executor.submit(self.process_project, project): project['name'] 
                for project in self.projects
            }
            
            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_project):
                project_name = future_to_project[future]
                try:
                    result = future.result()
                    self.results[project_name] = result
                    
                    # Progress update
                    completed = len([r for r in self.results.values() if 'processing_time' in r])
                    logger.info(f"📊 Progress: {completed}/{len(self.projects)} projects completed")
                    
                except Exception as e:
                    logger.error(f"Project {project_name} generated an exception: {e}")
                    self.results[project_name] = {
                        'project_name': project_name,
                        'success': False,
                        'error': str(e),
                        'processing_time': 0
                    }
        
        # Generate final report
        total_time = time.time() - self.start_time
        report = self._generate_batch_report(total_time)
        
        # Save report to file
        report_file = self.batch_dir / "batch_report.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info(f"📋 Batch processing completed in {total_time:.1f}s")
        logger.info(f"📊 Report saved: {report_file}")
        
        return report
    
    def _generate_batch_report(self, total_time: float) -> Dict[str, Any]:
        """Generate comprehensive batch processing report"""
        successful_projects = [r for r in self.results.values() if r.get('success', False)]
        failed_projects = [r for r in self.results.values() if not r.get('success', False)]
        
        # Calculate aggregate metrics
        avg_quality = sum(r.get('quality_score', 0) for r in successful_projects) / max(1, len(successful_projects))
        total_videos = sum(r.get('videos_generated', 0) for r in self.results.values())
        total_size = sum(r.get('output_size_mb', 0) for r in self.results.values())
        
        report = {
            'batch_info': {
                'batch_id': self.batch_id,
                'start_time': self.start_time,
                'total_processing_time': total_time,
                'output_directory': str(self.batch_dir)
            },
            'summary_stats': {
                'total_projects': len(self.projects),
                'successful_projects': len(successful_projects),
                'failed_projects': len(failed_projects),
                'success_rate': len(successful_projects) / len(self.projects) * 100,
                'total_videos_generated': total_videos,
                'total_output_size_mb': total_size,
                'average_quality_score': avg_quality
            },
            'project_results': self.results,
            'performance_metrics': {
                'average_project_time': sum(r.get('processing_time', 0) for r in self.results.values()) / len(self.results),
                'parallel_efficiency': self._calculate_parallel_efficiency(total_time),
                'throughput_projects_per_hour': len(self.projects) / (total_time / 3600)
            }
        }
        
        return report
    
    def _calculate_parallel_efficiency(self, total_time: float) -> float:
        """Calculate how efficiently parallel processing performed"""
        sequential_time = sum(r.get('processing_time', 0) for r in self.results.values())
        if sequential_time == 0:
            return 0.0
        
        # Efficiency = Sequential time / (Parallel time * workers used)
        workers_used = min(self.max_workers, len(self.projects))
        theoretical_parallel_time = sequential_time / workers_used
        
        return (theoretical_parallel_time / total_time) * 100 if total_time > 0 else 0.0
    
    def get_status_summary(self) -> Dict[str, Any]:
        """Get current processing status summary"""
        return {
            'batch_id': self.batch_id,
            'projects_added': len(self.projects),
            'project_status': dict(self.project_status),
            'overall_stats': dict(self.overall_stats),
            'output_directory': str(self.batch_dir)
        }


def main():
    """Demo usage of multi-project batch processor"""
    processor = MultiProjectProcessor(max_workers=2)
    
    # Example: Add multiple project directories
    test_projects = [
        "/Volumes/LaCie/VIDEO/nycap-portalcam",  # Main test project
        # Add more project directories here when available
    ]
    
    for project_path in test_projects:
        if Path(project_path).exists():
            processor.add_project(project_path)
        else:
            logger.warning(f"Skipping non-existent project: {project_path}")
    
    if processor.projects:
        # Run batch processing
        report = processor.run_batch_processing()
        
        # Print summary
        print("\n" + "="*60)
        print("🎬 MULTI-PROJECT BATCH PROCESSING COMPLETE")
        print("="*60)
        print(f"📊 Success Rate: {report['summary_stats']['success_rate']:.1f}%")
        print(f"🎥 Total Videos: {report['summary_stats']['total_videos_generated']}")
        print(f"💾 Total Size: {report['summary_stats']['total_output_size_mb']:.1f} MB")
        print(f"⏱️  Total Time: {report['batch_info']['total_processing_time']:.1f}s")
        print(f"📁 Output: {report['batch_info']['output_directory']}")
        print("="*60)
    else:
        print("❌ No valid projects found to process")


if __name__ == "__main__":
    main()