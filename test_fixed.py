#!/usr/bin/env python3
"""
Test script to verify fixed chat and screen sharing functionality.
This script will launch:
1. The fixed simple_server on port 8766
2. Two instances of the test_client
"""

import os
import sys
import subprocess
import time
import signal
import psutil

# Global processes list to keep track of started processes
processes = []

def start_server():
    """Start the simple_server.py in a new process"""
    print("Starting server...")
    server_process = subprocess.Popen([sys.executable, "simple_server.py"], 
                                      stdout=subprocess.PIPE, 
                                      stderr=subprocess.PIPE,
                                      text=True)
    processes.append(server_process)
    time.sleep(1)  # Give the server a moment to start
    
    # Check if the server started successfully
    if server_process.poll() is not None:
        print("Server failed to start!")
        out, err = server_process.communicate()
        print(f"Output: {out}")
        print(f"Error: {err}")
        cleanup()
        sys.exit(1)
    
    print("Server started successfully.")
    return server_process

def start_client(username, delay=0):
    """Start a test_client.py in a new process with the specified username"""
    if delay > 0:
        time.sleep(delay)
    
    print(f"Starting client with username {username}...")
    
    # Set environment variable for the username
    env = os.environ.copy()
    env["TEST_USERNAME"] = username
    
    # Start the client process
    client_process = subprocess.Popen([sys.executable, "test_client.py"], 
                                      env=env,
                                      stdout=subprocess.PIPE, 
                                      stderr=subprocess.PIPE)
    processes.append(client_process)
    return client_process

def cleanup():
    """Terminate all started processes"""
    print("Cleaning up processes...")
    
    for process in processes:
        try:
            # Get the process and its children
            parent = psutil.Process(process.pid)
            children = parent.children(recursive=True)
            
            # Terminate children
            for child in children:
                try:
                    print(f"Terminating child process {child.pid}...")
                    child.terminate()
                except:
                    pass
            
            # Terminate parent
            print(f"Terminating process {process.pid}...")
            process.terminate()
            
        except Exception as e:
            print(f"Error terminating process: {e}")
    
    # Allow a moment for processes to terminate gracefully
    time.sleep(1)
    
    # Force kill any remaining processes
    for process in processes:
        if process.poll() is None:
            try:
                print(f"Force killing process {process.pid}...")
                process.kill()
            except:
                pass

def main():
    """Main function to run the test"""
    try:
        print("=== Testing Fixed Screen Sharing Application ===")
        print("1. Starting server...")
        server_process = start_server()
        
        print("\n2. Starting first client (User1)...")
        client1_process = start_client("User1")
        
        print("\n3. Starting second client (User2)...")
        client2_process = start_client("User2", 2)
        
        print("\n4. All processes started. Follow the instructions on the client windows:")
        print("   - Connect both clients to the server")
        print("   - Connect from one client to the other")
        print("   - Test chat messaging in both directions")
        print("   - Test screen sharing")
        print("\n5. Press Ctrl+C when done to terminate all processes.")
        
        # Wait for user to finish testing
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nTest interrupted by user.")
    finally:
        cleanup()
        print("Test completed and all processes terminated.")

if __name__ == "__main__":
    main() 