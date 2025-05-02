import unittest
import sys
import os
import json
import time
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from websocket_handler import WebSocketHandler
from remote_controller import RemoteController
from PyQt5.QtCore import QObject, pyqtSignal

class MockServer:
    def __init__(self):
        self.clients = {}
        self.received_messages = []
        self.connected = False

    def connect(self, client):
        self.connected = True
        self.clients[client.username] = client

    def disconnect(self, client):
        if client.username in self.clients:
            del self.clients[client.username]
        self.connected = False

    def receive_message(self, message):
        self.received_messages.append(message)

class TestSystemIntegration(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        self.server = MockServer()
        self.ws_handler = WebSocketHandler("http://localhost:8765", "test_user")
        self.remote_controller = RemoteController(self.ws_handler)
        
        # Track events
        self.screen_frames = []
        self.input_events = []
        self.chat_messages = []
        
        # Connect signals
        self.remote_controller.screen_captured_signal.connect(
            lambda frame: self.screen_frames.append(frame)
        )
        
    def test_complete_session(self):
        """Test a complete user session with all components"""
        # 1. Connect to server
        self.server.connect(self.ws_handler)
        self.assertTrue(self.server.connected)
        
        # 2. Register user
        register_msg = {
            "type": "register",
            "username": "test_user"
        }
        self.ws_handler.send_message(register_msg)
        self.assertTrue(register_msg in self.server.received_messages)
        
        # 3. Start screen sharing
        self.remote_controller.start_screen_sharing(quality=50, fps=10)
        self.assertTrue(self.remote_controller._is_sharing)
        time.sleep(1)  # Wait for some frames
        self.assertGreater(len(self.screen_frames), 0)
        
        # 4. Send and receive chat
        chat_msg = {
            "type": "chat_message",
            "text": "Hello!"
        }
        self.ws_handler.send_message(chat_msg)
        self.assertTrue(chat_msg in self.server.received_messages)
        
        # 5. Process input events
        mouse_event = {
            "type": "move",
            "x": 100,
            "y": 100,
            "button": 1
        }
        self.remote_controller.send_input_event(mouse_event)
        
        # 6. Clean up
        self.remote_controller.stop_screen_sharing()
        self.assertFalse(self.remote_controller._is_sharing)
        self.server.disconnect(self.ws_handler)
        self.assertFalse(self.server.connected)

    def test_error_handling(self):
        """Test error handling across components"""
        # Test connection failure
        self.ws_handler._on_error(None, Exception("Connection failed"))
        self.assertFalse(self.ws_handler.is_connected)
        
        # Test screen sharing with disconnected websocket
        self.remote_controller.start_screen_sharing()
        self.assertFalse(self.remote_controller._is_sharing)
        
        # Test sending message while disconnected
        result = self.ws_handler.send_message({"type": "test"})
        self.assertFalse(result)

    def test_performance(self):
        """Basic performance tests"""
        # Test screen capture performance
        self.remote_controller.start_screen_sharing(quality=50, fps=30)
        start_time = time.time()
        time.sleep(2)
        frame_count = len(self.screen_frames)
        duration = time.time() - start_time
        
        # Check if achieving at least 15 FPS
        self.assertGreater(frame_count / duration, 15)
        
        self.remote_controller.stop_screen_sharing()

if __name__ == '__main__':
    unittest.main()