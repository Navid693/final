import sys
import os
import time
import json
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QLineEdit, QComboBox, QSlider, QGroupBox,
                             QListWidget, QTextEdit, QSplitter)
from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot, QRect, QPoint
from PyQt5.QtGui import QPixmap, QImage

from websocket_handler import WebSocketHandler
from remote_controller import RemoteController

class TestClient(QMainWindow):
    """Simple test client to demonstrate screen sharing and remote control"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Screen Sharing Test Client")
        self.resize(1200, 800)
        
        # Create websocket handler
        self.ws_handler = None
        self.remote_controller = None
        self.username = None
        self.current_peer = None
        
        # Setup UI
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the user interface"""
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
        self.username_edit = QLineEdit("TestUser")
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
        
        # Create a splitter for the screen view and chat
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter, 1)
        
        # Screen view section
        screen_widget = QWidget()
        screen_layout = QVBoxLayout(screen_widget)
        
        # Screen display with custom label that captures mouse events
        self.screen_label = ScreenViewLabel("No screen sharing active")
        self.screen_label.setAlignment(Qt.AlignCenter)
        self.screen_label.setMinimumSize(640, 480)
        self.screen_label.setStyleSheet("background-color: #333; color: white;")
        self.screen_label.setFocusPolicy(Qt.StrongFocus)  # Make sure it can receive keyboard focus
        self.screen_label.setMouseTracking(True)  # Enable mouse tracking
        screen_layout.addWidget(self.screen_label, 1)
        
        # Connect signals for remote control later
        self.screen_label.mouse_event_signal.connect(self.handle_remote_mouse_event)
        self.screen_label.key_event_signal.connect(self.handle_remote_key_event)
        
        # Sharing controls
        sharing_group = QGroupBox("Screen Sharing Controls")
        sharing_layout = QVBoxLayout()
        sharing_group.setLayout(sharing_layout)
        
        # Start/Stop buttons
        buttons_layout = QHBoxLayout()
        self.start_sharing_button = QPushButton("Start Sharing")
        self.start_sharing_button.clicked.connect(self.handle_start_sharing)
        self.start_sharing_button.setEnabled(False)
        buttons_layout.addWidget(self.start_sharing_button)
        
        self.stop_sharing_button = QPushButton("Stop Sharing")
        self.stop_sharing_button.clicked.connect(self.handle_stop_sharing)
        self.stop_sharing_button.setEnabled(False)
        buttons_layout.addWidget(self.stop_sharing_button)
        sharing_layout.addLayout(buttons_layout)
        
        # Settings
        settings_layout = QHBoxLayout()
        
        # Quality slider
        quality_layout = QVBoxLayout()
        quality_layout.addWidget(QLabel("Quality:"))
        self.quality_slider = QSlider(Qt.Horizontal)
        self.quality_slider.setRange(10, 100)
        self.quality_slider.setValue(75)
        self.quality_slider.setTickPosition(QSlider.TicksBelow)
        self.quality_slider.setTickInterval(10)
        self.quality_label = QLabel("75%")
        self.quality_slider.valueChanged.connect(lambda v: self.quality_label.setText(f"{v}%"))
        quality_layout.addWidget(self.quality_slider)
        quality_layout.addWidget(self.quality_label)
        settings_layout.addLayout(quality_layout)
        
        # Scale slider
        scale_layout = QVBoxLayout()
        scale_layout.addWidget(QLabel("Scale:"))
        self.scale_slider = QSlider(Qt.Horizontal)
        self.scale_slider.setRange(25, 100)
        self.scale_slider.setValue(75)
        self.scale_slider.setTickPosition(QSlider.TicksBelow)
        self.scale_slider.setTickInterval(25)
        self.scale_label = QLabel("75%")
        self.scale_slider.valueChanged.connect(lambda v: self.scale_label.setText(f"{v}%"))
        scale_layout.addWidget(self.scale_slider)
        scale_layout.addWidget(self.scale_label)
        settings_layout.addLayout(scale_layout)
        
        # FPS combobox
        fps_layout = QVBoxLayout()
        fps_layout.addWidget(QLabel("FPS:"))
        self.fps_combo = QComboBox()
        for fps in [5, 10, 15, 20, 30]:
            self.fps_combo.addItem(str(fps), fps)
        self.fps_combo.setCurrentIndex(2)  # Default to 15 FPS
        fps_layout.addWidget(self.fps_combo)
        settings_layout.addLayout(fps_layout)
        
        # Monitor selection
        monitor_layout = QVBoxLayout()
        monitor_layout.addWidget(QLabel("Monitor:"))
        self.monitor_combo = QComboBox()
        # Will be populated when connected
        monitor_layout.addWidget(self.monitor_combo)
        settings_layout.addLayout(monitor_layout)
        
        sharing_layout.addLayout(settings_layout)
        screen_layout.addWidget(sharing_group)
        
        # Add screen widget to splitter
        splitter.addWidget(screen_widget)
        
        # Chat section
        chat_widget = QWidget()
        chat_layout = QVBoxLayout(chat_widget)
        
        # Chat display
        chat_layout.addWidget(QLabel("Chat:"))
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        chat_layout.addWidget(self.chat_display, 1)
        
        # Chat input
        chat_input_layout = QHBoxLayout()
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Type message here...")
        self.chat_input.returnPressed.connect(self.handle_send_chat)
        chat_input_layout.addWidget(self.chat_input)
        self.send_chat_button = QPushButton("Send")
        self.send_chat_button.clicked.connect(self.handle_send_chat)
        chat_input_layout.addWidget(self.send_chat_button)
        chat_layout.addLayout(chat_input_layout)
        
        # Add chat widget to splitter
        splitter.addWidget(chat_widget)
        
        # Set the splitter sizes
        splitter.setSizes([700, 300])
        
        # Status bar
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Not connected")
        
        # Populate monitor combobox
        self.populate_monitors()
    
    def populate_monitors(self):
        """Populate the monitor selection combobox"""
        import screeninfo
        try:
            monitors = screeninfo.get_monitors()
            self.monitor_combo.clear()
            
            if not monitors:
                print("No monitors detected!")
                self.monitor_combo.addItem("Default Monitor", 0)
                return
                
            print(f"Found {len(monitors)} monitors:")
            for i, monitor in enumerate(monitors):
                # Use monitor name if available, otherwise use index
                monitor_name = getattr(monitor, 'name', f"Monitor {i+1}")
                
                # Check if it's the primary monitor
                is_primary = getattr(monitor, 'is_primary', False)
                primary_text = " (Primary)" if is_primary else ""
                
                # Create descriptive text with dimensions and position
                item_text = f"{monitor_name}{primary_text} - {monitor.width}×{monitor.height} at ({monitor.x},{monitor.y})"
                
                # Add to combobox
                self.monitor_combo.addItem(item_text, i)
                print(f"  Monitor {i}: {item_text}")
                
        except Exception as e:
            print(f"Error getting monitors: {e}")
            import traceback
            traceback.print_exc()
            # Add a default option
            self.monitor_combo.addItem("Default Monitor", 0)
    
    def handle_connect(self):
        """Handle connect button click"""
        try:
            server_url = self.server_url_edit.text()
            username = self.username_edit.text().strip()
            
            if not server_url or not username:
                self.status_bar.showMessage("Please enter server URL and username")
                return
            
            # Clear any random suffix from username
            if '_' in username and username.split('_')[-1].isdigit():
                parts = username.split('_')
                if len(parts) > 1 and parts[-1].isdigit():
                    username = '_'.join(parts[:-1])
                    self.username_edit.setText(username)
            
            self.username = username
            
            # Disable connect button to prevent multiple connections
            self.connect_button.setEnabled(False)
            self.status_bar.showMessage(f"Connecting to {server_url}...")
            
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
            
            # Create RemoteController
            self.remote_controller = RemoteController(self.ws_handler)
            
            # Connect RemoteController signals
            self.remote_controller.screen_captured_signal.connect(self.on_screen_captured)
            self.remote_controller.screen_share_status_signal.connect(self.on_screen_share_status_changed)
            self.remote_controller.fps_updated_signal.connect(self.on_fps_updated)
            self.remote_controller.error_signal.connect(self.on_remote_controller_error)
            
            # Connect to server
            self.ws_handler.connect_ws()
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.status_bar.showMessage(f"Error connecting: {str(e)}")
            self.connect_button.setEnabled(True)
            print(f"Error in handle_connect: {e}")
    
    def handle_connect_to_peer(self):
        """Handle connect to peer button click"""
        if not self.ws_handler:
            return
            
        selected_items = self.users_list.selectedItems()
        if not selected_items:
            self.status_bar.showMessage("Please select a user to connect to")
            return
            
        peer_username = selected_items[0].text()
        
        if peer_username == self.username:
            self.status_bar.showMessage("Cannot connect to yourself")
            return
            
        self.status_bar.showMessage(f"Requesting connection to {peer_username}...")
        self.ws_handler.request_connection(peer_username)
    
    def handle_disconnect_from_peer(self):
        """Handle disconnect from peer button click"""
        if not self.ws_handler or not self.current_peer:
            return
            
        self.ws_handler.disconnect_from_peer()
        self.status_bar.showMessage(f"Disconnected from {self.current_peer}")
        self.current_peer = None
        
        # Update UI
        self.connect_peer_button.setEnabled(True)
        self.disconnect_peer_button.setEnabled(False)
        self.start_sharing_button.setEnabled(False)
        self.stop_sharing_button.setEnabled(False)
    
    def handle_start_sharing(self):
        """Handle start sharing button click"""
        if not self.remote_controller or not self.current_peer:
            self.status_bar.showMessage("Cannot start sharing: No peer connected")
            return
            
        try:
            # Get settings from UI
            quality = self.quality_slider.value()
            scale = self.scale_slider.value() / 100.0
            fps_idx = self.fps_combo.currentIndex()
            fps = int(self.fps_combo.itemText(fps_idx))
            monitor_idx = self.monitor_combo.currentData()
            
            print(f"Starting screen sharing with settings: Quality={quality}, Scale={scale}, FPS={fps}, Monitor={monitor_idx}")
            
            # Update UI before starting sharing to prevent user from clicking again
            self.start_sharing_button.setEnabled(False)
            self.stop_sharing_button.setEnabled(True)
            self.status_bar.showMessage(f"Starting screen sharing with {self.current_peer}...")
            
            # Start sharing
            self.remote_controller.start_screen_sharing(
                quality=quality,
                scale_factor=scale,
                fps=fps,
                monitor_index=monitor_idx
            )
            
            # Add to chat
            self.chat_display.append(f"[System] Started sharing screen with {self.current_peer}")
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.status_bar.showMessage(f"Error starting screen sharing: {str(e)}")
            print(f"Error starting screen sharing: {e}")
            
            # Reset UI in case of error
            self.start_sharing_button.setEnabled(True)
            self.stop_sharing_button.setEnabled(False)
        
    def handle_stop_sharing(self):
        """Handle stop sharing button click"""
        if not self.remote_controller:
            return
            
        try:
            # Update UI before stopping sharing
            self.stop_sharing_button.setEnabled(False)
            self.status_bar.showMessage("Stopping screen sharing...")
            
            # Stop sharing
            self.remote_controller.stop_screen_sharing()
            
            # Update UI
            self.start_sharing_button.setEnabled(True)
            if self.current_peer:
                self.status_bar.showMessage(f"Connected to {self.current_peer}")
                
            # Add to chat
            self.chat_display.append("[System] Stopped sharing screen")
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.status_bar.showMessage(f"Error stopping screen sharing: {str(e)}")
            print(f"Error stopping screen sharing: {e}")
            
            # Make sure the UI is consistent even if there was an error
            self.start_sharing_button.setEnabled(True)
            self.stop_sharing_button.setEnabled(False)
    
    def handle_send_chat(self):
        """Handle send chat button click"""
        if not self.ws_handler or not self.current_peer:
            return
            
        text = self.chat_input.text().strip()
        if not text:
            return
            
        # Send chat message
        self.ws_handler.send_chat_message(self.current_peer, text)
        
        # Add to chat display with timestamp
        timestamp = time.strftime("%H:%M:%S")
        self.chat_display.append(f'<div style="text-align: right;"><span style="color: #0066cc; font-weight: bold;">You</span> <span style="color: #999; font-size: 0.8em;">{timestamp}</span><br/><span style="background-color: #e6f2ff; padding: 5px; border-radius: 10px; display: inline-block;">{text}</span></div>')
        
        # Clear input
        self.chat_input.clear()
    
    def on_ws_connected(self):
        """Handle WebSocket connected signal"""
        self.status_bar.showMessage("Connected to server")
    
    def on_ws_disconnected(self, reason):
        """Handle WebSocket disconnected signal"""
        self.status_bar.showMessage(f"Disconnected from server: {reason}")
        
        # Reset UI
        self.connect_button.setEnabled(True)
        self.connect_peer_button.setEnabled(False)
        self.disconnect_peer_button.setEnabled(False)
        self.start_sharing_button.setEnabled(False)
        self.stop_sharing_button.setEnabled(False)
        self.current_peer = None
        
        # Clear users list
        self.users_list.clear()
    
    def on_ws_error(self, error):
        """Handle WebSocket error signal"""
        self.status_bar.showMessage(f"WebSocket error: {error}")
    
    def on_user_registered(self, success, message):
        """Handle user registered signal"""
        if success:
            self.status_bar.showMessage(f"Registered: {message}")
        else:
            self.status_bar.showMessage(f"Registration failed: {message}")
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
        """Handle connection request from peer"""
        from PyQt5.QtWidgets import QMessageBox
        
        # Show confirmation dialog
        msg_box = QMessageBox()
        msg_box.setWindowTitle("Connection Request")
        msg_box.setText(f"User '{username}' wants to connect to you.")
        msg_box.setInformativeText("Do you want to accept?")
        msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg_box.setDefaultButton(QMessageBox.Yes)
        
        # Get user decision
        if msg_box.exec_() == QMessageBox.Yes:
            # Accept connection
            self.ws_handler.accept_connection(username)
            
            # Set as current peer
            self.current_peer = username
            
            # Update UI
            self.connect_peer_button.setEnabled(False)
            self.disconnect_peer_button.setEnabled(True)
            self.start_sharing_button.setEnabled(True)
            self.stop_sharing_button.setEnabled(False)
            self.status_bar.showMessage(f"Connected to {username}")
            
            # Add to chat
            timestamp = time.strftime("%H:%M:%S")
            self.chat_display.append(f'<div style="text-align: center; margin: 10px;"><span style="background-color: #e6ffe6; padding: 5px; border-radius: 10px; color: #006600;">Connected to {username} at {timestamp}</span></div>')
        else:
            # Reject connection
            reason = "Request declined by user"
            self.ws_handler.reject_connection(username, reason)
    
    def on_peer_connected(self, username):
        """Handle successful connection to peer"""
        # Set as current peer
        self.current_peer = username
        
        # Update UI
        self.connect_peer_button.setEnabled(False)
        self.disconnect_peer_button.setEnabled(True)
        self.start_sharing_button.setEnabled(True)
        self.stop_sharing_button.setEnabled(False)
        self.status_bar.showMessage(f"Connected to {username}")
        
        # Add to chat
        timestamp = time.strftime("%H:%M:%S")
        self.chat_display.append(f'<div style="text-align: center; margin: 10px;"><span style="background-color: #e6ffe6; padding: 5px; border-radius: 10px; color: #006600;">Connected to {username} at {timestamp}</span></div>')
    
    def on_peer_disconnected(self, username, reason):
        """Handle peer disconnection"""
        if username == self.current_peer:
            # Clear current peer
            self.current_peer = None
            
            # Update UI
            self.connect_peer_button.setEnabled(True)
            self.disconnect_peer_button.setEnabled(False)
            self.start_sharing_button.setEnabled(False)
            self.stop_sharing_button.setEnabled(False)
            self.screen_label.setText("No screen sharing active")
            self.screen_label.setStyleSheet("background-color: #333; color: white;")
            self.status_bar.showMessage(f"Disconnected from {username}: {reason}")
            
            # Stop sharing if active
            if self.remote_controller and self.remote_controller._is_sharing:
                self.remote_controller.stop_screen_sharing()
            
            # Add to chat
            timestamp = time.strftime("%H:%M:%S")
            self.chat_display.append(f'<div style="text-align: center; margin: 10px;"><span style="background-color: #ffe6e6; padding: 5px; border-radius: 10px; color: #cc0000;">Disconnected from {username} at {timestamp}: {reason}</span></div>')
    
    def on_chat_message_received(self, username, message):
        """Handle received chat message"""
        # Add to chat display with timestamp
        timestamp = time.strftime("%H:%M:%S")
        self.chat_display.append(f'<div style="text-align: left;"><span style="color: #cc6600; font-weight: bold;">{username}</span> <span style="color: #999; font-size: 0.8em;">{timestamp}</span><br/><span style="background-color: #f2f2f2; padding: 5px; border-radius: 10px; display: inline-block;">{message}</span></div>')
        
        # If not in focus, notify somehow
        if not self.isActiveWindow():
            self.setWindowTitle(f"* New message from {username} - Screen Sharing Test Client")
    
    def on_screen_captured(self, image_data):
        """Handle captured screen image"""
        try:
            # Don't process images if we're sharing ourselves (should be filtered in RemoteController)
            if self.remote_controller and self.remote_controller._is_sharing:
                print(f"Ignoring received screen capture while sharing (unexpected)")
                return
                
            if not image_data or len(image_data) < 100:
                print(f"Received invalid or too small image data: {len(image_data) if image_data else 0} bytes")
                return
                
            # Convert bytes to QImage
            img = QImage()
            success = img.loadFromData(image_data)
            
            if not success or img.isNull():
                print(f"Failed to load image from data ({len(image_data)} bytes)")
                return
                
            # Get the size of the label
            label_size = self.screen_label.size()
            
            if img.width() <= 0 or img.height() <= 0 or label_size.width() <= 0 or label_size.height() <= 0:
                print(f"Invalid dimensions: image({img.width()}x{img.height()}), label({label_size.width()}x{label_size.height()})")
                return
                
            # Create pixmap from the image
            pixmap = QPixmap.fromImage(img)
            if pixmap.isNull():
                print("Failed to create pixmap from image")
                return
                
            # Log image dimensions and size (once every 30 frames)
            if hasattr(self, '_frame_counter'):
                self._frame_counter += 1
            else:
                self._frame_counter = 1
                
            if self._frame_counter % 30 == 0:
                print(f"Received frame {self._frame_counter}: {img.width()}x{img.height()} ({len(image_data)/1024:.1f} KB)")
                
            # Scale the pixmap to fit the label while preserving aspect ratio
            scaled_pixmap = pixmap.scaled(
                label_size,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            
            # Set the pixmap to the label
            self.screen_label.setPixmap(scaled_pixmap)
            
            # Ensure the screen label has focus for keyboard events
            if not self.screen_label.hasFocus():
                self.screen_label.setFocus()
            
        except Exception as e:
            print(f"Error displaying screen image: {e}")
            import traceback
            traceback.print_exc()
    
    def on_screen_share_status_changed(self, is_sharing):
        """Handle screen share status changed signal"""
        if is_sharing:
            self.status_bar.showMessage(f"Sharing screen with {self.current_peer}")
            self.start_sharing_button.setEnabled(False)
            self.stop_sharing_button.setEnabled(True)
        else:
            if self.current_peer:
                self.status_bar.showMessage(f"Connected to {self.current_peer}")
            self.start_sharing_button.setEnabled(True)
            self.stop_sharing_button.setEnabled(False)
            self.screen_label.setText("No screen sharing active")
            self.screen_label.setPixmap(QPixmap())
    
    def on_fps_updated(self, fps):
        """Handle FPS updated signal"""
        self.status_bar.showMessage(f"Sharing screen with {self.current_peer} ({fps:.1f} FPS)")
    
    def on_remote_controller_error(self, error):
        """Handle remote controller error signal"""
        self.status_bar.showMessage(f"Error: {error}")
    
    def handle_remote_mouse_event(self, event_type, x, y, button):
        """Handle mouse events on the screen view and send to remote peer"""
        # Only forward events if we're connected to a peer, have a remote controller,
        # and we're NOT the one sharing the screen (we're viewing someone else's screen)
        if not self.remote_controller or not self.current_peer:
            return
            
        if self.remote_controller._is_sharing:
            # We don't want to send input events if we're the one sharing
            print(f"Ignoring mouse event while sharing: {event_type} at ({x},{y})")
            return
            
        # Log the event for debugging
        print(f"Sending mouse event to {self.current_peer}: {event_type} at ({x},{y}) with button {button}")
            
        # Create event data
        event_data = {
            "type": event_type,
            "x": x,
            "y": y,
            "button": button
        }
        
        # Send to WebSocket handler to forward to peer
        if self.ws_handler:
            self.ws_handler.send_input_event(self.current_peer, event_data)
            
    def handle_remote_key_event(self, event_type, key, modifiers):
        """Handle keyboard events on the screen view and send to remote peer"""
        # Only forward events if we're connected to a peer, have a remote controller,
        # and we're NOT the one sharing the screen (we're viewing someone else's screen)
        if not self.remote_controller or not self.current_peer:
            return
            
        if self.remote_controller._is_sharing:
            # We don't want to send input events if we're the one sharing
            print(f"Ignoring keyboard event while sharing: {event_type} key={key}")
            return
            
        # Log the event for debugging
        print(f"Sending keyboard event to {self.current_peer}: {event_type} key={key} modifiers={modifiers}")
            
        # Create event data
        event_data = {
            "type": event_type,
            "key": key,
            "modifiers": modifiers
        }
        
        # Send to WebSocket handler to forward to peer
        if self.ws_handler:
            self.ws_handler.send_input_event(self.current_peer, event_data)
    
    def closeEvent(self, event):
        """Handle window close event"""
        # Clean up
        if self.remote_controller:
            self.remote_controller.stop_screen_sharing()
        
        if self.ws_handler:
            self.ws_handler.stop()
        
        event.accept()

    def _on_message(self, message):
        """Handle received WebSocket messages"""
        try:
            # Binary messages (screen sharing data)
            if isinstance(message, bytes):
                self._handle_binary_message(message)
                return

            # Text messages (control data)
            data = json.loads(message)
            message_type = data.get("type", "")

            # Handle ping message from server to keep connection alive
            if message_type == "ping":
                self.send_message({"type": "pong"})
                return
                
            # Handle other message types
            if message_type == "register_response":
                self._handle_register_response(data)
            elif message_type == "users_list":
                self._handle_users_list(data)
            elif message_type == "connection_request":
                self._handle_connection_request(data)
            elif message_type == "connection_response":
                self._handle_connection_response(data)
            elif message_type == "peer_disconnected":
                self._handle_peer_disconnected(data)
            elif message_type == "chat_message":
                self._handle_chat_message(data)
            elif message_type == "input_event":
                self._handle_input_event(data)
            else:
                print(f"Unknown message type: {message_type}")
        except json.JSONDecodeError:
            print(f"Invalid JSON received")
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Error handling message: {str(e)}")

class ScreenViewLabel(QLabel):
    """Custom QLabel that captures mouse and keyboard events for remote control"""
    
    # Define signals
    mouse_event_signal = pyqtSignal(str, int, int, int)  # type, x, y, button
    key_event_signal = pyqtSignal(str, int, int)  # type, key, modifiers
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Enable mouse tracking to get all mouse move events, even without buttons pressed
        self.setMouseTracking(True)
        # Make sure the label can get keyboard focus and events
        self.setFocusPolicy(Qt.StrongFocus)  
        # Accept focus so it can receive keyboard events
        self.setFocusPolicy(Qt.WheelFocus)  
        # Store last mouse position to avoid sending too many move events
        self._last_mouse_pos = None
        # Set to true when viewing a remote screen
        self._is_viewing_remote = False
        
    def setPixmap(self, pixmap):
        """Override setPixmap to track when we're viewing a remote screen"""
        super().setPixmap(pixmap)
        # When we have a pixmap, we're viewing a remote screen
        self._is_viewing_remote = not pixmap.isNull() if pixmap else False
        # When we start viewing, grab focus
        if self._is_viewing_remote:
            self.setFocus()
            print("Remote view active - focus grabbed for keyboard input")
        
    def mouseDoubleClickEvent(self, event):
        """Handle double-click to grab focus"""
        self.setFocus()
        if self.pixmap() is not None:
            super().mouseDoubleClickEvent(event)
        
    def focusInEvent(self, event):
        """Called when the widget gets keyboard focus"""
        super().focusInEvent(event)
        if self.pixmap() is not None:
            # Set a visual indicator that we have focus (border)
            self.setStyleSheet("border: 2px solid #3498db; background-color: #333; color: white;")
            print("Screen view has focus - keyboard input will be sent")
        
    def focusOutEvent(self, event):
        """Called when the widget loses keyboard focus"""
        super().focusOutEvent(event)
        # Remove focus indicator
        self.setStyleSheet("border: none; background-color: #333; color: white;")
        
    def mouseMoveEvent(self, event):
        """Capture mouse movement events"""
        if self.pixmap() is not None:  # Only if we're viewing an image
            # Calculate position relative to image
            pos = self._map_to_image_coords(event.pos())
            if pos is None:
                return
                
            # Don't send events too frequently for mouse movement
            if self._last_mouse_pos is None or (pos - self._last_mouse_pos).manhattanLength() > 5:
                self.mouse_event_signal.emit("move", pos.x(), pos.y(), 0)
                self._last_mouse_pos = pos
                
        super().mouseMoveEvent(event)
        
    def mousePressEvent(self, event):
        """Capture mouse button press events"""
        # Ensure we have focus when clicked
        self.setFocus()
        
        if self.pixmap() is not None:
            pos = self._map_to_image_coords(event.pos())
            if pos is not None:
                button = self._map_qt_button_to_int(event.button())
                self.mouse_event_signal.emit("down", pos.x(), pos.y(), button)
                print(f"Mouse down: pos=({pos.x()}, {pos.y()}), button={button}")
        super().mousePressEvent(event)
        
    def mouseReleaseEvent(self, event):
        """Capture mouse button release events"""
        if self.pixmap() is not None:
            pos = self._map_to_image_coords(event.pos())
            if pos is not None:
                button = self._map_qt_button_to_int(event.button())
                self.mouse_event_signal.emit("up", pos.x(), pos.y(), button)
                print(f"Mouse up: pos=({pos.x()}, {pos.y()}), button={button}")
        super().mouseReleaseEvent(event)
        
    def keyPressEvent(self, event):
        """Capture keyboard press events"""
        if self.pixmap() is not None:
            key = event.key()
            modifiers = event.modifiers()
            self.key_event_signal.emit("down", key, int(modifiers))
            print(f"Key down: key={key}, modifiers={int(modifiers)}")
        super().keyPressEvent(event)
        
    def keyReleaseEvent(self, event):
        """Capture keyboard release events"""
        if self.pixmap() is not None:
            key = event.key()
            modifiers = event.modifiers()
            self.key_event_signal.emit("up", key, int(modifiers))
            print(f"Key up: key={key}, modifiers={int(modifiers)}")
        super().keyReleaseEvent(event)
        
    def _map_to_image_coords(self, pos):
        """Convert widget coordinates to image coordinates"""
        if self.pixmap() is None:
            return None
            
        try:
            # Get the rectangle where the image is drawn
            pixmap_rect = self._get_pixmap_rect()
            
            if not pixmap_rect.contains(pos):
                # If outside image bounds, clip to the image
                pos.setX(max(pixmap_rect.left(), min(pos.x(), pixmap_rect.right())))
                pos.setY(max(pixmap_rect.top(), min(pos.y(), pixmap_rect.bottom())))
                
            # Calculate relative position within the image rectangle
            if pixmap_rect.width() <= 0 or pixmap_rect.height() <= 0:
                return None
                
            rel_x = (pos.x() - pixmap_rect.left()) / pixmap_rect.width()
            rel_y = (pos.y() - pixmap_rect.top()) / pixmap_rect.height()
            
            # Scale to actual image dimensions
            img_x = int(rel_x * self.pixmap().width())
            img_y = int(rel_y * self.pixmap().height())
            
            return QPoint(img_x, img_y)
        except Exception as e:
            print(f"Error mapping coordinates: {e}")
            import traceback
            traceback.print_exc()
            return None
        
    def _get_pixmap_rect(self):
        """Get the rectangle where the pixmap is drawn in the label"""
        if not self.pixmap():
            return QRect()
            
        try:
            # Scale pixmap to fit label while preserving aspect ratio
            label_size = self.size()
            pixmap_size = self.pixmap().size()
            
            if pixmap_size.width() <= 0 or pixmap_size.height() <= 0 or label_size.width() <= 0 or label_size.height() <= 0:
                return QRect()
                
            # Calculate the scaled size
            scale_w = label_size.width() / pixmap_size.width()
            scale_h = label_size.height() / pixmap_size.height()
            scale = min(scale_w, scale_h)
            
            # Calculate the scaled dimensions
            scaled_width = int(pixmap_size.width() * scale)
            scaled_height = int(pixmap_size.height() * scale)
            
            # Calculate the position to center the pixmap
            x = (label_size.width() - scaled_width) // 2
            y = (label_size.height() - scaled_height) // 2
            
            return QRect(x, y, scaled_width, scaled_height)
        except Exception as e:
            print(f"Error calculating pixmap rect: {e}")
            import traceback
            traceback.print_exc()
            return QRect()
        
    def _map_qt_button_to_int(self, button):
        """Map Qt mouse button to simple integer (1=left, 2=right, 3=middle)"""
        if button == Qt.LeftButton:
            return 1
        elif button == Qt.RightButton:
            return 2
        elif button == Qt.MiddleButton:
            return 3
        else:
            return 0

def main():
    app = QApplication(sys.argv)
    window = TestClient()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main() 