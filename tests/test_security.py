import unittest
import sys
import os
import json
import base64
import websockets
import asyncio
import ssl
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from websocket_handler import WebSocketHandler
from remote_controller import RemoteController

class TestSecurity(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        self.base_url = "http://localhost:8765"
        self.ws_handler = WebSocketHandler(self.base_url, "test_user")

    def test_input_validation(self):
        """Test input validation and sanitization"""
        # Test potentially malicious usernames
        malicious_usernames = [
            "admin'; DROP TABLE users;--",
            "<script>alert('xss')</script>",
            "../../../etc/passwd",
            "user\x00name",
            "user\n\rname"
        ]
        
        for username in malicious_usernames:
            ws = WebSocketHandler(self.base_url, username)
            # Should not raise exception but should sanitize
            self.assertNotEqual(ws.username, username)

    def test_message_sanitization(self):
        """Test message content sanitization"""
        malicious_messages = [
            {"type": "chat_message", "text": "<script>alert('xss')</script>"},
            {"type": "chat_message", "text": "#!/bin/bash\nrm -rf /"},
            {"type": "chat_message", "text": "\x00\x01\x02\x03"},
        ]
        
        for message in malicious_messages:
            # Should not raise exception
            self.ws_handler.send_message(message)

    def test_input_event_validation(self):
        """Test input event validation"""
        mock_ws = type('MockWS', (), {'send_message': lambda x: None})()
        controller = RemoteController(mock_ws)
        
        invalid_events = [
            # Out of bounds coordinates
            {"type": "move", "x": -1, "y": -1},
            {"type": "move", "x": 999999, "y": 999999},
            # Invalid button values
            {"type": "down", "button": 999},
            # Invalid event types
            {"type": "invalid_type"},
            # Missing required fields
            {"type": "move"},
            # Invalid data types
            {"type": "move", "x": "not_a_number", "y": "not_a_number"},
        ]
        
        for event in invalid_events:
            # Should not raise exception but should reject invalid input
            controller._process_input_event(event)

    def test_binary_data_validation(self):
        """Test binary data validation"""
        invalid_binary_data = [
            b"not_an_image",
            b"\x00\x01\x02\x03",
            b"",
            b"A" * (10 * 1024 * 1024)  # Too large
        ]
        
        for data in invalid_binary_data:
            # Should not raise exception but should reject invalid data
            result = self.ws_handler.send_binary_message(data)
            self.assertFalse(result)

    async def test_rate_limiting(self):
        """Test rate limiting for messages and connections"""
        # Test rapid message sending
        message_count = 1000
        start_time = time.time()
        
        for i in range(message_count):
            self.ws_handler.send_message({
                "type": "chat_message",
                "text": f"Spam message {i}"
            })
        
        duration = time.time() - start_time
        rate = message_count / duration
        
        # Should be rate limited to reasonable number
        self.assertLess(rate, 100)  # Less than 100 messages per second

    def test_connection_security(self):
        """Test connection security settings"""
        # Test WSS (secure WebSocket) support
        secure_handler = WebSocketHandler("https://localhost:8765", "test_user")
        self.assertTrue(secure_handler.ws_url.startswith("wss://"))
        
        # Test certificate validation
        with self.assertRaises(Exception):
            # Should fail with self-signed/invalid cert
            secure_handler.connect_ws()

    def test_resource_limits(self):
        """Test resource usage limits"""
        # Test memory limits
        large_message = "X" * (100 * 1024 * 1024)  # 100MB
        result = self.ws_handler.send_message({
            "type": "chat_message",
            "text": large_message
        })
        self.assertFalse(result)  # Should reject too large messages
        
        # Test CPU limits
        remote = RemoteController(self.ws_handler)
        remote.start_screen_sharing(fps=1000)  # Try excessive FPS
        self.assertLess(remote.fps, 60)  # Should be limited to reasonable FPS

if __name__ == '__main__':
    unittest.main()