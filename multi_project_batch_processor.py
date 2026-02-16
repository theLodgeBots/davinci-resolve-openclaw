#!/usr/bin/env python3
"""
Multi-Project Batch Processor for DaVinci Resolve OpenClaw
Enterprise-scale video processing system for multiple projects

Features:
- Concurrent processing of multiple video projects
- Intelligent resource management and load balancing
- Project prioritization and scheduling
- Automated workflow orchestration
- Progress tracking and reporting
- Error handling and recovery
- Integration with quality scoring and client feedback
"""

import json
import os
import time
import threading
import queue
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, NamedTuple
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import subprocess
from enum import Enum
import psutil

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ProjectStatus(Enum):
    """Project processing status"""
    PENDING = "pending"
    QUEUED = "queued" 
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"

class ProjectPriority(Enum):
    """Project priority levels"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4

@dataclass
class ProjectConfig:
    """Configuration for a single project"""
    project_id: str
    name: str
    source_directory: str
    output_directory: str
    priority: ProjectPriority
    client_id: Optional[str] = None
    deadline: Optional[datetime] = None
    processing_options: Optional[Dict[str, Any]] = None
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

@dataclass
class ProcessingResult:
    """Result of processing a single project"""
    project_id: str
    status: ProjectStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    processing_time: Optional[float] = None
    files_processed: int = 0
    output_files: List[str] = None
    error_message: Optional[str] = None
    quality_scores: Optional[Dict[str, float]] = None
    
    def __post_init__(self):
        if self.output_files is None:
            self.output_files = []

class ResourceMonitor:
    """Monitor system resources and manage processing load"""
    
    def __init__(self, max_cpu_percent: float = 80.0, max_memory_percent: float = 70.0):
        self.max_cpu_percent = max_cpu_percent
        self.max_memory_percent = max_memory_percent
        self.monitoring = False
        self._monitor_thread = None
        
    def start_monitoring(self):
        """Start resource monitoring"""
        self.monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop)
        self._monitor_thread.start()
        logger.info("Resource monitoring started")
        
    def stop_monitoring(self):
        """Stop resource monitoring"""
        self.monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join()
        logger.info("Resource monitoring stopped")
        
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.monitoring:
            time.sleep(5)  # Check every 5 seconds
            
    def can_start_new_job(self) -> bool:
        """Check if system resources allow starting a new job"""
        cpu_percent = psutil.cpu_percent(interval=1)
        memory_percent = psutil.virtual_memory().percent
        
        return (cpu_percent < self.max_cpu_percent and 
                memory_percent < self.max_memory_percent)
    
    def get_system_stats(self) -> Dict[str, float]:
        """Get current system resource statistics"""
        return {
            'cpu_percent': psutil.cpu_percent(),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_percent': psutil.disk_usage('/').percent,
            'load_average': os.getloadavg()[0] if hasattr(os, 'getloadavg') else 0.0
        }

class ProjectQueue:
    """Priority queue for managing project processing order"""
    
    def __init__(self):
        self.projects = {}  # project_id -> ProjectConfig
        self.results = {}   # project_id -> ProcessingResult
        self._lock = threading.Lock()
        
    def add_project(self, project: ProjectConfig) -> bool:
        """Add a project to the queue"""
        with self._lock:
            if project.project_id in self.projects:
                logger.warning(f"Project {project.project_id} already exists in queue")
                return False
                
            self.projects[project.project_id] = project
            logger.info(f"Added project {project.project_id} to queue with priority {project.priority.name}")
            return True
    
    def get_next_project(self) -> Optional[ProjectConfig]:
        """Get the highest priority project that's ready to process"""
        with self._lock:
            # Find pending projects sorted by priority (highest first), then by deadline
            pending_projects = [
                p for p in self.projects.values() 
                if p.project_id not in self.results or 
                   self.results[p.project_id].status == ProjectStatus.PENDING
            ]
            
            if not pending_projects:
                return None
            
            # Sort by priority (descending) then by deadline (ascending)
            pending_projects.sort(
                key=lambda p: (
                    -p.priority.value,  # Higher priority first
                    p.deadline if p.deadline else datetime.max  # Earlier deadline first
                )
            )
            
            return pending_projects[0]
    
    def update_result(self, result: ProcessingResult):
        """Update processing result for a project"""
        with self._lock:
            self.results[result.project_id] = result
            logger.info(f"Updated result for project {result.project_id}: {result.status.value}")
    
    def get_status_summary(self) -> Dict[str, int]:
        """Get summary of project statuses"""
        with self._lock:
            summary = {status.value: 0 for status in ProjectStatus}
            
            for project_id in self.projects:
                if project_id in self.results:
                    status = self.results[project_id].status
                else:
                    status = ProjectStatus.PENDING
                summary[status.value] += 1
                
            return summary
    
    def get_queue_info(self) -> Dict[str, Any]:
        """Get detailed queue information"""
        with self._lock:
            return {
                'total_projects': len(self.projects),
                'status_summary': self.get_status_summary(),
                'projects': [
                    {
                        'project_id': p.project_id,
                        'name': p.name,
                        'priority': p.priority.name,
                        'status': self.results.get(p.project_id, ProcessingResult(p.project_id, ProjectStatus.PENDING, datetime.now())).status.value,
                        'deadline': p.deadline.isoformat() if p.deadline else None
                    }
                    for p in self.projects.values()
                ]
            }

class MultiProjectBatchProcessor:
    """Main batch processing system for multiple video projects"""
    
    def __init__(self, max_workers: int = 4, max_cpu_percent: float = 80.0, max_memory_percent: float = 70.0):
        self.max_workers = max_workers
        self.project_queue = ProjectQueue()
        self.resource_monitor = ResourceMonitor(max_cpu_percent, max_memory_percent)
        self.processing = False
        self.executor = None
        
        # Create processing directories
        self.batch_dir = Path("batch_processing")
        self.batch_dir.mkdir(exist_ok=True)
        
        self.logs_dir = self.batch_dir / "logs"
        self.logs_dir.mkdir(exist_ok=True)
        
        self.reports_dir = self.batch_dir / "reports"
        self.reports_dir.mkdir(exist_ok=True)
        
    def add_project(self, project: ProjectConfig) -> bool:
        """Add a project to the processing queue"""
        # Validate project configuration
        if not self._validate_project(project):
            return False
            
        return self.project_queue.add_project(project)
    
    def add_projects_from_config(self, config_file: str) -> int:
        """Add multiple projects from a JSON configuration file"""
        try:
            with open(config_file, 'r') as f:
                config_data = json.load(f)
            
            projects_added = 0
            for project_data in config_data.get('projects', []):
                # Convert deadline string to datetime if provided
                if 'deadline' in project_data and project_data['deadline']:
                    project_data['deadline'] = datetime.fromisoformat(project_data['deadline'])
                
                # Convert priority string to enum
                if 'priority' in project_data:
                    project_data['priority'] = ProjectPriority[project_data['priority'].upper()]
                
                project = ProjectConfig(**project_data)
                if self.add_project(project):
                    projects_added += 1
                    
            logger.info(f"Added {projects_added} projects from config file")
            return projects_added
            
        except Exception as e:
            logger.error(f"Error loading projects from config: {e}")
            return 0
    
    def _validate_project(self, project: ProjectConfig) -> bool:
        """Validate project configuration"""
        if not project.project_id:
            logger.error("Project ID is required")
            return False
            
        if not os.path.isdir(project.source_directory):
            logger.error(f"Source directory does not exist: {project.source_directory}")
            return False
            
        # Create output directory if it doesn't exist
        os.makedirs(project.output_directory, exist_ok=True)
        
        return True
    
    def start_processing(self) -> bool:
        """Start the batch processing system"""
        if self.processing:
            logger.warning("Batch processing is already running")
            return False
            
        self.processing = True
        self.resource_monitor.start_monitoring()
        
        # Start thread pool executor
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        
        # Start processing loop in a separate thread
        processing_thread = threading.Thread(target=self._processing_loop)
        processing_thread.start()
        
        logger.info(f"Batch processing started with {self.max_workers} workers")
        return True
    
    def stop_processing(self):
        """Stop the batch processing system"""
        if not self.processing:
            return
            
        logger.info("Stopping batch processing...")
        self.processing = False
        
        if self.executor:
            self.executor.shutdown(wait=True)
            
        self.resource_monitor.stop_monitoring()
        logger.info("Batch processing stopped")
    
    def _processing_loop(self):
        """Main processing loop"""
        while self.processing:
            try:
                # Check if we can start a new job
                if not self.resource_monitor.can_start_new_job():
                    logger.debug("System resources at capacity, waiting...")
                    time.sleep(10)
                    continue
                
                # Get next project to process
                project = self.project_queue.get_next_project()
                if not project:
                    logger.debug("No projects in queue, waiting...")
                    time.sleep(5)
                    continue
                
                # Submit project for processing
                future = self.executor.submit(self._process_project, project)
                logger.info(f"Started processing project {project.project_id}")
                
                # Brief pause to prevent overwhelming the system
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Error in processing loop: {e}")
                time.sleep(5)
    
    def _process_project(self, project: ProjectConfig) -> ProcessingResult:
        """Process a single project"""
        start_time = datetime.now()
        result = ProcessingResult(
            project_id=project.project_id,
            status=ProjectStatus.PROCESSING,
            start_time=start_time
        )
        
        try:
            # Update status to processing
            self.project_queue.update_result(result)
            
            # Log processing start
            self._log_project_event(project.project_id, "Processing started")
            
            # Process the project using the main video pipeline
            output_files = self._run_video_pipeline(project)
            
            # Calculate quality scores if quality scorer is available
            quality_scores = self._calculate_quality_scores(output_files)
            
            # Update result with success
            end_time = datetime.now()
            result.status = ProjectStatus.COMPLETED
            result.end_time = end_time
            result.processing_time = (end_time - start_time).total_seconds()
            result.output_files = output_files
            result.files_processed = len(output_files)
            result.quality_scores = quality_scores
            
            self._log_project_event(project.project_id, f"Processing completed successfully in {result.processing_time:.1f}s")
            
        except Exception as e:
            # Update result with error
            end_time = datetime.now()
            result.status = ProjectStatus.ERROR
            result.end_time = end_time
            result.processing_time = (end_time - start_time).total_seconds()
            result.error_message = str(e)
            
            logger.error(f"Error processing project {project.project_id}: {e}")
            self._log_project_event(project.project_id, f"Processing failed: {e}")
        
        # Update final result
        self.project_queue.update_result(result)
        
        # Generate project report
        self._generate_project_report(project, result)
        
        return result
    
    def _run_video_pipeline(self, project: ProjectConfig) -> List[str]:
        """Run the video processing pipeline for a project"""
        output_files = []
        
        # Use the existing video_pipeline script
        pipeline_script = Path(__file__).parent / "video_pipeline"
        
        if not pipeline_script.exists():
            raise FileNotFoundError("video_pipeline script not found")
        
        # Prepare command
        cmd = [
            str(pipeline_script),
            "pipeline",
            "--source", project.source_directory,
            "--output", project.output_directory,
            "--name", project.name
        ]
        
        # Add processing options if specified
        if project.processing_options:
            for key, value in project.processing_options.items():
                if isinstance(value, bool) and value:
                    cmd.append(f"--{key}")
                elif not isinstance(value, bool):
                    cmd.extend([f"--{key}", str(value)])
        
        # Run the pipeline
        logger.info(f"Running pipeline for project {project.project_id}: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent)
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"Pipeline failed with return code {result.returncode}: {result.stderr}")
        
        # Find output files
        output_dir = Path(project.output_directory)
        for ext in ['.mp4', '.mov', '.avi']:
            output_files.extend([str(f) for f in output_dir.glob(f"*{ext}")])
        
        return output_files
    
    def _calculate_quality_scores(self, output_files: List[str]) -> Dict[str, float]:
        """Calculate quality scores for output files"""
        try:
            # Try to import and use the quality scorer
            from ai_video_quality_scorer import AIVideoQualityScorer
            
            scorer = AIVideoQualityScorer()
            quality_scores = {}
            
            for file_path in output_files:
                try:
                    assessment = scorer.analyze_video_file(file_path)
                    filename = Path(file_path).name
                    quality_scores[filename] = assessment.quality_scores.overall
                except Exception as e:
                    logger.warning(f"Failed to score {file_path}: {e}")
            
            return quality_scores
            
        except ImportError:
            logger.warning("Quality scorer not available, skipping quality assessment")
            return {}
    
    def _log_project_event(self, project_id: str, message: str):
        """Log an event for a specific project"""
        log_file = self.logs_dir / f"{project_id}.log"
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        with open(log_file, 'a') as f:
            f.write(f"{timestamp} - {message}\n")
    
    def _generate_project_report(self, project: ProjectConfig, result: ProcessingResult):
        """Generate a detailed report for a processed project"""
        report = {
            'project_info': {
                'id': project.project_id,
                'name': project.name,
                'source_directory': project.source_directory,
                'output_directory': project.output_directory,
                'priority': project.priority.name,
                'client_id': project.client_id,
                'deadline': project.deadline.isoformat() if project.deadline else None,
                'created_at': project.created_at.isoformat()
            },
            'processing_result': {
                'status': result.status.value,
                'start_time': result.start_time.isoformat(),
                'end_time': result.end_time.isoformat() if result.end_time else None,
                'processing_time': result.processing_time,
                'files_processed': result.files_processed,
                'output_files': result.output_files,
                'error_message': result.error_message,
                'quality_scores': result.quality_scores
            },
            'system_info': self.resource_monitor.get_system_stats()
        }
        
        report_file = self.reports_dir / f"{project.project_id}_report.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Generated report for project {project.project_id}: {report_file}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current system status"""
        return {
            'processing': self.processing,
            'max_workers': self.max_workers,
            'queue_info': self.project_queue.get_queue_info(),
            'system_resources': self.resource_monitor.get_system_stats()
        }
    
    def generate_batch_report(self) -> str:
        """Generate a comprehensive batch processing report"""
        status = self.get_status()
        queue_info = status['queue_info']
        
        report = f"""
# Multi-Project Batch Processing Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## System Status
- Processing Active: {'Yes' if self.processing else 'No'}
- Max Workers: {self.max_workers}
- Current CPU Usage: {status['system_resources']['cpu_percent']:.1f}%
- Current Memory Usage: {status['system_resources']['memory_percent']:.1f}%

## Project Queue Summary
- Total Projects: {queue_info['total_projects']}
"""
        
        # Add status breakdown
        for status_name, count in queue_info['status_summary'].items():
            if count > 0:
                report += f"- {status_name.title()}: {count}\n"
        
        report += "\n## Project Details:\n"
        
        # Add project details
        for project in queue_info['projects']:
            report += f"""
### {project['name']} (ID: {project['project_id']})
- Priority: {project['priority']}
- Status: {project['status'].title()}
- Deadline: {project['deadline'] if project['deadline'] else 'None'}
"""
        
        return report
    
    def export_configuration(self, output_file: str):
        """Export current queue configuration to JSON file"""
        config = {
            'export_timestamp': datetime.now().isoformat(),
            'system_config': {
                'max_workers': self.max_workers,
                'max_cpu_percent': self.resource_monitor.max_cpu_percent,
                'max_memory_percent': self.resource_monitor.max_memory_percent
            },
            'projects': []
        }
        
        # Add all projects
        for project in self.project_queue.projects.values():
            project_dict = asdict(project)
            project_dict['priority'] = project.priority.name
            project_dict['created_at'] = project.created_at.isoformat()
            if project.deadline:
                project_dict['deadline'] = project.deadline.isoformat()
            config['projects'].append(project_dict)
        
        with open(output_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        logger.info(f"Configuration exported to: {output_file}")

def create_sample_config():
    """Create a sample configuration file for batch processing"""
    sample_config = {
        "projects": [
            {
                "project_id": "demo_project_1",
                "name": "Client A - Interview Series",
                "source_directory": "/Volumes/LaCie/VIDEO/client_a_interviews",
                "output_directory": "/Users/thelodgestudio/Desktop/batch_output/client_a",
                "priority": "HIGH",
                "client_id": "client_a",
                "deadline": "2026-02-20T17:00:00",
                "processing_options": {
                    "enhanced": True,
                    "social_media": True,
                    "quality_analysis": True
                }
            },
            {
                "project_id": "demo_project_2", 
                "name": "Product Demo Videos",
                "source_directory": "/Volumes/LaCie/VIDEO/product_demos",
                "output_directory": "/Users/thelodgestudio/Desktop/batch_output/product_demos",
                "priority": "NORMAL",
                "client_id": "internal",
                "processing_options": {
                    "enhanced": True,
                    "corporate_style": True
                }
            }
        ]
    }
    
    with open("sample_batch_config.json", 'w') as f:
        json.dump(sample_config, f, indent=2)
    
    print("Created sample_batch_config.json")

def main():
    """Main function for command-line usage"""
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description='Multi-Project Batch Processor for DaVinci Resolve OpenClaw')
    parser.add_argument('--config', help='JSON configuration file with projects to process')
    parser.add_argument('--workers', type=int, default=4, help='Maximum number of worker threads')
    parser.add_argument('--max-cpu', type=float, default=80.0, help='Maximum CPU usage percentage')
    parser.add_argument('--max-memory', type=float, default=70.0, help='Maximum memory usage percentage')
    parser.add_argument('--create-sample', action='store_true', help='Create sample configuration file')
    parser.add_argument('--status', action='store_true', help='Show current processing status')
    parser.add_argument('--report', action='store_true', help='Generate batch processing report')
    
    args = parser.parse_args()
    
    if args.create_sample:
        create_sample_config()
        return
    
    # Create processor instance
    processor = MultiProjectBatchProcessor(
        max_workers=args.workers,
        max_cpu_percent=args.max_cpu,
        max_memory_percent=args.max_memory
    )
    
    if args.config:
        # Load projects from config file
        projects_added = processor.add_projects_from_config(args.config)
        print(f"Added {projects_added} projects from configuration")
        
        if projects_added > 0:
            # Start processing
            print("Starting batch processing...")
            processor.start_processing()
            
            try:
                # Keep running until all projects are complete
                while True:
                    status = processor.get_status()
                    queue_info = status['queue_info']
                    
                    pending = queue_info['status_summary'].get('pending', 0)
                    processing = queue_info['status_summary'].get('processing', 0)
                    
                    if pending == 0 and processing == 0:
                        print("All projects completed!")
                        break
                    
                    print(f"Status: {processing} processing, {pending} pending")
                    time.sleep(10)
                    
            except KeyboardInterrupt:
                print("\nStopping batch processing...")
                
            finally:
                processor.stop_processing()
                
                # Generate final report
                report = processor.generate_batch_report()
                report_file = f"batch_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
                with open(report_file, 'w') as f:
                    f.write(report)
                print(f"Final report saved to: {report_file}")
    
    elif args.status:
        status = processor.get_status()
        print(json.dumps(status, indent=2))
        
    elif args.report:
        report = processor.generate_batch_report()
        print(report)
        
    else:
        parser.print_help()

if __name__ == "__main__":
    main()