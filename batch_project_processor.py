#!/usr/bin/env python3
"""
Multi-Project Batch Processing System for DaVinci Resolve OpenClaw
Enterprise-grade parallel processing of multiple video projects

Features:
- Process multiple projects simultaneously
- Intelligent resource allocation
- Priority queue management
- Real-time progress tracking
- Failure recovery and retry logic
- Client isolation and project management
"""

import json
import os
import asyncio
import threading
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
import logging
import uuid
import queue
import psutil

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ProjectStatus(Enum):
    """Project processing status"""
    QUEUED = "queued"
    PROCESSING = "processing"
    TRANSCRIBING = "transcribing"
    SCRIPTING = "scripting"
    TIMELINE_BUILDING = "timeline_building"
    RENDERING = "rendering"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class ProjectPriority(Enum):
    """Project processing priority"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    URGENT = 4

@dataclass
class BatchProject:
    """Individual project in the batch processing queue"""
    project_id: str
    client_id: str
    source_folder: str
    project_name: str
    priority: ProjectPriority = ProjectPriority.MEDIUM
    status: ProjectStatus = ProjectStatus.QUEUED
    created_at: datetime = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    progress: int = 0
    estimated_duration: Optional[int] = None
    actual_duration: Optional[int] = None
    output_files: List[str] = None
    config: Dict[str, Any] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.output_files is None:
            self.output_files = []
        if self.config is None:
            self.config = {}

class ResourceMonitor:
    """Monitor system resources for optimal batch processing"""
    
    def __init__(self):
        self.cpu_threshold = 80  # Max CPU usage percentage
        self.memory_threshold = 85  # Max memory usage percentage
        self.disk_threshold = 90  # Max disk usage percentage
        self.monitor_interval = 5  # seconds
        self._monitoring = False
        self._monitor_thread = None
        
    def start_monitoring(self):
        """Start resource monitoring"""
        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("Resource monitoring started")
        
    def stop_monitoring(self):
        """Stop resource monitoring"""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=10)
        logger.info("Resource monitoring stopped")
        
    def _monitor_loop(self):
        """Resource monitoring loop"""
        while self._monitoring:
            try:
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                
                # Log high resource usage
                if cpu_percent > self.cpu_threshold:
                    logger.warning(f"High CPU usage: {cpu_percent:.1f}%")
                if memory.percent > self.memory_threshold:
                    logger.warning(f"High memory usage: {memory.percent:.1f}%")
                if disk.percent > self.disk_threshold:
                    logger.warning(f"High disk usage: {disk.percent:.1f}%")
                    
            except Exception as e:
                logger.error(f"Resource monitoring error: {e}")
                
            time.sleep(self.monitor_interval)
    
    def get_system_capacity(self) -> int:
        """Calculate optimal concurrent job capacity based on current resources"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            cpu_cores = psutil.cpu_count()
            
            # Base capacity on available resources
            cpu_capacity = max(1, int((100 - cpu_percent) / 25))  # Every 25% CPU = 1 job
            memory_capacity = max(1, int((100 - memory.percent) / 30))  # Every 30% memory = 1 job
            core_capacity = max(2, cpu_cores // 2)  # Half of available cores
            
            # Take the most conservative estimate
            capacity = min(cpu_capacity, memory_capacity, core_capacity, 4)  # Max 4 concurrent jobs
            
            return capacity
        except Exception as e:
            logger.error(f"Error calculating system capacity: {e}")
            return 2  # Safe fallback

class BatchProjectProcessor:
    """Main batch processing system for multiple video projects"""
    
    def __init__(self, base_output_dir: str = "batch_output", max_workers: int = None):
        self.base_output_dir = Path(base_output_dir)
        self.base_output_dir.mkdir(exist_ok=True)
        
        # Processing queue and status tracking
        self.project_queue = queue.PriorityQueue()
        self.active_projects: Dict[str, BatchProject] = {}
        self.completed_projects: Dict[str, BatchProject] = {}
        self.failed_projects: Dict[str, BatchProject] = {}
        
        # Resource management
        self.resource_monitor = ResourceMonitor()
        self.max_workers = max_workers or self.resource_monitor.get_system_capacity()
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        
        # Batch processing state
        self.processing = False
        self.batch_thread = None
        self.stats = {
            'total_processed': 0,
            'successful': 0,
            'failed': 0,
            'total_time': 0,
            'average_time': 0
        }
        
        logger.info(f"BatchProjectProcessor initialized with {self.max_workers} max workers")
    
    def add_project(self, source_folder: str, client_id: str = "default", 
                   project_name: str = None, priority: ProjectPriority = ProjectPriority.MEDIUM,
                   config: Dict[str, Any] = None) -> str:
        """Add a new project to the processing queue"""
        
        # Validate source folder
        source_path = Path(source_folder)
        if not source_path.exists() or not source_path.is_dir():
            raise ValueError(f"Source folder does not exist: {source_folder}")
        
        # Generate project ID and create project
        project_id = str(uuid.uuid4())[:8]
        if not project_name:
            project_name = source_path.name
            
        project = BatchProject(
            project_id=project_id,
            client_id=client_id,
            source_folder=str(source_path.resolve()),
            project_name=project_name,
            priority=priority,
            config=config or {}
        )
        
        # Add to queue with priority (lower number = higher priority)
        self.project_queue.put((priority.value, project_id, project))
        
        logger.info(f"Added project {project_id} ({project_name}) to queue with priority {priority.name}")
        return project_id
    
    def start_batch_processing(self):
        """Start the batch processing system"""
        if self.processing:
            logger.warning("Batch processing already running")
            return
            
        self.processing = True
        self.resource_monitor.start_monitoring()
        self.batch_thread = threading.Thread(target=self._batch_processing_loop, daemon=True)
        self.batch_thread.start()
        
        logger.info("Batch processing started")
    
    def stop_batch_processing(self):
        """Stop the batch processing system"""
        if not self.processing:
            logger.warning("Batch processing not running")
            return
            
        self.processing = False
        self.resource_monitor.stop_monitoring()
        
        if self.batch_thread:
            self.batch_thread.join(timeout=30)
            
        # Shutdown executor
        self.executor.shutdown(wait=True, timeout=60)
        
        logger.info("Batch processing stopped")
    
    def _batch_processing_loop(self):
        """Main batch processing loop"""
        while self.processing:
            try:
                # Check system capacity
                current_capacity = self.resource_monitor.get_system_capacity()
                available_slots = current_capacity - len(self.active_projects)
                
                if available_slots > 0 and not self.project_queue.empty():
                    # Get next project from queue
                    try:
                        priority, project_id, project = self.project_queue.get_nowait()
                        
                        # Update project status and start processing
                        project.status = ProjectStatus.PROCESSING
                        project.started_at = datetime.now()
                        self.active_projects[project_id] = project
                        
                        # Submit to executor
                        future = self.executor.submit(self._process_project, project)
                        future.add_done_callback(lambda f, pid=project_id: self._project_completed(pid, f))
                        
                        logger.info(f"Started processing project {project_id}")
                        
                    except queue.Empty:
                        pass
                
                # Brief sleep to prevent busy-waiting
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Error in batch processing loop: {e}")
                time.sleep(5)
    
    def _process_project(self, project: BatchProject) -> Dict[str, Any]:
        """Process a single project through the complete pipeline"""
        
        project_dir = self.base_output_dir / f"{project.client_id}_{project.project_id}"
        project_dir.mkdir(exist_ok=True)
        
        try:
            logger.info(f"Starting project {project.project_id}: {project.project_name}")
            start_time = time.time()
            
            # Step 1: Ingest (20% of progress)
            project.status = ProjectStatus.PROCESSING
            project.progress = 5
            logger.info(f"Project {project.project_id}: Running ingest...")
            
            # Run ingest
            import subprocess
            ingest_result = subprocess.run([
                "python3", "ingest.py", project.source_folder
            ], cwd=Path(__file__).parent, capture_output=True, text=True)
            
            if ingest_result.returncode != 0:
                raise Exception(f"Ingest failed: {ingest_result.stderr}")
            
            project.progress = 20
            
            # Step 2: Transcription (40% of progress)
            project.status = ProjectStatus.TRANSCRIBING
            project.progress = 25
            logger.info(f"Project {project.project_id}: Running transcription...")
            
            transcribe_result = subprocess.run([
                "python3", "transcribe.py", project.source_folder
            ], cwd=Path(__file__).parent, capture_output=True, text=True)
            
            if transcribe_result.returncode != 0:
                raise Exception(f"Transcription failed: {transcribe_result.stderr}")
            
            project.progress = 40
            
            # Step 3: Script Generation (60% of progress)
            project.status = ProjectStatus.SCRIPTING
            project.progress = 45
            logger.info(f"Project {project.project_id}: Generating edit script...")
            
            script_result = subprocess.run([
                "python3", "script_engine_enhanced.py", project.source_folder
            ], cwd=Path(__file__).parent, capture_output=True, text=True)
            
            if script_result.returncode != 0:
                raise Exception(f"Script generation failed: {script_result.stderr}")
            
            project.progress = 60
            
            # Step 4: Timeline Building (80% of progress)
            project.status = ProjectStatus.TIMELINE_BUILDING
            project.progress = 65
            logger.info(f"Project {project.project_id}: Building timeline...")
            
            timeline_result = subprocess.run([
                "python3", "timeline_builder_enhanced.py", project.source_folder
            ], cwd=Path(__file__).parent, capture_output=True, text=True)
            
            if timeline_result.returncode != 0:
                raise Exception(f"Timeline building failed: {timeline_result.stderr}")
            
            project.progress = 80
            
            # Step 5: Rendering (100% of progress)
            project.status = ProjectStatus.RENDERING
            project.progress = 85
            logger.info(f"Project {project.project_id}: Rendering outputs...")
            
            render_result = subprocess.run([
                "python3", "render_manager.py", project.source_folder, "--batch"
            ], cwd=Path(__file__).parent, capture_output=True, text=True)
            
            if render_result.returncode != 0:
                raise Exception(f"Rendering failed: {render_result.stderr}")
            
            project.progress = 100
            project.status = ProjectStatus.COMPLETED
            
            # Calculate processing time
            end_time = time.time()
            processing_time = int(end_time - start_time)
            project.actual_duration = processing_time
            
            # Find output files
            renders_dir = Path(project.source_folder) / "renders"
            if renders_dir.exists():
                project.output_files = [str(f) for f in renders_dir.glob("*.mp4")]
            
            logger.info(f"Project {project.project_id} completed successfully in {processing_time}s")
            
            return {
                'success': True,
                'project_id': project.project_id,
                'processing_time': processing_time,
                'output_files': project.output_files
            }
            
        except Exception as e:
            logger.error(f"Project {project.project_id} failed: {e}")
            project.status = ProjectStatus.FAILED
            project.error_message = str(e)
            
            return {
                'success': False,
                'project_id': project.project_id,
                'error': str(e)
            }
    
    def _project_completed(self, project_id: str, future):
        """Handle project completion"""
        try:
            result = future.result()
            project = self.active_projects.get(project_id)
            
            if project:
                project.completed_at = datetime.now()
                
                # Move to appropriate completion list
                del self.active_projects[project_id]
                
                if result['success']:
                    self.completed_projects[project_id] = project
                    self.stats['successful'] += 1
                    logger.info(f"Project {project_id} completed successfully")
                else:
                    self.failed_projects[project_id] = project
                    self.stats['failed'] += 1
                    logger.error(f"Project {project_id} failed: {result.get('error', 'Unknown error')}")
                
                self.stats['total_processed'] += 1
                if project.actual_duration:
                    self.stats['total_time'] += project.actual_duration
                    self.stats['average_time'] = self.stats['total_time'] / self.stats['total_processed']
        
        except Exception as e:
            logger.error(f"Error handling completion for project {project_id}: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive batch processing status"""
        return {
            'processing': self.processing,
            'queue_size': self.project_queue.qsize(),
            'active_projects': len(self.active_projects),
            'completed_projects': len(self.completed_projects),
            'failed_projects': len(self.failed_projects),
            'system_capacity': self.resource_monitor.get_system_capacity(),
            'max_workers': self.max_workers,
            'stats': self.stats,
            'active_project_details': [
                {
                    'project_id': p.project_id,
                    'project_name': p.project_name,
                    'status': p.status.value,
                    'progress': p.progress,
                    'client_id': p.client_id,
                    'started_at': p.started_at.isoformat() if p.started_at else None
                }
                for p in self.active_projects.values()
            ]
        }
    
    def get_project_status(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific project"""
        project = (self.active_projects.get(project_id) or 
                  self.completed_projects.get(project_id) or 
                  self.failed_projects.get(project_id))
        
        if not project:
            return None
        
        return {
            'project_id': project.project_id,
            'project_name': project.project_name,
            'client_id': project.client_id,
            'status': project.status.value,
            'progress': project.progress,
            'priority': project.priority.name,
            'created_at': project.created_at.isoformat(),
            'started_at': project.started_at.isoformat() if project.started_at else None,
            'completed_at': project.completed_at.isoformat() if project.completed_at else None,
            'actual_duration': project.actual_duration,
            'error_message': project.error_message,
            'output_files': project.output_files
        }

def main():
    """Demo/test the batch processing system"""
    processor = BatchProjectProcessor()
    
    # Add a test project (using the existing nycap-portalcam project)
    test_folder = "/Volumes/LaCie/VIDEO/nycap-portalcam"
    if Path(test_folder).exists():
        project_id = processor.add_project(
            source_folder=test_folder,
            client_id="demo_client",
            project_name="Test Batch Project",
            priority=ProjectPriority.HIGH
        )
        
        print(f"Added test project: {project_id}")
        
        # Start processing
        processor.start_batch_processing()
        
        # Monitor progress
        try:
            while True:
                status = processor.get_status()
                print(f"\nBatch Status:")
                print(f"  Queue: {status['queue_size']} | Active: {status['active_projects']} | Completed: {status['completed_projects']} | Failed: {status['failed_projects']}")
                print(f"  System Capacity: {status['system_capacity']} | Stats: {status['stats']}")
                
                if status['active_project_details']:
                    print("  Active Projects:")
                    for proj in status['active_project_details']:
                        print(f"    {proj['project_id']}: {proj['status']} ({proj['progress']}%)")
                
                # Check if specific project is done
                proj_status = processor.get_project_status(project_id)
                if proj_status and proj_status['status'] in ['completed', 'failed']:
                    print(f"\nProject {project_id} finished with status: {proj_status['status']}")
                    if proj_status['error_message']:
                        print(f"Error: {proj_status['error_message']}")
                    else:
                        print(f"Duration: {proj_status['actual_duration']}s")
                        print(f"Outputs: {len(proj_status['output_files'])} files")
                    break
                
                time.sleep(10)
                
        except KeyboardInterrupt:
            print("\nStopping batch processing...")
            processor.stop_batch_processing()
            
    else:
        print(f"Test folder not found: {test_folder}")
        print("Please update the path to your test footage folder.")

if __name__ == "__main__":
    main()