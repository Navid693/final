import unittest
import sys
import os
import json
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from websocket_handler import WebSocketHandler
from PyQt5.QtCore import QObject, pyqtSignal

class MockWebSocket:
    def __init__(self):
        self.sent_messages = []
        
    def send(self, message):
        self.sent_messages.append(message)

class TestChatAndUsers(unittest.TestCase):
    def setUp(self):
        """Set up test cases"""
        self.ws_handler = WebSocketHandler("http://localhost:8765", "test_user")
        self.ws_handler.ws = MockWebSocket()
        
        # Track emitted signals
        self.received_chat_messages = []
        self.users_list_updates = []
        
        # Connect to signals
        self.ws_handler.chat_message_received_signal.connect(
            lambda sender, msg: self.received_chat_messages.append((sender, msg))
        )
        self.ws_handler.users_list_updated_signal.connect(
            lambda users: self.users_list_updates.append(users)
        )

    def test_send_chat_message(self):
        """Test sending chat messages"""
        message = "Hello, World!"
        self.ws_handler.send_message({
            "type": "chat_message",
            "text": message
        })
        
        sent_message = json.loads(self.ws_handler.ws.sent_messages[-1])
        self.assertEqual(sent_message["type"], "chat_message")
        self.assertEqual(sent_message["text"], message)

    def test_receive_chat_message(self):
        """Test receiving chat messages"""
        test_message = {
            "type": "chat_message",
            "from_user": "other_user",
            "text": "Test message"
        }
        
        # Simulate receiving a message
        self.ws_handler._on_message(None, json.dumps(test_message))
        
        # Check if signal was emitted with correct data
        self.assertEqual(len(self.received_chat_messages), 1)
        sender, msg = self.received_chat_messages[0]
        self.assertEqual(sender, "other_user")
        self.assertEqual(msg, "Test message")

    def test_users_list_update(self):
        """Test users list updates"""
        test_users = ["user1", "user2", "user3"]
        test_message = {
            "type": "users_list",
            "users": test_users
        }
        
        # Simulate receiving users list
        self.ws_handler._on_message(None, json.dumps(test_message))
        
        # Check if signal was emitted with correct data
        self.assertEqual(len(self.users_list_updates), 1)
        self.assertEqual(self.users_list_updates[0], test_users)

    def test_user_registration(self):
        """Test user registration process"""
        # Test successful registration
        success_response = {
            "type": "register_response",
            "success": True,
            "message": "Registration successful"
        }
        self.ws_handler._on_message(None, json.dumps(success_response))
        self.assertTrue(self.ws_handler.is_connected)
        
        # Test failed registration
        fail_response = {
            "type": "register_response",
            "success": False,
            "message": "Username already taken"
        }
        self.ws_handler._on_message(None, json.dumps(fail_response))
        self.assertFalse(self.ws_handler.is_connected)

if __name__ == '__main__':
    unittest.main()