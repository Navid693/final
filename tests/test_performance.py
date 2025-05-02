import unittest
import sys
import os
import time
import psutil
import threading
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from remote_controller import RemoteController
from websocket_handler import WebSocketHandler
from PyQt5.QtCore import QObject

class MockWebSocketHandler(QObject):
    def __init__(self):
        super().__init__()
        self.sent_messages = []
        self.sent_binary = []
        self.is_connected = True

    def send_message(self, message):
        self.sent_messages.append(message)
        return True

    def send_binary_message(self, data):
        self.sent_binary.append(data)
        return True

class TestPerformance(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        self.mock_ws = MockWebSocketHandler()
        self.remote_controller = RemoteController(self.mock_ws)
        self.process = psutil.Process()

    def test_screen_capture_performance(self):
        """Test screen capture performance and resource usage"""
        # Track initial resource usage
        initial_cpu = self.process.cpu_percent()
        initial_memory = self.process.memory_info().rss / 1024 / 1024  # MB

        # Start screen capture with high quality and FPS
        self.remote_controller.start_screen_sharing(
            quality=90,
            scale_factor=1.0,
            fps=30
        )

        # Monitor for 5 seconds
        frames = []
        start_time = time.time()
        time.sleep(5)
        
        # Stop capture
        self.remote_controller.stop_screen_sharing()
        duration = time.time() - start_time

        # Get final resource usage
        final_cpu = self.process.cpu_percent()
        final_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        
        # Assert performance metrics
        self.assertLess(final_memory - initial_memory, 500)  # Memory increase < 500MB
        self.assertLess(final_cpu - initial_cpu, 50)  # CPU increase < 50%
        
        # Check frame rate
        frame_count = len(self.mock_ws.sent_binary)
        actual_fps = frame_count / duration
        self.assertGreater(actual_fps, 15)  # Should achieve at least 15 FPS

    def test_concurrent_connections(self):
        """Test performance with multiple concurrent connections"""
        max_connections = 10
        connections = []
        
        try:
            # Create multiple connections
            for i in range(max_connections):
                ws = WebSocketHandler(f"http://localhost:8765", f"test_user_{i}")
                ws.connect_ws()
                connections.append(ws)
                
                # Check resource usage
                memory_usage = self.process.memory_info().rss / 1024 / 1024
                self.assertLess(memory_usage, 1000)  # Total memory should stay under 1GB
                
                # Brief pause between connections
                time.sleep(0.1)
        
        finally:
            # Clean up connections
            for ws in connections:
                ws.stop()

    def test_message_throughput(self):
        """Test message handling throughput"""
        message_count = 1000
        start_time = time.time()
        
        # Send many messages rapidly
        for i in range(message_count):
            self.mock_ws.send_message({
                "type": "test_message",
                "content": f"Test message {i}"
            })
        
        duration = time.time() - start_time
        messages_per_second = message_count / duration
        
        # Should handle at least 1000 messages per second
        self.assertGreater(messages_per_second, 1000)

    def test_input_event_latency(self):
        """Test input event processing latency"""
        event_count = 100
        total_latency = 0
        
        for i in range(event_count):
            start_time = time.time()
            
            # Process mouse event
            self.remote_controller._process_input_event({
                "type": "move",
                "x": i,
                "y": i,
                "button": 1
            })
            
            latency = time.time() - start_time
            total_latency += latency
        
        average_latency = total_latency / event_count
        # Input processing should take less than 1ms on average
        self.assertLess(average_latency, 0.001)

    def test_memory_leaks(self):
        """Test for memory leaks during extended operation"""
        initial_memory = self.process.memory_info().rss
        
        # Perform operations that might leak memory
        for _ in range(100):
            # Start and stop screen sharing
            self.remote_controller.start_screen_sharing()
            time.sleep(0.1)
            self.remote_controller.stop_screen_sharing()
            
            # Send and process messages
            for i in range(10):
                self.mock_ws.send_message({"type": "test", "data": "x" * 1000})
        
        # Force garbage collection
        import gc
        gc.collect()
        
        final_memory = self.process.memory_info().rss
        memory_growth = final_memory - initial_memory
        
        # Memory growth should be minimal after garbage collection
        self.assertLess(memory_growth, 10 * 1024 * 1024)  # Less than 10MB growth

if __name__ == '__main__':
    unittest.main()