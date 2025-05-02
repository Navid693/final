"""
Chat Example Application

This example demonstrates how to use the ChatComponent with WebSocketHandler
to create a fully functional chat application.
"""

import sys
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QPushButton, QLabel, QLineEdit, 
                            QListWidget, QGroupBox, QSplitter)
from PyQt5.QtCore import Qt

from chat_component import ChatComponent
from websocket_handler import WebSocketHandler

class ChatExample(QMainWindow):
    """Simple example of using the ChatComponent with WebSocket for communication"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chat Example")
        self.resize(800, 600)
        
        # WebSocket handler
        self.ws_handler = None
        self.username = None
        self.current_peer = None
        
        # Set up UI
        self.setup_ui()
    
    def setup_ui(self):
        """Create the user interface"""
        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        
        # Connection section
        connection_group = QGroupBox("Connection")
        connection_layout = QVBoxLayout()
        connection_group.setLayout(connection_layout)
        
        # Server URL and username
        server_layout = QHBoxLayout()
        server_layout.addWidget(QLabel("Server URL:"))
        self.server_url_edit = QLineEdit("ws://localhost:8765")
        server_layout.addWidget(self.server_url_edit)
        server_layout.addWidget(QLabel("Username:"))
        self.username_edit = QLineEdit("User")
        server_layout.addWidget(self.username_edit)
        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.handle_connect)
        server_layout.addWidget(self.connect_button)
        connection_layout.addLayout(server_layout)
        
        # User list and peer connection
        users_layout = QHBoxLayout()
        users_layout.addWidget(QLabel("Online Users:"))
        self.users_list = QListWidget()
        users_layout.addWidget(self.users_list)
        self.connect_peer_button = QPushButton("Connect to Selected User")
        self.connect_peer_button.clicked.connect(self.handle_connect_to_peer)
        self.connect_peer_button.setEnabled(False)
        users_layout.addWidget(self.connect_peer_button)
        self.disconnect_peer_button = QPushButton("Disconnect from Peer")
        self.disconnect_peer_button.clicked.connect(self.handle_disconnect_from_peer)
        self.disconnect_peer_button.setEnabled(False)
        users_layout.addWidget(self.disconnect_peer_button)
        connection_layout.addLayout(users_layout)
        
        # Add connection section to main layout
        main_layout.addWidget(connection_group)
        
        # Add the chat component
        self.chat_component = ChatComponent()
        self.chat_component.message_sent_signal.connect(self.handle_message_sent)
        main_layout.addWidget(self.chat_component, 1)
        
        # Status bar
        self.statusBar().showMessage("Disconnected")
    
    def handle_connect(self):
        """Handle the connect button click"""
        server_url = self.server_url_edit.text()
        username = self.username_edit.text()
        
        if not server_url or not username:
            self.statusBar().showMessage("Please enter server URL and username")
            return
        
        self.username = username
        self.chat_component.set_username(username)
        
        # Create WebSocket handler
        self.ws_handler = WebSocketHandler(server_url, username)
        
        # Connect signals
        self.ws_handler.connected_signal.connect(self.on_ws_connected)
        self.ws_handler.disconnected_signal.connect(self.on_ws_disconnected)
        self.ws_handler.error_signal.connect(self.on_ws_error)
        self.ws_handler.user_registered_signal.connect(self.on_user_registered)
        self.ws_handler.users_list_updated_signal.connect(self.on_users_list_updated)
        self.ws_handler.peer_connection_requested_signal.connect(self.on_peer_connection_requested)
        self.ws_handler.peer_connected_signal.connect(self.on_peer_connected)
        self.ws_handler.peer_disconnected_signal.connect(self.on_peer_disconnected)
        self.ws_handler.chat_message_received_signal.connect(self.on_chat_message_received)
        
        # Connect to server
        self.statusBar().showMessage(f"Connecting to {server_url}...")
        self.ws_handler.connect_ws()
        
        # Disable connect button
        self.connect_button.setEnabled(False)
    
    def handle_connect_to_peer(self):
        """Handle connect to peer button click"""
        if not self.ws_handler:
            return
            
        selected_items = self.users_list.selectedItems()
        if not selected_items:
            self.statusBar().showMessage("Please select a user to connect to")
            return
            
        peer_username = selected_items[0].text()
        
        if peer_username == self.username:
            self.statusBar().showMessage("Cannot connect to yourself")
            return
            
        self.statusBar().showMessage(f"Requesting connection to {peer_username}...")
        self.ws_handler.request_connection(peer_username)
    
    def handle_disconnect_from_peer(self):
        """Handle disconnect from peer button click"""
        if not self.ws_handler or not self.current_peer:
            return
            
        self.ws_handler.disconnect_from_peer()
        self.chat_component.add_connection_message(self.current_peer, False)
        self.statusBar().showMessage(f"Disconnected from {self.current_peer}")
        self.current_peer = None
        self.chat_component.set_peer(None)
        
        # Update UI
        self.connect_peer_button.setEnabled(True)
        self.disconnect_peer_button.setEnabled(False)
    
    def handle_message_sent(self, message):
        """Handle a message sent from the chat component"""
        if not self.ws_handler or not self.current_peer:
            return
            
        # Send message through WebSocket
        self.ws_handler.send_chat_message(self.current_peer, message)
    
    def on_ws_connected(self):
        """Handle WebSocket connected signal"""
        self.statusBar().showMessage("Connected to server")
        self.chat_component.add_system_message("Connected to server", "info")
    
    def on_ws_disconnected(self, reason):
        """Handle WebSocket disconnected signal"""
        self.statusBar().showMessage(f"Disconnected from server: {reason}")
        self.chat_component.add_system_message(f"Disconnected from server: {reason}", "error")
        
        # Reset UI
        self.connect_button.setEnabled(True)
        self.connect_peer_button.setEnabled(False)
        self.disconnect_peer_button.setEnabled(False)
        self.current_peer = None
        self.chat_component.set_peer(None)
        
        # Clear users list
        self.users_list.clear()
    
    def on_ws_error(self, error):
        """Handle WebSocket error signal"""
        self.statusBar().showMessage(f"WebSocket error: {error}")
        self.chat_component.add_system_message(f"Error: {error}", "error")
    
    def on_user_registered(self, success, message):
        """Handle user registered signal"""
        if success:
            self.statusBar().showMessage(f"Registered: {message}")
            self.chat_component.add_system_message(f"Registered as {self.username}", "success")
        else:
            self.statusBar().showMessage(f"Registration failed: {message}")
            self.chat_component.add_system_message(f"Registration failed: {message}", "error")
            self.connect_button.setEnabled(True)
    
    def on_users_list_updated(self, users):
        """Handle users list updated signal"""
        # Clear and repopulate the list
        self.users_list.clear()
        
        # Add all users except our own username
        for user in users:
            if user != self.username:
                self.users_list.addItem(user)
        
        # Enable connect button if there are other users
        self.connect_peer_button.setEnabled(self.users_list.count() > 0)
    
    def on_peer_connection_requested(self, username):
        """Handle peer connection request signal"""
        from PyQt5.QtWidgets import QMessageBox
        
        # Show confirmation dialog
        reply = QMessageBox.question(
            self, 
            "Connection Request",
            f"User '{username}' wants to connect. Accept?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Accept connection
            self.ws_handler.accept_connection(username)
            self.current_peer = username
            self.chat_component.set_peer(username)
            self.chat_component.add_connection_message(username, True)
            self.statusBar().showMessage(f"Connected to {username}")
            
            # Update UI
            self.connect_peer_button.setEnabled(False)
            self.disconnect_peer_button.setEnabled(True)
        else:
            # Reject connection
            self.ws_handler.reject_connection(username, "Request declined")
    
    def on_peer_connected(self, username):
        """Handle peer connected signal"""
        self.current_peer = username
        self.chat_component.set_peer(username)
        self.chat_component.add_connection_message(username, True)
        self.statusBar().showMessage(f"Connected to {username}")
        
        # Update UI
        self.connect_peer_button.setEnabled(False)
        self.disconnect_peer_button.setEnabled(True)
    
    def on_peer_disconnected(self, username, reason):
        """Handle peer disconnected signal"""
        if self.current_peer == username:
            self.chat_component.add_connection_message(username, False)
            self.chat_component.add_system_message(f"Reason: {reason}", "warning")
            self.statusBar().showMessage(f"Disconnected from {username}: {reason}")
            self.current_peer = None
            self.chat_component.set_peer(None)
            
            # Update UI
            self.connect_peer_button.setEnabled(True)
            self.disconnect_peer_button.setEnabled(False)
    
    def on_chat_message_received(self, username, message):
        """Handle chat message received signal"""
        if username == self.current_peer:
            self.chat_component.add_incoming_message(username, message)
            
            # If window is not in focus, update the title
            if not self.isActiveWindow():
                self.setWindowTitle(f"* New message from {username} - Chat Example")
    
    def closeEvent(self, event):
        """Handle window close event"""
        # Clean up WebSocket connection
        if self.ws_handler:
            self.ws_handler.stop()
        
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Load stylesheet if available
    css_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "styles/chat_styles.qss")
    if os.path.exists(css_path):
        with open(css_path, "r") as f:
            app.setStyleSheet(f.read())
    
    window = ChatExample()
    window.show()
    sys.exit(app.exec_()) 