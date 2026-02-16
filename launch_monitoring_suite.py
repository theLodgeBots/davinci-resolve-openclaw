#!/usr/bin/env python3
"""
Launch Monitoring Suite for DaVinci Resolve OpenClaw
Starts complete enterprise monitoring and dashboard system

Features:
- Starts advanced performance monitor in background
- Launches real-time dashboard web interface
- Manages both processes with proper cleanup
- Professional deployment ready

Usage:
    python3 launch_monitoring_suite.py
    
Then access:
- Performance Dashboard: http://localhost:8081
- Main Project Dashboard: http://localhost:8080
"""

import os
import sys
import time
import signal
import subprocess
import threading
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MonitoringSuite:
    """Manages the complete monitoring suite"""
    
    def __init__(self):
        self.performance_monitor_process = None
        self.dashboard_process = None
        self.running = True
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info("🔴 Shutdown signal received, stopping monitoring suite...")
        self.running = False
        self.cleanup()
        sys.exit(0)
    
    def start_performance_monitor(self):
        """Start the advanced performance monitor in background"""
        try:
            logger.info("🚀 Starting Advanced Performance Monitor...")
            
            # Check if the performance monitor exists
            if not os.path.exists('advanced_performance_monitor.py'):
                logger.error("❌ advanced_performance_monitor.py not found!")
                return False
            
            # Start the performance monitor as a subprocess
            self.performance_monitor_process = subprocess.Popen([
                sys.executable, 'advanced_performance_monitor.py'
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Give it a moment to start
            time.sleep(2)
            
            if self.performance_monitor_process.poll() is None:
                logger.info("✅ Advanced Performance Monitor started successfully")
                return True
            else:
                logger.error("❌ Performance Monitor failed to start")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error starting Performance Monitor: {e}")
            return False
    
    def start_dashboard(self):
        """Start the real-time dashboard"""
        try:
            logger.info("🚀 Starting Real-Time Performance Dashboard...")
            
            # Import and start the dashboard in a separate thread
            from real_time_dashboard import start_dashboard_server
            
            dashboard_thread = threading.Thread(
                target=start_dashboard_server,
                args=(8081,),
                daemon=True
            )
            dashboard_thread.start()
            
            # Give it a moment to start
            time.sleep(2)
            logger.info("✅ Real-Time Performance Dashboard started successfully")
            logger.info("🌐 Dashboard available at: http://localhost:8081")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error starting Dashboard: {e}")
            return False
    
    def check_dependencies(self):
        """Check if all required components are available"""
        logger.info("🔍 Checking system dependencies...")
        
        required_files = [
            'advanced_performance_monitor.py',
            'real_time_dashboard.py'
        ]
        
        missing_files = []
        for file in required_files:
            if not os.path.exists(file):
                missing_files.append(file)
        
        if missing_files:
            logger.error(f"❌ Missing required files: {missing_files}")
            return False
        
        logger.info("✅ All dependencies available")
        return True
    
    def display_startup_info(self):
        """Display startup information and instructions"""
        logger.info("=" * 60)
        logger.info("🎬 DaVinci Resolve OpenClaw - Monitoring Suite")
        logger.info("=" * 60)
        logger.info("")
        logger.info("🚀 Enterprise Performance Monitoring System")
        logger.info("")
        logger.info("📊 Available Interfaces:")
        logger.info("   • Real-Time Dashboard: http://localhost:8081")
        logger.info("   • Main Project Dashboard: http://localhost:8080 (if running)")
        logger.info("")
        logger.info("⚡ Features:")
        logger.info("   • Real-time system metrics (CPU, Memory, Disk)")
        logger.info("   • Performance history and trends")
        logger.info("   • Active alerts and recommendations")
        logger.info("   • Professional enterprise interface")
        logger.info("")
        logger.info("🔧 Controls:")
        logger.info("   • Press Ctrl+C to stop all monitoring services")
        logger.info("   • Dashboard auto-refreshes every 5 seconds")
        logger.info("")
        logger.info("=" * 60)
    
    def monitor_processes(self):
        """Monitor the health of monitoring processes"""
        while self.running:
            try:
                # Check performance monitor process
                if self.performance_monitor_process:
                    if self.performance_monitor_process.poll() is not None:
                        logger.warning("⚠️ Performance Monitor process stopped, restarting...")
                        self.start_performance_monitor()
                
                time.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Error monitoring processes: {e}")
                time.sleep(10)
    
    def cleanup(self):
        """Clean up all processes"""
        logger.info("🧹 Cleaning up monitoring processes...")
        
        if self.performance_monitor_process:
            try:
                self.performance_monitor_process.terminate()
                self.performance_monitor_process.wait(timeout=5)
                logger.info("✅ Performance Monitor stopped")
            except subprocess.TimeoutExpired:
                self.performance_monitor_process.kill()
                logger.info("🔴 Performance Monitor force-killed")
            except Exception as e:
                logger.error(f"Error stopping Performance Monitor: {e}")
        
        logger.info("✅ Monitoring suite cleanup complete")
    
    def run(self):
        """Run the complete monitoring suite"""
        # Set up signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        try:
            # Display startup info
            self.display_startup_info()
            
            # Check dependencies
            if not self.check_dependencies():
                return False
            
            # Start performance monitor
            if not self.start_performance_monitor():
                logger.error("❌ Failed to start Performance Monitor")
                return False
            
            # Start dashboard
            if not self.start_dashboard():
                logger.error("❌ Failed to start Dashboard")
                return False
            
            # Log success
            logger.info("🎉 Monitoring Suite started successfully!")
            logger.info("📊 All systems operational")
            logger.info("")
            logger.info("🌟 Professional enterprise monitoring is now active")
            logger.info("   Visit http://localhost:8081 for the real-time dashboard")
            logger.info("")
            
            # Start process monitoring in background
            monitor_thread = threading.Thread(target=self.monitor_processes, daemon=True)
            monitor_thread.start()
            
            # Keep the main thread alive
            while self.running:
                time.sleep(1)
            
            return True
            
        except KeyboardInterrupt:
            logger.info("🔴 Interrupted by user")
            self.cleanup()
            return True
        except Exception as e:
            logger.error(f"❌ Error running monitoring suite: {e}")
            self.cleanup()
            return False

def main():
    """Main entry point"""
    try:
        # Change to script directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(script_dir)
        
        # Create and run monitoring suite
        suite = MonitoringSuite()
        success = suite.run()
        
        if success:
            logger.info("✅ Monitoring Suite completed successfully")
        else:
            logger.error("❌ Monitoring Suite failed")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()