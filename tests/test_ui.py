import unittest
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtTest import QTest
from PyQt5.QtCore import Qt
from ui import MainWindow
from chat_component import ChatComponent
import time

class TestUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Create the application once"""
        cls.app = QApplication(sys.argv)

    def setUp(self):
        """Set up the test case"""
        self.window = MainWindow()
        self.chat_component = ChatComponent()

    def test_main_window_initialization(self):
        """Test main window initialization"""
        self.assertIsNotNone(self.window)
        self.assertTrue(hasattr(self.window, 'screen_display_widget'))
        self.assertTrue(hasattr(self.window, 'chat_component'))
        self.assertEqual(self.window.windowTitle(), "Screen Sharing App")

    def test_chat_component(self):
        """Test chat component functionality"""
        # Test message input
        test_message = "Test message"
        self.chat_component.message_input.setText(test_message)
        self.assertEqual(self.chat_component.message_input.text(), test_message)

        # Test sending message
        QTest.mouseClick(self.chat_component.send_button, Qt.LeftButton)
        self.assertEqual(self.chat_component.message_input.text(), "")  # Should clear after sending

    def test_screen_display_widget(self):
        """Test screen display widget"""
        self.assertIsNotNone(self.window.screen_display_widget)
        # Test initial state
        self.assertFalse(self.window.screen_display_widget.isEnabled())

    def test_connection_controls(self):
        """Test connection control buttons"""
        # Test connect button
        self.assertTrue(hasattr(self.window, 'connect_button'))
        QTest.mouseClick(self.window.connect_button, Qt.LeftButton)
        
        # Test request view button
        self.assertTrue(hasattr(self.window, 'request_view_button'))
        QTest.mouseClick(self.window.request_view_button, Qt.LeftButton)

    def test_settings_dialog(self):
        """Test settings dialog functionality"""
        # Open settings
        if hasattr(self.window, 'settings_button'):
            QTest.mouseClick(self.window.settings_button, Qt.LeftButton)
            # Test that dialog appears
            dialogs = [w for w in self.app.topLevelWidgets() if w.isWindow()]
            settings_dialog = next((d for d in dialogs if "Settings" in d.windowTitle()), None)
            self.assertIsNotNone(settings_dialog)

    def test_theme_switching(self):
        """Test theme switching functionality"""
        if hasattr(self.window, 'switch_theme'):
            initial_style = self.window.styleSheet()
            self.window.switch_theme()
            new_style = self.window.styleSheet()
            self.assertNotEqual(initial_style, new_style)

    def test_status_bar(self):
        """Test status bar updates"""
        test_status = "Test status"
        self.window.show_status_message(test_status)
        self.assertEqual(self.window.statusBar().currentMessage(), test_status)

    def test_user_list(self):
        """Test user list functionality"""
        if hasattr(self.window, 'users_list'):
            # Test adding users
            test_users = ["user1", "user2", "user3"]
            self.window.update_users_list(test_users)
            self.assertEqual(self.window.users_list.count(), len(test_users))

    def tearDown(self):
        """Clean up after each test"""
        self.window.close()
        self.chat_component.close()

    @classmethod
    def tearDownClass(cls):
        """Clean up the application"""
        cls.app.quit()

if __name__ == '__main__':
    unittest.main()