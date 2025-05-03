import sys
import os
import time
import json
import logging
import asyncio
import websockets
import threading
import base64
import cv2
import numpy as np
import traceback
import httpx
from PyQt5.QtWidgets import QApplication, QMessageBox, QVBoxLayout, QFormLayout
from PyQt5.QtCore import QTimer, Qt, QThread, pyqtSignal, pyqtSlot, QObject
from PyQt5.QtGui import QImage, QPixmap, QKeyEvent, QMouseEvent, QWheelEvent, QPaintEvent
import ui
from remote_controller import RemoteController
from constants import (
    DEFAULT_BACKEND_URL, DEFAULT_WS_URL, MAX_RECONNECT_ATTEMPTS, RECONNECT_DELAY_MS,
    DEFAULT_STREAM_QUALITY, DEFAULT_STREAM_SCALE, DEFAULT_STREAM_FPS, DEFAULT_MONITOR_INDEX,
    DEFAULT_THEME, AVAILABLE_THEMES, INITIAL_STATUS, CONNECTION_STATUS,
    WS_MESSAGE_TYPES, STYLES_DIR, ICONS_DIR, LOG_FILE,
    LOG_FORMAT, LOG_DATE_FORMAT, LOG_LEVEL
)

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format=LOG_FORMAT,
    datefmt=LOG_DATE_FORMAT
)

# Import local modules
import utils
import ui
# Removed unused server/client imports
from websocket_handler import WebSocketHandler # Import WebSocketHandler

# --- Function to load stylesheet ---
def load_stylesheet(theme_name="dark"):
    """Loads and returns the content of a QSS file based on theme name."""
    base_filename = "light_styles.qss" if theme_name == "light" else "styles.qss"
    filename = f"styles/{base_filename}" # Prepend the directory
    logging.debug(f"[DEBUG] Attempting to load stylesheet: {filename}")
    try:
        with open(filename, "r") as f:
            return f.read()
    except FileNotFoundError:
        logging.warning(f"Stylesheet file '{filename}' not found.")
        return "" # Return empty string if file not found
    except Exception as e:
        logging.error(f"Failed to load stylesheet '{filename}': {e}")
        return ""

class AppController(QObject):
    # Signal to request showing the permission dialog in the GUI thread
    request_permission_signal = pyqtSignal(str, object) # controller_uid, pending_event
    # Signal for FPS updates from viewing
    fps_updated_signal = pyqtSignal(float) # Emits calculated FPS
    # Add signals related to view request
    request_view_permission_signal = pyqtSignal(str) # Ask user if peer can view

    RECONNECT_DELAY_MS = RECONNECT_DELAY_MS
    MAX_RECONNECT_ATTEMPTS = MAX_RECONNECT_ATTEMPTS

    def __init__(self):
        super().__init__()  # Initialize QObject
        self.app = QApplication(sys.argv)
        self.current_theme = DEFAULT_THEME
        self._apply_theme()
        
        self.login_window = None
        self.registration_window = None
        self.main_window = None
        self.websocket_handler = None
        self.jwt_token = None
        self.backend_base_url = None
        self.username = None
        self.current_peer_uid = None
        self.control_permissions = {}
        
        self._is_sharing_screen = False
        self.remote_controller = None
        
        # Stream settings with defaults from constants
        self._stream_quality = DEFAULT_STREAM_QUALITY
        self._stream_scale_factor = DEFAULT_STREAM_SCALE / 100.0
        self._stream_fps = DEFAULT_STREAM_FPS
        self._stream_monitor_index = DEFAULT_MONITOR_INDEX
        
        # FPS calculation
        self._received_frame_counter = 0
        self._fps_calc_start_time = time.perf_counter()
        self._last_status_message = INITIAL_STATUS
        
        # Reconnection settings
        self._reconnect_attempts = 0
        self._reconnect_timer = QTimer()
        self._reconnect_timer.timeout.connect(self._attempt_reconnect)
        
        # Track pending permission requests
        self._permission_requests_pending = set()

        # Connect signals that are always relevant
        self.request_permission_signal.connect(self.show_permission_dialog_slot)
        self.fps_updated_signal.connect(self._handle_fps_update_to_ui)
        self.request_view_permission_signal.connect(self._ask_view_permission_slot)

        # Start with login window
        self.show_login_window()

    def _apply_theme(self):
        """Loads and applies the stylesheet for the current theme."""
        stylesheet = load_stylesheet(self.current_theme)
        if stylesheet:
            self.app.setStyleSheet(stylesheet)
            logging.debug(f"Applied {self.current_theme} theme stylesheet.")
        else:
            self.app.setStyleSheet("") # Clear stylesheet if loading fails
            logging.warning(f"Failed to load {self.current_theme} stylesheet, cleared styles.")

        # Update UI elements that need explicit theme changes
        try:
            if self.login_window:
                self.login_window._update_theme_icon(self.current_theme)
            if self.main_window:
                self.main_window._update_theme_icon(self.current_theme)
        except AttributeError:
            pass  # Ignore if windows haven't been created yet

    @pyqtSlot()
    def toggle_theme(self):
        """Switches between light and dark themes and reapplies styles."""
        logging.debug("Toggling theme...")
        self.current_theme = "light" if self.current_theme == "dark" else "dark"
        self._apply_theme() # Reload and apply the new stylesheet

    def show_login_window(self):
        """Displays the login window."""
        if self.login_window is None:
            self.login_window = ui.LoginWindow()
            self.login_window.login_attempt_signal.connect(self.handle_login_attempt)
            self.login_window.toggle_theme_signal.connect(self.toggle_theme)
            self.login_window.register_signal.connect(lambda _: self.show_registration_window())
            # Load remembered credentials if available
            self._load_remembered_credentials()
        else:
            # Reset login button state if window already exists
            self.login_window.login_button.setEnabled(True)
            self.login_window.login_button.setText("Login")
            self.login_window.register_button.setEnabled(True)
            self.login_window.error_label.hide()
            # Also reload remembered credentials if window is reused
            self._load_remembered_credentials()
        self.login_window._update_theme_icon(self.current_theme)
        self.login_window.show()

    def _load_remembered_credentials(self):
        """Load credentials from credentials.json and pre-fill the login form if Remember Me was checked."""
        import os, json
        cred_path = os.path.join(os.path.dirname(__file__), 'credentials.json')
        if os.path.exists(cred_path):
            try:
                with open(cred_path, 'r') as f:
                    data = json.load(f)
                username = data.get('username', '')
                password = data.get('password', '')
                remember = data.get('remember', False)
                if remember and username and password:
                    self.login_window.set_remembered_credentials(username, password)
                else:
                    self.login_window.clear_remembered_credentials()
            except Exception as e:
                logging.warning(f"Failed to load credentials: {e}")
                self.login_window.clear_remembered_credentials()
        else:
            self.login_window.clear_remembered_credentials()

    def _save_remembered_credentials(self, username, password, remember):
        """Save or clear credentials in credentials.json based on Remember Me state."""
        import os, json
        cred_path = os.path.join(os.path.dirname(__file__), 'credentials.json')
        if remember and username and password:
            data = {"username": username, "password": password, "remember": True}
            try:
                with open(cred_path, 'w') as f:
                    json.dump(data, f)
            except Exception as e:
                logging.warning(f"Failed to save credentials: {e}")
        else:
            # Remove credentials file if exists
            try:
                if os.path.exists(cred_path):
                    os.remove(cred_path)
            except Exception as e:
                logging.warning(f"Failed to remove credentials: {e}")

    def show_registration_window(self):
        """Shows the registration window."""
        if self.registration_window is None:
            self.registration_window = ui.RegistrationWindow(self.current_theme)
            self.registration_window.register_attempt_signal.connect(self.handle_registration_attempt)
            self.registration_window.toggle_theme_signal.connect(self.toggle_theme)
        self.registration_window._update_theme_icon(self.current_theme)
        self.registration_window.show()

    @pyqtSlot(str, str, str)
    def handle_registration_attempt(self, username, password, confirm_password):
        """Handles the registration attempt signal from RegistrationWindow."""
        logging.info(f"Attempting registration for user {username}")
        self.registration_window.set_registering()

        try:
            # --- TODO (Backend): Implement Actual HTTP Registration ---
            # 1. Define the exact endpoint (e.g., /api/register).
            # 2. Define the HTTP method (POST).
            # 3. Define the request body format (e.g., JSON: {"username": "user", "password": "pass"}).
            # 4. Define the expected success response format.
            # 5. Define the expected failure response format.
            # 6. Replace the simulation block below with an actual `httpx` call.
            # -----------------------------------------------------

            # <<<<< START: SIMULATED REGISTRATION - REPLACE WITH ACTUAL API CALL >>>>>
            import time
            time.sleep(1) # Simulate network delay
            logging.info("Registration successful (Simulated)!")
            
            # Show success message and close registration window
            QMessageBox.information(self.registration_window, "Registration Successful", 
                                  "Account created successfully. You can now login.")
            self.registration_window.close()
            self.registration_window = None
            
            # Update login window with the new username
            if self.login_window:
                self.login_window.username_input.setText(username)
                self.login_window.password_input.clear()
                self.login_window.username_input.setFocus()
            # <<<<< END: SIMULATED REGISTRATION - REPLACE WITH ACTUAL API CALL >>>>>

        except Exception as e:
            error_msg = f"An unexpected error occurred during registration: {e}"
            logging.exception(error_msg)
            self.registration_window.show_error(error_msg)

    @pyqtSlot(str, str, str)
    def handle_login_attempt(self, backend_url, username, password):
        """Handles the login attempt signal from LoginWindow."""
        logging.info(f"Attempting login to {backend_url} for user {username}")
        self.backend_base_url = backend_url
        self.login_window.set_logging_in()

        # Save or clear credentials based on Remember Me state
        remember = self.login_window.remember_checkbox.isChecked()
        self._save_remembered_credentials(username, password, remember)

        try:
            # --- TEMPORARY BYPASS: Auto-login for testing ---
            # This will be replaced with actual authentication when backend is ready
            self.jwt_token = "test_token" # Temporary token for testing
            self.username = username
            logging.info("Login successful (Temporary Bypass)!")
            
            # Close and clean up login window
            if self.login_window:
                self.login_window.close()
                self.login_window = None
            
            # Initialize WebSocket connection
            self._initialize_websocket()
            
            # Show main window
            self.show_main_window()
            # --- END TEMPORARY BYPASS ---

        except Exception as e:
            error_msg = f"An unexpected error occurred during login: {e}"
            logging.exception(error_msg)
            self.login_window.show_error(error_msg)

    def on_login_success(self):
        """Called after successful login and JWT token is obtained."""
        if self.login_window:
            self.login_window.close()
        self.login_window = None

        logging.info(f"Proceeding to main app for user {self.username} with token: {self.jwt_token}")
        self.show_main_window()
        self.init_websocket() # Initialize WebSocket AFTER showing main window

    def show_main_window(self):
        """Creates and shows the main application window."""
        if self.main_window is None:
            logging.debug("Creating MainWindow...")
            self.main_window = ui.MainWindow(self.username, self.current_theme)

            # --- Connect signals FROM MainWindow UI Actions TO Controller Logic ---
            logging.debug("Connecting MainWindow signals...")
            self.main_window.request_view_signal.connect(self.handle_request_view)
            self.main_window.disconnect_signal.connect(self.handle_disconnect)
            self.main_window.send_chat_message_signal.connect(self.handle_send_chat)
            self.main_window.logout_signal.connect(self.handle_logout)
            self.main_window.toggle_theme_signal.connect(self.toggle_theme)
            self.main_window.start_sharing_signal.connect(self.start_screen_sharing)
            self.main_window.stop_sharing_signal.connect(self.stop_screen_sharing)
            self.main_window.mouse_permission_signal.connect(self.handle_mouse_permission_change)

            # Connect Stream Settings Signals (UI -> Controller)
            self.main_window.quality_changed_signal.connect(self._handle_quality_changed)
            self.main_window.scale_changed_signal.connect(self._handle_scale_changed)
            self.main_window.fps_changed_signal.connect(self._handle_fps_changed)
            self.main_window.monitor_changed_signal.connect(self._handle_monitor_changed)

            # Connect screen input signals (UI -> Controller)
            if hasattr(self.main_window, "screen_display_widget") and self.main_window.screen_display_widget:
                self.main_window.screen_display_widget.mouse_event_signal.connect(self.handle_send_input_event)
                self.main_window.screen_display_widget.key_event_signal.connect(self.handle_send_input_event)
                logging.debug("Screen display widget signals connected.")
            else:
                 logging.warning("screen_display_widget not found on main_window during signal connection.")

            logging.debug("MainWindow signals connected.")
            self.main_window.show()
            logging.debug("MainWindow shown.")

        # Ensure screen display starts in view-only mode
        if (
            hasattr(self.main_window, "screen_display_widget")
            and self.main_window.screen_display_widget
        ):
            logging.debug("Setting screen display widget to view-only mode initially.")
            self.main_window.screen_display_widget.set_view_only(True)


    def _initialize_websocket(self):
        """Initializes the WebSocket connection with the backend."""
        if self.websocket_handler is not None:
            self.websocket_handler.close()
            self.websocket_handler = None

        try:
            # Create WebSocket handler
            self.websocket_handler = WebSocketHandler(self.backend_base_url, self.username)
            
            # Connect signals FROM WebSocketHandler TO Controller Logic
            self.websocket_handler.connected_signal.connect(self.on_websocket_connected)
            self.websocket_handler.disconnected_signal.connect(self.on_websocket_disconnected)
            self.websocket_handler.error_signal.connect(self.on_websocket_error)
            # Specific message type signals (Backend needs to send these types)
            self.websocket_handler.user_registered_signal.connect(self._on_user_registered)
            self.websocket_handler.users_list_updated_signal.connect(self._on_users_list_updated)
            self.websocket_handler.peer_connection_requested_signal.connect(self._on_peer_connection_requested)
            self.websocket_handler.peer_connected_signal.connect(self._on_peer_connected)
            self.websocket_handler.peer_disconnected_signal.connect(self._on_peer_disconnected)
            self.websocket_handler.chat_message_received_signal.connect(self._on_chat_message_received)
            # Generic message handler for other JSON types
            self.websocket_handler.message_received_signal.connect(self.handle_websocket_message)
            # Binary message handler (screen frames + cursor)
            self.websocket_handler.binary_message_received_signal.connect(self.handle_websocket_binary_message)

            # Initialize RemoteController *after* websocket_handler is created
            if not self.remote_controller:
                self.remote_controller = RemoteController(self.websocket_handler)
                # Connect RemoteController signals TO Controller/UI
                self.remote_controller.screen_captured_signal.connect(self._on_screen_captured)
                self.remote_controller.screen_share_status_signal.connect(self._on_screen_share_status_changed)
                self.remote_controller.error_signal.connect(self._on_remote_controller_error)

            # Attempt WebSocket connection
            self.websocket_handler.connect_ws()

        except Exception as e:
            error_msg = f"Failed to initialize WebSocket connection: {e}"
            logging.exception(error_msg)
            self.login_window.show_error(error_msg)
            self.jwt_token = None
            self.username = None

    def init_websocket(self):
        """Initializes and attempts to connect the WebSocket handler."""
        if not self.backend_base_url:
            logging.error("Cannot initialize WebSocket: Missing Backend URL.")
            # TODO (Client): Show user-facing error if main_window exists?
            return

        if self.websocket_handler and self.websocket_handler.is_connected:
            logging.info("WebSocket already connected.")
            if self._reconnect_timer.isActive():
                logging.info("Stopping reconnect timer as connection established.")
                self._reconnect_timer.stop()
            self._reconnect_attempts = 0 # Reset attempts on successful manual init
            return

        logging.info(f"Initializing WebSocket Handler (Attempt: {self._reconnect_attempts + 1})...")
        if self._reconnect_attempts == 0 and self._reconnect_timer.isActive():
            self._reconnect_timer.stop()

        # --- Create websocket handler ---
        # TODO (Backend): Decide if JWT token needs to be passed/used by WS connection/messages.
        # If so, the WebSocketHandler init AND backend need modification.
        # Currently, WS connection is unauthenticated beyond the initial user registration message.
        self.websocket_handler = WebSocketHandler(self.backend_base_url, self.username)

        # --- Connect signals FROM WebSocketHandler TO Controller Logic ---
        self.websocket_handler.connected_signal.connect(self.on_websocket_connected)
        self.websocket_handler.disconnected_signal.connect(self.on_websocket_disconnected)
        self.websocket_handler.error_signal.connect(self.on_websocket_error)
        # Specific message type signals (Backend needs to send these types)
        self.websocket_handler.user_registered_signal.connect(self._on_user_registered)
        self.websocket_handler.users_list_updated_signal.connect(self._on_users_list_updated)
        self.websocket_handler.peer_connection_requested_signal.connect(self._on_peer_connection_requested)
        self.websocket_handler.peer_connected_signal.connect(self._on_peer_connected)
        self.websocket_handler.peer_disconnected_signal.connect(self._on_peer_disconnected)
        self.websocket_handler.chat_message_received_signal.connect(self._on_chat_message_received)
        # Generic message handler for other JSON types (e.g., permission updates, view responses, errors)
        self.websocket_handler.message_received_signal.connect(self.handle_websocket_message)
        # Binary message handler (screen frames + cursor)
        self.websocket_handler.binary_message_received_signal.connect(self.handle_websocket_binary_message)

        # Initialize RemoteController *after* websocket_handler is created
        # RemoteController handles screen capture (when sharing) and input simulation (when sharing + permission)
        if not self.remote_controller:
             self.remote_controller = RemoteController(self.websocket_handler)
             # Connect RemoteController signals TO Controller/UI
             self.remote_controller.screen_captured_signal.connect(self._on_screen_captured)
             self.remote_controller.screen_share_status_signal.connect(self._on_screen_share_status_changed)
             self.remote_controller.error_signal.connect(self._on_remote_controller_error)
             # Use the direct FPS signal from RemoteController for *sending* FPS info (if needed)
             # self.remote_controller.fps_updated_signal.connect(...) # Connect if needed

        # Attempt WebSocket connection
        # TODO (Backend): Ensure a WebSocket server is running at the derived ws_url (e.g., ws://127.0.0.1:8000/ws)
        self.websocket_handler.connect_ws()

    # --- WebSocket Signal Handlers (Events coming FROM WebSocketHandler) ---
    @pyqtSlot()
    def on_websocket_connected(self):
        """Called when WebSocket connection is established and handler sends `connected_signal`."""
        logging.info("WebSocket connected successfully!")
        if self._reconnect_timer.isActive():
            logging.info("Stopping reconnect timer as connection established.")
            self._reconnect_timer.stop()
        self._reconnect_attempts = 0

        if self.main_window:
             # Update status bar
             self.main_window.show_status_message("WebSocket Connected. Ready.")
             # TODO (Backend): Upon successful WS connection and user registration,
             # the backend should ideally send the current list of online users.
             # self.websocket_handler.request_user_list() # Or similar if client needs to ask

    @pyqtSlot(str)
    def on_websocket_disconnected(self, reason):
        """Called when WebSocket connection is lost and handler sends `disconnected_signal`."""
        logging.info(f"WebSocket disconnected: {reason}")

        # Clean up peer connection state if WS disconnects
        if self.current_peer_uid:
             self.handle_disconnect(inform_peer=False) # Disconnect locally without sending msg

        # Attempt auto-reconnect
        if (not self._reconnect_timer.isActive() and
            self._reconnect_attempts < self.MAX_RECONNECT_ATTEMPTS):
            logging.info(f"Starting reconnect timer. Attempt {self._reconnect_attempts + 1}/{self.MAX_RECONNECT_ATTEMPTS}")
            self._reconnect_timer.start(self.RECONNECT_DELAY_MS)
            if self.main_window:
                self.main_window.show_status_message(f"WebSocket Disconnected: {reason}. Retrying...")
        else:
            # Max attempts reached or timer already active
             if self.main_window:
                self.main_window.show_status_message("WebSocket Disconnected. Reconnection failed.")
                # Ensure main window shows fully disconnected state
                self.main_window.set_disconnected_state("WebSocket Connection Failed")


    @pyqtSlot(str)
    def on_websocket_error(self, error_message):
        """Called when a WebSocket error occurs and handler sends `error_signal`."""
        logging.error(f"WebSocket error: {error_message}")
        if self.main_window:
             self.main_window.show_status_message(f"WebSocket Error: {error_message}")
             # TODO (Client/Backend): Decide if UI should enter disconnected state on certain errors.

    @pyqtSlot(dict)
    def handle_websocket_message(self, message):
        """Handle incoming generic JSON WebSocket messages via `message_received_signal`."""
        # This handles messages NOT covered by specific signals from WebSocketHandler
        # (e.g., permission updates, view responses, backend errors).
        try:
            message_type = message.get("type")
            sender_uid = message.get("sender_uid") # Expected sender from backend/peer
            logging.debug(f"Received generic WS message: Type={message_type}, Sender={sender_uid}")

            # --- Handle Input Permission Updates (Peer telling us if we can control them) ---
            if message_type == "input_permission_update":
                allowed = message.get("allowed", False)
                if sender_uid and sender_uid == self.current_peer_uid:
                    logging.debug(f"Received input permission update from {sender_uid}: {allowed}")
                    # NOTE: We are VIEWING here. `allowed` means WE are allowed to control the PEER.
                    # We update our ScreenDisplayWidget view_only state.
                    if self.main_window and self.main_window.screen_display_widget:
                         # If allowed=True, view_only=False (we can send input).
                         # If allowed=False, view_only=True (we cannot send input).
                         self.main_window.screen_display_widget.set_view_only(not allowed)
                         # Also update the status bar display
                         self.main_window.update_control_status_display()
                         logging.debug(f"Set screen display view_only to: {not allowed}")
                else:
                    logging.warning(f"Received input_permission_update from unexpected sender {sender_uid} or no peer connected.")

            # --- Handle View Responses (Peer responding to our view request) ---
            elif message_type == "view_response":
                allowed = message.get("allowed", False)
                response_sender = message.get("sender_uid") # The user who allowed/denied
                target_requester = message.get("target_uid") # Should be self.username

                if target_requester != self.username:
                     logging.warning(f"Received view_response intended for {target_requester}")
                     return # Ignore responses not meant for us

                # Re-enable the request button now that we have a response
                if self.main_window:
                    self.main_window.request_view_button.setEnabled(True)

                if allowed and response_sender:
                    # Successfully connected FOR VIEWING
                    logging.debug(f"View request accepted by {response_sender}")
                    self.current_peer_uid = response_sender
                    self.control_permissions.clear() # Clear old permissions
                    if self.main_window:
                        self.main_window.set_connected_state(response_sender)
                        # Role will be set to VIEWING when first frame is received (handle_websocket_binary_message)
                        self.main_window.set_role(ui.MainWindow.ROLE_IDLE) # Start as idle until frame arrives
                        # Start viewing - enable screen widget input based on initial permission
                        if self.main_window.screen_display_widget:
                             # Assume view-only initially, permission update will follow if granted by peer
                             self.main_window.screen_display_widget.set_view_only(True)
                             self.main_window.update_control_status_display()
                    self._reset_fps_counter() # Reset FPS counter for new view
                else:
                    # View request was denied by the peer
                    denial_message = message.get("message", f"User '{response_sender}' denied your view request.")
                    logging.debug(f"View request denied by {response_sender}")
                    if self.main_window:
                        self.main_window.set_disconnected_state(denial_message) # Show reason in status
                        QMessageBox.information(self.main_window,"View Request Denied", denial_message)

            # --- Handle generic error messages from Backend ---
            elif message_type == "error":
                error_message = message.get("message", "Unknown error from peer/server")
                logging.error(f"Received error message from backend/peer: {error_message}")
                if self.main_window:
                    self.main_window.show_status_message(f"Error: {error_message}")
                    QMessageBox.warning(self.main_window, "Error", error_message)
                    # TODO (Client): Should we disconnect on certain backend errors?

            # --- Handle potential Stream Settings Update from Peer (if needed) ---
            # TODO (Backend): Decide if stream settings (quality, fps etc.) need to be relayed
            # between peers or if they only affect the sender's capture.
            # If relayed, handle message type e.g., "stream_settings_peer_update"
            # elif message_type == "stream_settings_peer_update":
            #     settings = message.get("settings")
            #     print(f"[DEBUG] Received peer stream settings update: {settings}")
            #     # Update UI display elements if needed (e.g., status bar)

            else:
                logging.warning(f"Unhandled generic message type: {message_type}")

        except Exception as e:
            logging.exception(f"Error handling generic WebSocket message: {e}")
            traceback.print_exc()

    @pyqtSlot(bytes)
    def handle_websocket_binary_message(self, data_bytes):
        """Handles BINARY messages (screen frames + cursor) received via `binary_message_received_signal`."""
        # TODO (Backend): Backend relays input events from controller peer to sharer peer.
        # This method is called when such a relayed event is received.
        # Note: Backend should have already checked permission before relaying.
        if not data_bytes or len(data_bytes) <= 8: # Expect image data + 4 bytes X + 4 bytes Y
            logging.warning("Received empty or too short binary message.")
            return

        # Check if the main window and display widget are ready
        if not (
            self.main_window
            and hasattr(self.main_window, "screen_display_widget")
            and self.main_window.screen_display_widget
        ):
            logging.warning("MainWindow not ready to display received binary frame.")
            return

        # If we are receiving frames, our role is VIEWING
        if self.main_window._current_role != ui.MainWindow.ROLE_VIEWING:
            logging.debug("Received first frame, setting role to VIEWING")
            self.main_window.set_viewing_state(True) # Update UI state
            # Control status display is updated within set_viewing_state

        # --- Increment frame counter for FPS calculation ---
        self._received_frame_counter += 1

        try:
            # Separate image data and cursor data (Assumes format: JPEG + 4 bytes X + 4 bytes Y)
            # TODO (Client/Backend): Ensure this data packing format is consistent.
            image_data = data_bytes[:-8]
            cursor_x = int.from_bytes(data_bytes[-8:-4], "big", signed=False)
            cursor_y = int.from_bytes(data_bytes[-4:], "big", signed=False)

            # Update the UI (calls methods in ui.py)
            self.main_window.screen_display_widget.update_screen(image_data)
            self.main_window.screen_display_widget.update_remote_cursor(cursor_x, cursor_y)

        except Exception as e:
            logging.error(f"Error processing received binary frame data: {e}")
            # traceback.print_exc() # Optional detailed trace

        # --- Calculate and emit FPS periodically ---
        current_time = time.perf_counter()
        time_elapsed = current_time - self._fps_calc_start_time
        if time_elapsed >= 1.0: # Calculate every second
            calculated_fps = self._received_frame_counter / time_elapsed
            self.fps_updated_signal.emit(calculated_fps) # Emit signal for UI update
            # Reset counter and timer
            self._received_frame_counter = 0
            self._fps_calc_start_time = current_time


    # --- Specific WebSocket Signal Handlers (from WebSocketHandler - simplified processing) ---
    @pyqtSlot(bool, str)
    def _on_user_registered(self, success, message):
        """Handles `user_registered_signal` after WS sends register message."""
        logging.info(f"User registration response: Success={success}, Message='{message}'")
        if self.main_window:
            self.main_window.show_status_message(message)
        if not success:
             # TODO (Client): What happens if registration fails? Close connection? Show error? Go back to login?
             QMessageBox.critical(self.main_window, "Registration Failed", message)
             # self.handle_logout() # Example: force logout

    @pyqtSlot(list)
    def _on_users_list_updated(self, users):
        """Handles `users_list_updated_signal`."""
        # TODO (Backend): Backend should send `users_list` message (e.g., on user connect/disconnect).
        logging.info(f"Users list updated: {users}")
        # TODO (Client): Implement user list display in MainWindow and update it here.
        # if self.main_window:
        #     self.main_window.update_users_list(users)


    @pyqtSlot(str)
    def _on_peer_connection_requested(self, requesting_username):
        """Handles `peer_connection_requested_signal`. A peer wants to view US."""
        # TODO (Backend): Backend receives `request_connection` from User A to User B,
        # relays it as `connection_request` to User B.
        logging.info(f"Connection request received from: {requesting_username}")
        # Ask user for permission (using signal to ensure it runs in UI thread)
        self.request_view_permission_signal.emit(requesting_username)


    @pyqtSlot(str)
    def _on_peer_connected(self, username):
        """Handles `peer_connected_signal`. WebSocketHandler confirms connection."""
        # TODO (Backend): This signal is triggered by WebSocketHandler upon receiving
        # an *accepted* `connection_response` message from the backend.
        logging.info(f"Controller notified: Connected to peer: {username}")
        # This might be redundant if view_response/acceptance handlers update UI,
        # but serves as confirmation.
        if not self.current_peer_uid: # Only update if not already set
             self.current_peer_uid = username
             if self.main_window:
                 self.main_window.set_connected_state(username)
                 # Role will be set based on whether we receive frames (viewing) or start sharing.


    @pyqtSlot(str, str)
    def _on_peer_disconnected(self, username, reason):
        """Handles `peer_disconnected_signal`. Peer connection ended."""
        # TODO (Backend): Backend sends `peer_disconnected` message when:
        # 1. A user sends `disconnect_peer`.
        # 2. A user's WebSocket disconnects abruptly while peered.
        # 3. A connection request is rejected (handled slightly differently by client logic).
        logging.info(f"Controller notified: Disconnected from peer: {username}, Reason: {reason}")
        if self.current_peer_uid == username:
            # Call local disconnect handler to clean up state and UI
            self.handle_disconnect(inform_peer=False) # Clean up local state only
            if self.main_window:
                 self.main_window.show_status_message(f"Peer {username} disconnected: {reason}")
        else:
            logging.warning(f"Received disconnect for non-current peer {username}")


    @pyqtSlot(str, str)
    def _on_chat_message_received(self, sender_username, message):
        """Handles `chat_message_received_signal`."""
        # TODO (Backend): Backend receives `chat_message` from User A to User B,
        # relays it as `chat_message` from User A to User B.
        logging.info(f"Chat from {sender_username}: {message}")
        if self.main_window and sender_username == self.current_peer_uid:
            # Format message before appending to UI
            formatted_message = f"{sender_username}: {message}"
            self.main_window.append_chat_message(formatted_message)
            # TODO (Client): Add notification/highlight for new messages?
        elif not self.current_peer_uid:
             logging.warning("Chat message received but no peer connected.")
        else:
             logging.warning(f"Chat message received from {sender_username} but connected to {self.current_peer_uid}")
             # TODO (Client): Maybe still show message but indicate it's unexpected?

    # --- MainWindow Signal Handlers (Actions originating FROM UI) ---

    @pyqtSlot(str)
    def handle_request_view(self, target_uid):
        """Handles the 'Connect' button click from MainWindow to request viewing a peer."""
        # This action triggers a request TO the backend.
        logging.debug(f"UI requested to view UID: {target_uid}")

        if not target_uid or target_uid.strip() == "" or target_uid == self.username:
            QMessageBox.warning(self.main_window,"Error","Please enter a valid Peer UID to connect to (cannot connect to self).")
            if self.main_window:
                # Reset UI state if validation fails
                self.main_window.set_peer_connection_status(ui.MainWindow.PEER_STATUS_DISCONNECTED)
                self.main_window.request_view_button.setEnabled(True)
            return

        # Ensure WebSocket is ready before sending
        if self.websocket_handler and self.websocket_handler.is_connected:
            # TODO (Backend): Backend needs to handle the `request_view` message type.
            # It should look up the target_uid, find their connection, and forward
            # the request to them (as `connection_request` type).
            message = {
                "type": "request_view", # Client-specific type to initiate request
                "target_uid": target_uid,
                "sender_uid": self.username, # Include sender for backend processing
            }
            # Delegate sending to WebSocketHandler
            success = self.websocket_handler.send_message(message)

            if success and self.main_window:
                # Update UI to show "Connecting..." status while waiting for peer response
                self.main_window.set_peer_connection_status(ui.MainWindow.PEER_STATUS_CONNECTING)
                self.main_window.show_status_message(f"Requesting to view {target_uid}'s screen...")
                self.main_window.request_view_button.setEnabled(False) # Disable button while waiting
                logging.debug(f"Sent view request to {target_uid}, waiting for response")
            elif not success:
                 QMessageBox.warning(self.main_window,"Error","Failed to send view request (WebSocket error).")
                 if self.main_window: # Reset UI state
                      self.main_window.set_peer_connection_status(ui.MainWindow.PEER_STATUS_DISCONNECTED)
                      self.main_window.request_view_button.setEnabled(True)

        else:
            QMessageBox.warning(self.main_window,"Error","WebSocket not connected. Cannot request view.")
            if self.main_window: # Reset UI state
                self.main_window.set_peer_connection_status(ui.MainWindow.PEER_STATUS_DISCONNECTED)
                self.main_window.request_view_button.setEnabled(True)


    @pyqtSlot()
    def handle_disconnect(self, inform_peer=True):
        """Handles disconnection from current peer (UI button click or internal trigger)."""
        if not self.current_peer_uid:
            logging.warning("Disconnect called but not connected to a peer.")
            return

        peer_to_disconnect = self.current_peer_uid
        logging.info(f"Disconnecting from peer: {peer_to_disconnect}")

        try:
            # Stop sharing if *we* are currently sharing
            if self._is_sharing_screen:
                self.stop_screen_sharing(inform_peer=False) # Stop locally first

            # Send disconnect message TO the backend/peer if requested
            if inform_peer and self.websocket_handler and self.websocket_handler.is_connected:
                 # TODO (Backend): Backend needs to handle `disconnect_peer` message.
                 # It should notify the `peer_to_disconnect` (using `peer_disconnected` message)
                 # and break the logical link between the peers.
                 # Use WebSocketHandler method if it exists, otherwise send manually
                 if hasattr(self.websocket_handler, 'disconnect_from_peer'):
                     self.websocket_handler.disconnect_from_peer() # Assumes handler sends correct message
                 else:
                     # Fallback if handler doesn't have specific method
                     self.websocket_handler.send_message({
                         "type": "disconnect_peer", # Or appropriate type backend expects
                         "target_uid": peer_to_disconnect, # Inform the peer (or backend handles based on sender)
                     })

        except Exception as e:
            logging.exception(f"Error during disconnect signalling: {e}")
            traceback.print_exc()
        finally:
             # --- Always clean up local client state regardless of send success ---
             self.current_peer_uid = None
             self.control_permissions = {} # Clear permissions
             self._reset_fps_counter() # Reset viewing FPS counter

             # Update UI to disconnected state
             if self.main_window:
                 self.main_window.set_disconnected_state(f"Disconnected from {peer_to_disconnect}")

    @pyqtSlot(str)
    def handle_send_chat(self, message):
        """Handles sending a chat message from MainWindow UI."""
        # Sends message TO the backend for relaying.
        if not message or not message.strip():
            return

        if self.current_peer_uid and self.websocket_handler and self.websocket_handler.is_connected:
             logging.info(f"Sending chat to {self.current_peer_uid}: {message}")
             # TODO (Backend): Backend needs to handle `chat_message`.
             # It should find the `current_peer_uid`'s connection and forward the message
             # (as `chat_message` type, ensuring `from_user` is set correctly).
             # Use WebSocketHandler method for sending chat
             if hasattr(self.websocket_handler, 'send_chat_message'):
                 self.websocket_handler.send_chat_message(self.current_peer_uid, message)
                 # Add own message to UI immediately for responsiveness
                 if self.main_window:
                      self.main_window.append_chat_message(f"You: {message}")
             else:
                 # Fallback if specific method doesn't exist
                 logging.error("WebSocketHandler missing send_chat_message method.")
                 self.websocket_handler.send_message({
                     "type": "chat_message",
                     "to_user": self.current_peer_uid,
                     "text": message
                 })
                 # Add own message to UI immediately
                 if self.main_window:
                      self.main_window.append_chat_message(f"You: {message}")

        else:
             logging.warning("Cannot send chat: No peer connected or WebSocket disconnected.")
             if self.main_window:
                 self.main_window.append_chat_message("<i>Error: Not connected. Cannot send message.</i>")


    @pyqtSlot()
    def handle_logout(self):
        """Handles logout request from MainWindow UI (cleans up client state)."""
        # TODO (Backend): Consider if an explicit logout notification is needed.
        # E.g., sending a specific WS message or calling an HTTP /api/logout endpoint
        # to allow the backend to clean up session/token state immediately.
        logging.info("Handling logout.")
        # 1. Disconnect from peer if connected (inform peer via backend)
        if self.current_peer_uid:
            self.handle_disconnect(inform_peer=True)

        # 2. Stop WebSocket handler
        if self.websocket_handler:
            self.websocket_handler.stop()
            self.websocket_handler = None

        # 3. Stop RemoteController if active
        if self.remote_controller:
             if hasattr(self.remote_controller, 'stop'):
                  logging.info("Stopping RemoteController...")
                  self.remote_controller.stop()
             self.remote_controller = None
        self._is_sharing_screen = False

        # 4. Close Main Window if open
        if self.main_window:
             try:
                  # Clear screen display before closing
                  if hasattr(self.main_window, "screen_display_widget") and self.main_window.screen_display_widget:
                      self.main_window.screen_display_widget.pixmap = QPixmap()
                      self.main_window.screen_display_widget.update()
             except Exception as e:
                  logging.error(f"Error clearing screen during logout: {e}")
             self.main_window.close()
             self.main_window = None

        # 5. Clear sensitive user data
        self.jwt_token = None
        self.username = None
        self.current_peer_uid = None
        self.control_permissions = {}
        self.backend_base_url = None # Reset URL
        self._reset_fps_counter()

        # 6. Show Login Window again
        self.show_login_window()

    # --- Input Handling --- (When VIEWING and sending control input) ---
    @pyqtSlot(dict)
    def handle_send_input_event(self, event_data):
        """Sends mouse/keyboard events captured by ScreenDisplayWidget TO the peer via backend."""
        # Check if we are connected, have a controller, AND are not in view-only mode
        if (
            self.current_peer_uid
            and self.remote_controller
            and self.main_window and self.main_window.screen_display_widget
            and not self.main_window.screen_display_widget._view_only # Check if control is allowed for us
        ):
            # TODO (Backend): Backend receives this `input_event` message.
            # It MUST verify that the sender (self.username) actually has permission
            # (granted by `current_peer_uid`) to send input before relaying it.
            # If permission granted, relay the event_data to the `current_peer_uid`.
            # The exact format relayed is up to backend/receiving client agreement.
            # print(f"[DEBUG CONTROLLER {self.username}] Sending input: {event_data} to {self.current_peer_uid}")
            # Use RemoteController (which uses WebSocketHandler) to send the event
            self.remote_controller.send_input_event(event_data)
        else:
            # Input ignored - print reason if needed for debugging
            if not self.current_peer_uid: logging.debug("Input ignored: No peer.")
            if not self.remote_controller: logging.debug("Input ignored: No RemoteController.")
            if not (self.main_window and self.main_window.screen_display_widget): logging.debug("Input ignored: No screen widget.")
            if self.main_window and self.main_window.screen_display_widget._view_only: logging.debug("Input ignored: View-Only mode.")
            pass


    # --- Input Handling --- (When SHARING and receiving control input) ---
    def simulate_received_input(self, controller_uid, event_data):
        """Simulates input event received FROM a peer, only if permission is granted."""
        # TODO (Backend): Backend relays input events from controller peer to sharer peer.
        # This method is called when such a relayed event is received.
        # Note: Backend should have already checked permission before relaying.
        if not event_data or not controller_uid:
            logging.debug(f"Ignoring received input: No event data or controller UID (Sharer: {self.username}).")
            return

        # --- Check Local Permission Cache --- 
        # This is a local check, primary enforcement should be on backend before relaying.
        permission_granted = self.control_permissions.get(controller_uid, False)

        if permission_granted:
            # print(f"[DEBUG SHARER {self.username}] Local permission check PASSED for {controller_uid}. Simulating input...")
            try:
                # Delegate simulation to utils module
                utils.simulate_input(event_data)
            except Exception as e:
                logging.error(f"Failed to simulate received input from {controller_uid}: {e}")
                # traceback.print_exc() # Optional detailed trace
        else:
             # Permission not granted locally - Request it via UI thread signal
             # This handles the case where backend might relay but local permission wasn't set/synced,
             # or the initial request attempt.
             if controller_uid in self._permission_requests_pending:
                 # print(f"[DEBUG SHARER {self.username}] Permission request already pending for {controller_uid}. Ignoring event.")
                 logging.debug(f"Permission request already pending for {controller_uid}. Ignoring event.")
                 return # Avoid spamming dialogs

             logging.debug(f"Local permission check FAILED for {controller_uid}. Emitting request signal...")
             # Mark request as pending *before* emitting signal
             self._permission_requests_pending.add(controller_uid)
             # Emit signal to ask user in UI thread
             self.request_permission_signal.emit(controller_uid, event_data)


    @pyqtSlot(str, object)
    def show_permission_dialog_slot(self, controller_uid, pending_event):
        """Shows dialog asking the user (SHARER) for input control permission. Runs in UI thread."""
        # Triggered by `request_permission_signal` when input received without local permission.
        allowed = False # Default
        try:
            if not self.main_window:
                logging.error(f"Cannot show permission dialog for {controller_uid}: MainWindow closed.")
                # TODO (Client): Silently deny or handle? If main window closed, we likely disconnected anyway.
                return

            # Avoid dialog if already connected to someone else (shouldn't happen often)
            if self.current_peer_uid != controller_uid:
                 logging.warning(f"Received control request from {controller_uid} but connected to {self.current_peer_uid}. Denying.")
                 # Silently deny or inform user?
                 self._send_permission_response(controller_uid, False) # Inform peer they were denied
                 return

            logging.debug(f"Showing permission dialog for {controller_uid}")
            reply = QMessageBox.question(
                self.main_window,
                "Control Request",
                f"User '{controller_uid}' wants to control your desktop. Allow?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No, # Default button
            )

            allowed = (reply == QMessageBox.Yes)
            self.control_permissions[controller_uid] = allowed # Update local cache

            if allowed:
                logging.debug(f"Input control permission GRANTED for {controller_uid} by user.")
            else:
                logging.debug(f"Input control permission DENIED for {controller_uid} by user.")

            # Send permission update TO the backend/peer
            # TODO (Backend): Backend receives this `input_permission_update`.
            # It should store this permission state (controller_uid CAN control self.username).
            # It should then relay this message back to the `controller_uid` so their UI updates.
            self._send_permission_response(controller_uid, allowed)

            # Update our own UI checkbox state to reflect the decision
            if self.main_window:
                 self.main_window.mouse_permission_checkbox.blockSignals(True)
                 self.main_window.mouse_permission_checkbox.setChecked(allowed)
                 self.main_window.mouse_permission_checkbox.blockSignals(False)
                 self.main_window.update_control_status_display() # Update status bar

        except Exception as e:
            logging.exception(f"Error showing/handling permission dialog for {controller_uid}: {e}")
            # Attempt to deny on error to be safe
            self._send_permission_response(controller_uid, False)
        finally:
             # Remove from pending requests *after* handling is complete
             if controller_uid in self._permission_requests_pending:
                 self._permission_requests_pending.remove(controller_uid)


    def _send_permission_response(self, controller_uid, allowed):
        """Helper sends the input permission response TO the backend/peer."""
        if self.websocket_handler and self.websocket_handler.is_connected:
            response_message = {
                "type": "input_permission_update",
                "target_uid": controller_uid, # The user who asked for control
                "sender_uid": self.username, # We are the one granting/denying
                "allowed": allowed,
            }
            self.websocket_handler.send_message(response_message)
            logging.debug(f"Sent permission update ({allowed}) to {controller_uid}")
        else:
            logging.warning("Cannot send permission response: WebSocket disconnected.")

    @pyqtSlot(bool)
    def handle_mouse_permission_change(self, allowed):
        """Handles the toggle of the 'Allow Peer Mouse Control' checkbox in MainWindow UI (when SHARING)."""
        # This is triggered by the *user* clicking the checkbox in their own UI.
        if not self.current_peer_uid:
            logging.debug("Ignoring mouse permission change: No peer connected.")
            # Revert checkbox state if toggled erroneously
            if self.main_window:
                 self.main_window.mouse_permission_checkbox.blockSignals(True)
                 self.main_window.mouse_permission_checkbox.setChecked(False)
                 self.main_window.mouse_permission_checkbox.blockSignals(False)
            return

        logging.info(f"User toggled mouse permission for peer {self.current_peer_uid} to: {allowed}")
        self.control_permissions[self.current_peer_uid] = allowed # Update local state

        # Send permission update TO the backend/peer
        # TODO (Backend): Backend receives this, updates stored permission state, relays to peer.
        if self.websocket_handler and self.websocket_handler.is_connected:
            message = {
                "type": "input_permission_update",
                "target_uid": self.current_peer_uid, # Inform the peer
                "sender_uid": self.username, # We are the sender changing the state
                "allowed": allowed,
            }
            self.websocket_handler.send_message(message)
            logging.debug(f"Sent input permission update to {self.current_peer_uid}: {allowed}")

        # Update local status bar display
        if self.main_window:
             self.main_window.update_control_status_display()


    # --- Screen Sharing Logic --- (When WE start/stop sharing)
    @pyqtSlot()
    def start_screen_sharing(self):
        """Initiates screen sharing FROM this client TO the connected peer."""
        # TODO (Backend): No direct message sent here. Backend implicitly knows sharing
        # starts when it receives the first binary screen frame from this client, directed
        # at the `current_peer_uid`. It should then start relaying these frames.
        if not self.current_peer_uid:
            logging.warning("Start sharing requested but no peer connected.")
            QMessageBox.warning(self.main_window, "Sharing Error", "Please connect to a peer first.")
            if self.main_window: self.main_window.set_sharing_state(False) # Reset UI
            return

        if self._is_sharing_screen:
            logging.info("Start sharing requested but already sharing.")
            return

        if not self.remote_controller:
             logging.error("RemoteController not initialized. Cannot start sharing.")
             QMessageBox.critical(self.main_window, "Error", "Internal error: Remote controller not ready.")
             return

        logging.info(f"Attempting to start screen sharing to peer: {self.current_peer_uid}")
        try:
            # Update UI immediately to show potential "sharing" state (actual state confirmed by signal)
            # if self.main_window: self.main_window.set_sharing_state(True)

            # Start sharing using RemoteController with current settings
            self.remote_controller.start_screen_sharing(
                quality=self._stream_quality,
                scale_factor=self._stream_scale_factor,
                fps=self._stream_fps,
                monitor_index=self._stream_monitor_index
                # TODO (Client): Pass self.current_peer_uid to RemoteController if it needs to know who to send to?
                # Or does it implicitly send via the handler which knows the peer? Currently relies on handler.
            )
            # State `_is_sharing_screen = True` is set by `_on_screen_share_status_changed` signal handler.

        except Exception as e:
            logging.exception(f"Error starting screen sharing: {e}")
            self._is_sharing_screen = False # Ensure state is reset on error
            if self.main_window:
                self.main_window.set_sharing_state(False) # Reset UI
                self.main_window.show_status_message(f"Error starting sharing: {e}")
                QMessageBox.critical(self.main_window, "Sharing Error", f"Failed to start screen sharing:\n{e}")


    @pyqtSlot()
    def stop_screen_sharing(self, inform_peer=True): # Added inform_peer flag
        """Stops active screen sharing FROM this client."""
        # TODO (Backend): No direct message sent here needed by backend usually.
        # Backend stops receiving binary frames, which implicitly means sharing stopped.
        # Optionally, client could send a "stopped_sharing" message if needed.
        if not self._is_sharing_screen:
            return

        if not self.remote_controller:
             logging.error("RemoteController not initialized. Cannot stop sharing.")
             self._is_sharing_screen = False # Reset state anyway
             if self.main_window: self.main_window.set_sharing_state(False)
             return

        logging.info("Stopping screen sharing...")
        try:
            # Stop sharing via RemoteController
            self.remote_controller.stop_screen_sharing()
            # State `_is_sharing_screen = False` is set by `_on_screen_share_status_changed` signal handler.

            # TODO (Client/Backend): Decide if an explicit notification to the peer is useful.
            # if inform_peer and self.current_peer_uid and self.websocket_handler and self.websocket_handler.is_connected:
            #     self.websocket_handler.send_message({
            #         "type": "sharing_stopped",
            #         "target_uid": self.current_peer_uid,
            #         "sender_uid": self.username
            #     })

        except Exception as e:
            logging.exception(f"Error stopping screen sharing: {e}")
            # Still attempt to reset state even if error occurs during stop
            self._is_sharing_screen = False
            if self.main_window:
                self.main_window.set_sharing_state(False)
                self.main_window.show_status_message(f"Error stopping sharing: {e}")


    # --- RemoteController Signal Handlers (Events from screen capture/input simulation) ---
    @pyqtSlot(bytes)
    def _on_screen_captured(self, image_data):
        """Called when RemoteController captures a frame (when we are sharing)."""
        # This signal confirms a frame was captured. RemoteController handles sending it via WS handler.
        # No direct backend interaction needed from this handler itself.
        pass

    @pyqtSlot(bool)
    def _on_screen_share_status_changed(self, is_sharing):
        """Called by RemoteController when sharing actually starts or stops."""
        logging.info(f"Screen sharing status changed to: {is_sharing}")
        self._is_sharing_screen = is_sharing
        if self.main_window:
            self.main_window.set_sharing_state(is_sharing) # Update UI based on actual status
            # Update mouse permission checkbox state based on role
            self.main_window.mouse_permission_checkbox.setEnabled(is_sharing)
            if not is_sharing:
                 # Ensure checkbox is unchecked and local permission cleared when sharing stops
                 self.main_window.mouse_permission_checkbox.blockSignals(True)
                 self.main_window.mouse_permission_checkbox.setChecked(False)
                 self.main_window.mouse_permission_checkbox.blockSignals(False)
                 if self.current_peer_uid:
                     self.control_permissions[self.current_peer_uid] = False
            self.main_window.update_control_status_display() # Update status bar

    @pyqtSlot(str)
    def _on_remote_controller_error(self, error_message):
        """Called when RemoteController encounters an error during capture/simulation."""
        logging.error(f"RemoteController error: {error_message}")
        # Stop sharing if an error occurs in the controller
        if self._is_sharing_screen:
             self.stop_screen_sharing(inform_peer=False)
        if self.main_window:
            self.main_window.show_status_message(f"Sharing Error: {error_message}")
            QMessageBox.warning(self.main_window, "Sharing Error", error_message)

    # --- Stream Settings Handlers (UI changes affecting sharing) ---
    # TODO (Backend): Decide if backend needs to be notified of these changes.
    # Currently, these settings primarily affect the client-side RemoteController capture.
    # Backend might only care if enforcing limits or for analytics.
    @pyqtSlot(int)
    def _handle_quality_changed(self, quality):
        if self._stream_quality != quality:
            logging.debug(f"Stream quality setting changed by UI to: {quality}%")
            self._stream_quality = quality
            if self.remote_controller and self._is_sharing_screen:
                self.remote_controller.update_sharing_settings(quality=quality)
            if self.main_window:
                self.main_window.update_quality_display(quality)
            # self._send_stream_settings_update() # Optional: Send update to backend/peer

    @pyqtSlot(int)
    def _handle_scale_changed(self, scale_percent):
        scale_factor = scale_percent / 100.0
        if self._stream_scale_factor != scale_factor:
            logging.debug(f"Stream scale setting changed by UI to: {scale_percent}% (Factor: {scale_factor})")
            self._stream_scale_factor = scale_factor
            if self.remote_controller and self._is_sharing_screen:
                self.remote_controller.update_sharing_settings(scale_factor=scale_factor)
            # self._send_stream_settings_update() # Optional: Send update to backend/peer

    @pyqtSlot(int)
    def _handle_fps_changed(self, fps):
         if self._stream_fps != fps:
            logging.debug(f"Stream Max FPS setting changed by UI to: {fps}")
            self._stream_fps = fps
            if self.remote_controller and self._is_sharing_screen:
                self.remote_controller.update_sharing_settings(fps=fps)
            # self._send_stream_settings_update() # Optional: Send update to backend/peer

    @pyqtSlot(int)
    def _handle_monitor_changed(self, monitor_index):
        """Handles signal when monitor selection changes (1-based index)."""
        if self._stream_monitor_index != monitor_index:
            logging.debug(f"Stream monitor setting changed by UI to index: {monitor_index}")
            self._stream_monitor_index = monitor_index
            if self.remote_controller and self._is_sharing_screen:
                self.remote_controller.update_sharing_settings(monitor_index=monitor_index)
            # self._send_stream_settings_update() # Optional: Send update to backend/peer

    # def _send_stream_settings_update(self):
    #     """Optional: Sends current stream settings to backend/peer."""
    #     if self.websocket_handler and self.websocket_handler.is_connected and self.current_peer_uid and self._is_sharing_screen:
    #         settings = {
    #             "quality": self._stream_quality,
    #             "scale": int(self._stream_scale_factor * 100),
    #             "fps": self._stream_fps,
    #             "monitor": self._stream_monitor_index
    #         }
    #         message = {
    #             "type": "stream_settings_update",
    #             "target_uid": self.current_peer_uid,
    #             "sender_uid": self.username,
    #             "settings": settings
    #         }
    #         self.websocket_handler.send_message(message)
    #         print(f"[DEBUG] Sent stream settings update: {settings}")

    # --- Helper for FPS counter (Receiving/Viewing) ---
    def _reset_fps_counter(self):
        """Resets the FPS counter used when viewing."""
        self._received_frame_counter = 0
        self._fps_calc_start_time = time.perf_counter()
        # Reset display in UI immediately
        self.fps_updated_signal.emit(0.0)

    @pyqtSlot(float)
    def _handle_fps_update_to_ui(self, fps):
        """Updates the FPS display in the MainWindow status bar."""
        if self.main_window:
            self.main_window.update_fps_display(fps)

    # --- Auto Reconnect Slot --- (Internal client logic)
    @pyqtSlot()
    def _attempt_reconnect(self):
        """Attempts to reconnect to the WebSocket server."""
        self._reconnect_attempts += 1
        logging.info(f"Attempting to reconnect (Attempt {self._reconnect_attempts}/{self.MAX_RECONNECT_ATTEMPTS})")

        # Update UI
        if self.main_window:
            self.main_window.show_status_message("Attempting WebSocket Reconnect...")
            # Ensure main window shows disconnected state during attempts
            self.main_window.set_disconnected_state("Attempting Reconnect...")

        # Try initializing the WebSocket again
        self.init_websocket()

        # Check if max attempts reached
        if self._reconnect_attempts >= self.MAX_RECONNECT_ATTEMPTS and self._reconnect_timer.isActive():
            logging.warning("Max reconnect attempts reached. Giving up.")
            self._reconnect_timer.stop()
            if self.main_window:
                self.main_window.show_status_message("WebSocket Disconnected. Max reconnect attempts reached.")
                self.main_window.set_disconnected_state("WebSocket Reconnection Failed")


    # --- Slot for View Permission Request (Incoming from peer via backend) ---
    @pyqtSlot(str)
    def _ask_view_permission_slot(self, requester_uid):
        """Shows dialog asking user (SHARER) to allow viewing. Runs in UI thread."""
        # Triggered by `peer_connection_requested_signal` from WebSocketHandler.
        allowed = False # Default
        try:
            if not self.main_window:
                logging.error("[Error] Cannot ask view permission, main window missing.")
                # TODO (Client): Reject automatically if UI isn't there?
                # self._send_view_response(requester_uid, False)
                return

            # Prevent accepting connection if already connected to someone else
            if self.current_peer_uid and self.current_peer_uid != requester_uid:
                 logging.warning(f"Already connected to {self.current_peer_uid}. Rejecting new request from {requester_uid}.")
                 QMessageBox.information(self.main_window, "Busy", f"Already connected to {self.current_peer_uid}. Please disconnect first.")
                 # Send rejection response TO backend/peer
                 self._send_view_response(requester_uid, False)
                 return
            # Handle case where request comes from current peer (shouldn't happen in normal flow)
            elif self.current_peer_uid == requester_uid:
                 logging.warning(f"[WARN] Received view request from already connected peer {requester_uid}. Ignoring.")
                 return

            logging.debug(f"[UI SLOT] Asking user permission for view request from {requester_uid}")
            reply = QMessageBox.question(
                self.main_window,
                "View Request",
                f"User '{requester_uid}' wants to connect and view your screen. Allow?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No, # Default button
            )

            allowed = (reply == QMessageBox.Yes)

            # Send response back TO the backend/requester via WebSocketHandler
            # TODO (Backend): Backend receives this `view_response`.
            # If allowed=True, it establishes the peer link and notifies the requester.
            # If allowed=False, it just notifies the requester.
            self._send_view_response(requester_uid, allowed)

            if allowed:
                logging.debug(f"[UI SLOT] User ALLOWED view request from {requester_uid}")
                # Set peer connection state locally
                self.current_peer_uid = requester_uid
                self.control_permissions.clear() # Clear old permissions for new peer
                if self.main_window:
                     self.main_window.set_connected_state(requester_uid)
                     # Role set to Idle. User needs to click "Share Screen" to start sharing.
                     self.main_window.set_role(ui.MainWindow.ROLE_IDLE)
                     # Enable mouse permission checkbox, default to unchecked (peer cannot control yet)
                     self.main_window.mouse_permission_checkbox.setEnabled(True)
                     self.main_window.mouse_permission_checkbox.blockSignals(True)
                     self.main_window.mouse_permission_checkbox.setChecked(False)
                     self.main_window.mouse_permission_checkbox.blockSignals(False)
                     self.main_window.update_control_status_display()
            else:
                logging.debug(f"[UI SLOT] User DENIED view request from {requester_uid}")
                # No local state change needed, UI remains disconnected

        except Exception as e:
            logging.exception(f"Error asking view permission for {requester_uid}: {e}")
            # Ensure rejection response is sent on error
            if requester_uid:
                 self._send_view_response(requester_uid, False)

    def _send_view_response(self, target_uid, allowed):
        """Helper sends the view permission response TO the backend/requester via WebSocket."""
        if self.websocket_handler and self.websocket_handler.is_connected:
            response_message = {
                "type": "view_response", # This client's response to a view request
                "target_uid": target_uid, # The user who requested to view us
                "sender_uid": self.username, # We are the one responding
                "allowed": allowed,
                "message": ("View request accepted" if allowed else "View request denied by user"),
            }
            logging.debug(f"Sending view_response to {target_uid}: Allowed={allowed}")
            self.websocket_handler.send_message(response_message)
        else:
             logging.error(f"Cannot send view response to {target_uid}: WebSocket disconnected.")


    # --- Application Lifecycle ---
    def run(self):
        """Starts the Qt application event loop."""
        # TODO (Backend): Ensure backend server is running before client starts.
        self.app.aboutToQuit.connect(self.cleanup)
        sys.exit(self.app.exec_())

    def cleanup(self):
        """Ensures resources are cleaned up gracefully on application exit."""
        # TODO (Backend): Consider if backend needs notification on clean client exit
        # (e.g., via WS close frame or explicit `disconnect_peer` before closing).
        logging.info("Cleaning up before application exit...")
        # Stop screen sharing if active
        if self._is_sharing_screen:
             self.stop_screen_sharing(inform_peer=False) # Stop locally

        # Stop RemoteController thread/tasks
        if self.remote_controller:
             if hasattr(self.remote_controller, 'stop'):
                  logging.info("Stopping RemoteController...")
                  self.remote_controller.stop()

        # Stop WebSocket handler (sends close frame)
        if self.websocket_handler:
            self.websocket_handler.stop()

        logging.info("Cleanup finished.")


if __name__ == "__main__":
    # TODO (Packaging): Ensure necessary dependencies (PyQt5, websocket-client, Pillow, httpx, screeninfo, mss, etc.)
    # are listed in requirements.txt for deployment.
    import mss # Ensure mss is imported if needed by RemoteController init
    controller = AppController()
    controller.run()