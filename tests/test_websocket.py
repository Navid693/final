import unittest
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from websocket_handler import WebSocketHandler
from PyQt5.QtCore import QObject

class TestWebSocketHandler(unittest.TestCase):
    def setUp(self):
        """Set up test cases"""
        self.base_url = "http://localhost:8765"
        self.username = "test_user"
        self.ws_handler = WebSocketHandler(self.base_url, self.username)

    def test_websocket_initialization(self):
        """Test WebSocket handler initialization"""
        self.assertEqual(self.ws_handler.username, "test_user")
        self.assertFalse(self.ws_handler.is_connected)
        self.assertIsNone(self.ws_handler.ws)

    def test_websocket_url_construction(self):
        """Test WebSocket URL construction from HTTP URL"""
        self.assertEqual(self.ws_handler.ws_url, "ws://localhost:8765/ws")
        
        # Test HTTPS to WSS conversion
        secure_handler = WebSocketHandler("https://example.com", "test_user")
        self.assertEqual(secure_handler.ws_url, "wss://example.com/ws")

    def test_connection_state(self):
        """Test connection state management"""
        self.assertFalse(self.ws_handler.is_running)
        self.ws_handler.connect_ws()
        self.assertTrue(self.ws_handler.is_running)
        self.ws_handler.stop()
        self.assertFalse(self.ws_handler.is_running)

if __name__ == '__main__':
    unittest.main()