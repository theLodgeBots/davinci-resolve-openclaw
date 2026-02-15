#!/usr/bin/env python3
"""
Launch the DaVinci Resolve OpenClaw Web Dashboard
Simple HTTP server for local development and demo
"""

import http.server
import socketserver
import webbrowser
import os
import sys
from pathlib import Path

def main():
    # Change to the script directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    port = 8080
    handler = http.server.SimpleHTTPRequestHandler
    
    # Try to find an available port
    for port_try in range(8080, 8090):
        try:
            with socketserver.TCPServer(("", port_try), handler) as httpd:
                port = port_try
                break
        except OSError:
            continue
    else:
        print("❌ Could not find an available port")
        return
    
    print(f"🎬 DaVinci Resolve OpenClaw Dashboard")
    print(f"🌐 Starting server at http://localhost:{port}")
    print(f"📁 Serving from: {script_dir}")
    print("📊 Dashboard will open automatically...")
    print("⏹️  Press Ctrl+C to stop the server")
    
    # Open the dashboard in the default browser
    dashboard_url = f"http://localhost:{port}/web_dashboard.html"
    webbrowser.open(dashboard_url)
    
    try:
        with socketserver.TCPServer(("", port), handler) as httpd:
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Dashboard server stopped")

if __name__ == '__main__':
    main()