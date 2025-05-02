"""
Chat Component Module

This module contains a reusable chat component for PyQt5 applications.
Features include:
- Styled chat bubbles with timestamps
- Different styles for sent and received messages
- Connection status notifications
- Input field with send button
"""

import time
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QLineEdit, QTextEdit)
from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot

class ChatComponent(QWidget):
    """A reusable chat component that can be integrated into any PyQt5 application."""
    
    # Define signals
    message_sent_signal = pyqtSignal(str)  # Emitted when a message is sent
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.username = "You"  # Default username for this user
        self.current_peer = None  # Current peer username
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the chat UI components"""
        # Main layout
        layout = QVBoxLayout(self)
        
        # Chat display
        layout.addWidget(QLabel("Chat:"))
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        layout.addWidget(self.chat_display, 1)
        
        # Chat input
        chat_input_layout = QHBoxLayout()
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Type message here...")
        self.chat_input.returnPressed.connect(self.handle_send_chat)
        chat_input_layout.addWidget(self.chat_input)
        self.send_chat_button = QPushButton("Send")
        self.send_chat_button.clicked.connect(self.handle_send_chat)
        chat_input_layout.addWidget(self.send_chat_button)
        layout.addLayout(chat_input_layout)
        
        # Set some sensible default size
        self.setMinimumWidth(300)
        self.setMinimumHeight(400)
    
    def set_username(self, username):
        """Set the current user's username"""
        self.username = username
    
    def set_peer(self, peer_username):
        """Set the peer's username"""
        self.current_peer = peer_username
    
    def handle_send_chat(self):
        """Handle send chat button click"""
        if not self.current_peer:
            return
            
        text = self.chat_input.text().strip()
        if not text:
            return
        
        # Add to chat display with timestamp
        self.add_outgoing_message(text)
        
        # Emit signal with message
        self.message_sent_signal.emit(text)
        
        # Clear input
        self.chat_input.clear()
    
    def add_outgoing_message(self, text):
        """Add an outgoing message to the chat display"""
        timestamp = time.strftime("%H:%M:%S")
        self.chat_display.append(
            f'<div style="text-align: right;"><span style="color: #0066cc; font-weight: bold;">{self.username}</span> '
            f'<span style="color: #999; font-size: 0.8em;">{timestamp}</span><br/>'
            f'<span style="background-color: #e6f2ff; padding: 5px; border-radius: 10px; display: inline-block;">{text}</span></div>'
        )
        self.chat_display.verticalScrollBar().setValue(self.chat_display.verticalScrollBar().maximum())
    
    def add_incoming_message(self, sender, text):
        """Add an incoming message to the chat display"""
        timestamp = time.strftime("%H:%M:%S")
        self.chat_display.append(
            f'<div style="text-align: left;"><span style="color: #cc6600; font-weight: bold;">{sender}</span> '
            f'<span style="color: #999; font-size: 0.8em;">{timestamp}</span><br/>'
            f'<span style="background-color: #f2f2f2; padding: 5px; border-radius: 10px; display: inline-block;">{text}</span></div>'
        )
        self.chat_display.verticalScrollBar().setValue(self.chat_display.verticalScrollBar().maximum())
    
    def add_system_message(self, text, message_type="info"):
        """Add a system message to the chat display
        
        message_type can be "info", "success", "warning", or "error"
        """
        timestamp = time.strftime("%H:%M:%S")
        
        # Set style based on message type
        style = ""
        if message_type == "info":
            style = "background-color: #e6f7ff; color: #0066cc;"
        elif message_type == "success":
            style = "background-color: #e6ffe6; color: #006600;"
        elif message_type == "warning":
            style = "background-color: #fff7e6; color: #cc6600;"
        elif message_type == "error":
            style = "background-color: #ffe6e6; color: #cc0000;"
        
        self.chat_display.append(
            f'<div style="text-align: center; margin: 10px;"><span style="{style} padding: 5px; border-radius: 10px;">'
            f'{text} ({timestamp})</span></div>'
        )
        self.chat_display.verticalScrollBar().setValue(self.chat_display.verticalScrollBar().maximum())
    
    def add_connection_message(self, username, connected=True):
        """Add a connection status message"""
        timestamp = time.strftime("%H:%M:%S")
        if connected:
            self.add_system_message(f"Connected to {username} at {timestamp}", "success")
        else:
            self.add_system_message(f"Disconnected from {username} at {timestamp}", "error")
    
    def clear_chat(self):
        """Clear the chat display"""
        self.chat_display.clear()


# Example usage:
if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    chat = ChatComponent()
    chat.set_username("User1")
    chat.set_peer("User2")
    chat.add_system_message("Welcome to the chat!", "info")
    chat.add_connection_message("User2", True)
    chat.add_outgoing_message("Hello there!")
    chat.add_incoming_message("User2", "Hi! How are you?")
    chat.add_outgoing_message("I'm fine, thanks!")
    chat.add_system_message("User2 is typing...", "info")
    chat.add_incoming_message("User2", "Great! Let's get started.")
    
    chat.show()
    sys.exit(app.exec_()) 