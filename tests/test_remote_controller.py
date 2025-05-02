import unittest
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from remote_controller import RemoteController
from websocket_handler import WebSocketHandler
from PyQt5.QtCore import QObject

class MockWebSocketHandler(QObject):
    """Mock WebSocket handler for testing RemoteController"""
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

class TestRemoteController(unittest.TestCase):
    def setUp(self):
        """Set up test cases"""
        self.mock_ws = MockWebSocketHandler()
        self.remote_controller = RemoteController(self.mock_ws)

    def test_initialization(self):
        """Test RemoteController initialization"""
        self.assertFalse(self.remote_controller._is_sharing)
        self.assertEqual(self.remote_controller.quality, 75)
        self.assertEqual(self.remote_controller.scale_factor, 0.75)
        self.assertEqual(self.remote_controller.fps, 15)
        self.assertEqual(self.remote_controller.monitor_index, 0)

    def test_screen_sharing_control(self):
        """Test screen sharing start/stop"""
        # Start sharing
        self.remote_controller.start_screen_sharing()
        self.assertTrue(self.remote_controller._is_sharing)
        self.assertIsNotNone(self.remote_controller._screen_thread)

        # Stop sharing
        self.remote_controller.stop_screen_sharing()
        self.assertFalse(self.remote_controller._is_sharing)
        self.assertTrue(self.remote_controller._stop_sharing_flag.is_set())

    def test_settings_update(self):
        """Test updating screen sharing settings"""
        new_settings = {
            'quality': 90,
            'scale_factor': 0.5,
            'fps': 30,
            'monitor_index': 1
        }
        self.remote_controller.update_sharing_settings(**new_settings)
        
        self.assertEqual(self.remote_controller.quality, 90)
        self.assertEqual(self.remote_controller.scale_factor, 0.5)
        self.assertEqual(self.remote_controller.fps, 30)
        self.assertEqual(self.remote_controller.monitor_index, 1)

    def test_input_event_processing(self):
        """Test input event processing"""
        # Test mouse event
        mouse_event = {
            'type': 'move',
            'x': 100,
            'y': 200,
            'button': 1
        }
        self.remote_controller._is_sharing = True
        self.remote_controller._process_input_event(mouse_event)
        
        # Test keyboard event
        key_event = {
            'type': 'down',
            'key': 65,  # 'A' key
            'modifiers': 0
        }
        self.remote_controller._process_input_event(key_event)

if __name__ == '__main__':
    unittest.main()