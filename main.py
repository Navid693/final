import sys
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import QObject, pyqtSignal, QTimer, pyqtSlot
from PyQt5.QtGui import QPixmap , QIcon , QPaintEvent , QKeyEvent, QMouseEvent, QWheelEvent, QPaintEvent
import base64
import threading
import time
import traceback
import json
from PIL import Image
import io
import httpx # Keep httpx import for future API calls

# Import local modules
import utils
import ui
# Removed unused server/client imports
from websocket_handler import WebSocketHandler # Import WebSocketHandler
from remote_controller import RemoteController # Import the RemoteController class

# --- Function to load stylesheet ---
def load_stylesheet(theme_name="dark"):
    """Loads and returns the content of a QSS file based on theme name."""
    base_filename = f"{theme_name}_styles.qss" if theme_name == "light" else "styles.qss"
    filename = f"styles/{base_filename}" # Prepend the directory
    print(f"[DEBUG] Attempting to load stylesheet: {filename}")
    try:
        with open(filename, "r") as f:
            return f.read()
    except FileNotFoundError:
        print(f"[WARNING] Stylesheet file '{filename}' not found.")
        return "" # Return empty string if file not found
    except Exception as e:
        print(f"[ERROR] Failed to load stylesheet '{filename}': {e}")
        return ""

class AppController(QObject):
    # Signal to request showing the permission dialog in the GUI thread
    request_permission_signal = pyqtSignal(str, object) # controller_uid, pending_event
    # Signal for FPS updates from viewing
    fps_updated_signal = pyqtSignal(float) # Emits calculated FPS
    # Add signals related to view request
    request_view_permission_signal = pyqtSignal(str) # Ask user if peer can view

    RECONNECT_DELAY_MS = 5000 # Delay between reconnect attempts (5 seconds)
    MAX_RECONNECT_ATTEMPTS = 5 # Max number of attempts

    def __init__(self):
        super().__init__() # Initialize the QObject base class
        self.app = QApplication(sys.argv)
        self.current_theme = "dark" # Start with dark theme

        # New attributes for new architecture
        self.login_window = None
        self.main_window = None
        self.api_client = None # TODO: Implement API interaction logic here
        self.websocket_handler = None
        self.jwt_token = None
        self.backend_base_url = None # Will be set from LoginWindow
        self.username = None # Store username after login
        self.current_peer_uid = None # Store UID of the peer we are connected to
        self.control_permissions = {} # Store permission status: {peer_uid: bool}

        # RemoteController instance
        self._is_sharing_screen = False
        self.remote_controller = None # Initialized after websocket is ready

        # Apply initial theme
        self.apply_theme()

        # Default streaming settings
        self._stream_quality = ui.MainWindow.DEFAULT_QUALITY
        self._stream_scale_factor = ui.MainWindow.DEFAULT_SCALE / 100.0
        self._stream_fps = ui.MainWindow.DEFAULT_FPS
        self._stream_monitor_index = ui.MainWindow.DEFAULT_MONITOR_INDEX

        # Attributes for FPS calculation (when viewing)
        self._received_frame_counter = 0
        self._fps_calc_start_time = time.perf_counter()
        self._last_status_message = "Initializing..." # Store last base status

        # Auto-Reconnect Attributes
        self._reconnect_attempts = 0
        self._reconnect_timer = QTimer()
        self._reconnect_timer.timeout.connect(self._attempt_reconnect)

        # Connect signals that are always relevant
        self.request_permission_signal.connect(self.show_permission_dialog_slot)
        self.fps_updated_signal.connect(self._handle_fps_update_to_ui)
        self.request_view_permission_signal.connect(self._ask_view_permission_slot)

        self._permission_requests_pending = set() # Track pending requests {peer_uid}

        # Start with login window
        self.show_login_window()

    def apply_theme(self):
        """Loads and applies the stylesheet for the current theme."""
        stylesheet = load_stylesheet(self.current_theme)
        if stylesheet:
            self.app.setStyleSheet(stylesheet)
            print(f"[DEBUG] Applied {self.current_theme} theme stylesheet.")
        else:
            self.app.setStyleSheet("") # Clear stylesheet if loading fails
            print(f"[WARNING] Failed to load {self.current_theme} stylesheet, cleared styles.")

        # Update UI elements that need explicit theme changes
        if self.login_window:
            self.login_window._update_theme_icon(self.current_theme)
        if self.main_window:
             self.main_window._update_theme_icon(self.current_theme)

    @pyqtSlot()
    def toggle_theme(self):
        """Switches between light and dark themes and reapplies styles."""
        print("[DEBUG] Toggling theme...")
        self.current_theme = "light" if self.current_theme == "dark" else "dark"
        self.apply_theme() # Reload and apply the new stylesheet

    def show_login_window(self):
        """Displays the login window."""
        if self.login_window is None:
            self.login_window = ui.LoginWindow()
            self.login_window.login_attempt_signal.connect(self.handle_login_attempt)
            self.login_window.toggle_theme_signal.connect(self.toggle_theme)
            # TODO: Connect register_signal if needed
        self.login_window._update_theme_icon(self.current_theme) # Ensure icon is correct
        self.login_window.show()

    @pyqtSlot(str, str, str)
    def handle_login_attempt(self, backend_url, username, password):
        """Handles the login attempt signal from LoginWindow."""
        print(f"Attempting login to {backend_url} for user {username}")
        self.backend_base_url = backend_url
        self.username = username # Store username
        self.login_window.set_logging_in() # Update UI

        # <<<<< START: SIMULATED LOGIN - REPLACE WITH ACTUAL API CALL >>>>>
        # TODO: Replace this block with actual httpx API call to backend_url/login
        # Example (needs refinement based on actual API):
        # try:
        #     async with httpx.AsyncClient() as client:
        #         response = await client.post(f"{backend_url}/api/login", json={"username": username, "password": password})
        #         response.raise_for_status() # Raise exception for 4xx/5xx status
        #         data = response.json()
        #         if data.get("success") and data.get("token"):
        #             self.jwt_token = data["token"]
        #             print("Login successful!")
        #             self.on_login_success()
        #         else:
        #             error_msg = data.get("message", "Login failed.")
        #             print(f"Login failed: {error_msg}")
        #             self.login_window.show_error(error_msg)
        # except httpx.RequestError as e:
        #     print(f"Login network error: {e}")
        #     self.login_window.show_error(f"Network error: {e}")
        # except Exception as e:
        #     print(f"Login error: {e}")
        #     self.login_window.show_error(f"An error occurred: {e}")

        # --- Temporary Simulation ---
        import time
        time.sleep(1) # Simulate network delay
        print("Login successful (Simulated)!")
        self.jwt_token = "fake_jwt_token_for_testing" # Use fake token
        self.on_login_success()
        # --- End Temporary Simulation ---
        # <<<<< END: SIMULATED LOGIN - REPLACE WITH ACTUAL API CALL >>>>>

    def on_login_success(self):
        """Called after successful login."""
        if self.login_window:
            self.login_window.close()
        self.login_window = None

        print(f"Proceeding to main app for user {self.username} with token: {self.jwt_token}")
        self.show_main_window()
        self.init_websocket() # Initialize WebSocket after showing main window

    def show_main_window(self):
        """Creates and shows the main application window."""
        if self.main_window is None:
            print("[DEBUG] Creating MainWindow...")
            self.main_window = ui.MainWindow(self.username, self.current_theme)

            # --- Connect signals FROM MainWindow TO Controller ---
            print("[DEBUG] Connecting MainWindow signals...")
            self.main_window.request_view_signal.connect(self.handle_request_view)
            self.main_window.disconnect_signal.connect(self.handle_disconnect)
            self.main_window.send_chat_message_signal.connect(self.handle_send_chat)
            self.main_window.logout_signal.connect(self.handle_logout)
            self.main_window.toggle_theme_signal.connect(self.toggle_theme)
            self.main_window.start_sharing_signal.connect(self.start_screen_sharing)
            self.main_window.stop_sharing_signal.connect(self.stop_screen_sharing)
            self.main_window.mouse_permission_signal.connect(self.handle_mouse_permission_change)

            # Connect Stream Settings Signals
            self.main_window.quality_changed_signal.connect(self._handle_quality_changed)
            self.main_window.scale_changed_signal.connect(self._handle_scale_changed)
            self.main_window.fps_changed_signal.connect(self._handle_fps_changed)
            self.main_window.monitor_changed_signal.connect(self._handle_monitor_changed)

            # Connect screen input signals (ensure widget exists)
            if hasattr(self.main_window, "screen_display_widget") and self.main_window.screen_display_widget:
                self.main_window.screen_display_widget.mouse_event_signal.connect(self.handle_send_input_event)
                self.main_window.screen_display_widget.key_event_signal.connect(self.handle_send_input_event)
                print("[DEBUG]  - screen_display_widget signals connected.")
            else:
                 print("[WARN] screen_display_widget not found on main_window during signal connection.")

            print("[DEBUG] MainWindow signals connected.")
            self.main_window.show()
            print("[DEBUG] MainWindow shown.")

        # Ensure screen display starts in view-only mode
        if (
            hasattr(self.main_window, "screen_display_widget")
            and self.main_window.screen_display_widget
        ):
            print("[DEBUG] Setting screen display widget to view-only mode initially.")
            self.main_window.screen_display_widget.set_view_only(True)


    def init_websocket(self):
        """Initializes and attempts to connect the WebSocket handler."""
        if not self.backend_base_url: # Removed check for jwt_token as it might not be needed for initial WS connection itself
            print("Cannot initialize WebSocket: Missing Backend URL.")
            # TODO: Maybe show error to user if main_window exists
            return

        if self.websocket_handler and self.websocket_handler.is_connected:
            print("WebSocket already connected.")
            if self._reconnect_timer.isActive():
                print("Stopping reconnect timer as connection established.")
                self._reconnect_timer.stop()
            self._reconnect_attempts = 0 # Reset attempts on successful manual init
            return

        print(f"Initializing WebSocket Handler (Attempt: {self._reconnect_attempts + 1})...")
        if self._reconnect_attempts == 0 and self._reconnect_timer.isActive():
            self._reconnect_timer.stop()

        # Create websocket handler
        # TODO: Pass jwt_token to WebSocketHandler for authentication during connection handshake or first message
        # self.websocket_handler = WebSocketHandler(self.backend_base_url, self.username, self.jwt_token) # Pass token
        self.websocket_handler = WebSocketHandler(self.backend_base_url, self.username)

        # --- Connect signals FROM WebSocketHandler TO Controller ---
        self.websocket_handler.connected_signal.connect(self.on_websocket_connected)
        self.websocket_handler.disconnected_signal.connect(self.on_websocket_disconnected)
        self.websocket_handler.error_signal.connect(self.on_websocket_error)
        # Use specific signals from WebSocketHandler where available
        self.websocket_handler.user_registered_signal.connect(self._on_user_registered)
        self.websocket_handler.users_list_updated_signal.connect(self._on_users_list_updated)
        self.websocket_handler.peer_connection_requested_signal.connect(self._on_peer_connection_requested)
        self.websocket_handler.peer_connected_signal.connect(self._on_peer_connected)
        self.websocket_handler.peer_disconnected_signal.connect(self._on_peer_disconnected)
        self.websocket_handler.chat_message_received_signal.connect(self._on_chat_message_received)
        # Use generic message handler for types not covered by specific signals
        self.websocket_handler.message_received_signal.connect(self.handle_websocket_message)
        # Handle binary data (likely screen frames + cursor)
        self.websocket_handler.binary_message_received_signal.connect(self.handle_websocket_binary_message)

        # Initialize RemoteController *after* websocket_handler is created
        if not self.remote_controller:
             self.remote_controller = RemoteController(self.websocket_handler)
             # Connect RemoteController signals TO Controller/UI
             self.remote_controller.screen_captured_signal.connect(self._on_screen_captured)
             self.remote_controller.screen_share_status_signal.connect(self._on_screen_share_status_changed)
             self.remote_controller.error_signal.connect(self._on_remote_controller_error)
             # Use the direct FPS signal from RemoteController for *sending* FPS info (if needed)
             # self.remote_controller.fps_updated_signal.connect(...) # Connect if needed

        # Attempt WebSocket connection
        self.websocket_handler.connect_ws()

    # --- WebSocket Signal Handlers ---
    @pyqtSlot()
    def on_websocket_connected(self):
        """Called when WebSocket connection is established."""
        print("WebSocket connected successfully!")
        if self._reconnect_timer.isActive():
            print("Stopping reconnect timer as connection established.")
            self._reconnect_timer.stop()
        self._reconnect_attempts = 0

        if self.main_window:
             # Update status bar (only WS part if separated, or general message)
             # self.main_window.update_ws_status("Connected") # If using separate WS status
             self.main_window.show_status_message("WebSocket Connected. Ready.")
             # Potentially refresh user list or other initial state from backend here

    @pyqtSlot(str)
    def on_websocket_disconnected(self, reason):
        """Called when WebSocket connection is lost."""
        print(f"WebSocket disconnected: {reason}")

        # Clean up peer connection state if WS disconnects
        if self.current_peer_uid:
             self.handle_disconnect(inform_peer=False) # Disconnect locally without sending msg

        # Attempt auto-reconnect
        if (not self._reconnect_timer.isActive() and
            self._reconnect_attempts < self.MAX_RECONNECT_ATTEMPTS):
            print(f"Starting reconnect timer. Attempt {self._reconnect_attempts + 1}/{self.MAX_RECONNECT_ATTEMPTS}")
            self._reconnect_timer.start(self.RECONNECT_DELAY_MS)
            if self.main_window:
                # self.main_window.update_ws_status("Reconnecting...")
                self.main_window.show_status_message(f"WebSocket Disconnected: {reason}. Retrying...")
        else:
            # Max attempts reached or timer already active (shouldn't happen often)
             if self.main_window:
                # self.main_window.update_ws_status("Disconnected (Failed)")
                self.main_window.show_status_message("WebSocket Disconnected. Reconnection failed.")
                # Ensure main window shows fully disconnected state
                self.main_window.set_disconnected_state("WebSocket Connection Failed")


    @pyqtSlot(str)
    def on_websocket_error(self, error_message):
        """Called when a WebSocket error occurs."""
        print(f"WebSocket error: {error_message}")
        if self.main_window:
             # self.main_window.update_ws_status("Error")
             self.main_window.show_status_message(f"WebSocket Error: {error_message}")
             # Consider if disconnect state should be triggered on certain errors

    @pyqtSlot(dict)
    def handle_websocket_message(self, message):
        """Handle incoming JSON WebSocket messages NOT covered by specific signals."""
        try:
            message_type = message.get("type")
            sender_uid = message.get("sender_uid") # Common field
            print(f"[DEBUG Client {self.username}] Received generic WS message: Type={message_type}, Sender={sender_uid}")

            # --- Handle message types not covered by specific signals ---
            # Example: Status updates, permission responses, view responses etc.
            # if message_type == "some_other_status":
            #     # process
            # elif message_type == "peer_typing":
            #     # process

            # --- Handle Permission Updates (important) ---
            if message_type == "input_permission_update":
                allowed = message.get("allowed", False)
                if sender_uid and sender_uid == self.current_peer_uid:
                    print(f"[DEBUG] Received input permission update from {sender_uid}: {allowed}")
                    self.control_permissions[sender_uid] = allowed
                    # Update UI (ScreenDisplayWidget's view_only state)
                    if self.main_window and self.main_window.screen_display_widget:
                         self.main_window.screen_display_widget.set_view_only(not allowed)
                         # Also update the status bar display
                         self.main_window.update_control_status_display()
                         print(f"[DEBUG] Set screen display view_only to: {not allowed}")

                    # Optionally show a notification to the user
                    # status = "allowed" if allowed else "denied"
                    # QMessageBox.information(self.main_window, "Input Permission", f"Peer '{sender_uid}' {status} remote control.")
                else:
                    print(f"[WARN] Received input_permission_update from unexpected sender {sender_uid} or no peer connected.")

            # --- Handle View Responses ---
            elif message_type == "view_response":
                allowed = message.get("allowed", False)
                response_sender = message.get("sender_uid")
                target_requester = message.get("target_uid") # Should be self.username

                if target_requester != self.username:
                     print(f"[WARN] Received view_response intended for {target_requester}")
                     return # Ignore responses not meant for us

                # Re-enable the request button now that we have a response
                if self.main_window:
                    self.main_window.request_view_button.setEnabled(True)

                if allowed and response_sender:
                    print(f"[DEBUG] View request accepted by {response_sender}")
                    # Successfully connected for viewing
                    self.current_peer_uid = response_sender
                    self.control_permissions.clear() # Clear old permissions
                    # Update UI to connected state (viewing role set when first frame arrives)
                    if self.main_window:
                        self.main_window.set_connected_state(response_sender)
                        # Role will be set to VIEWING when first frame is received
                        self.main_window.set_role(ui.MainWindow.ROLE_IDLE) # Start as idle until frame arrives
                        # Start viewing - enable screen widget input based on initial permission
                        if self.main_window.screen_display_widget:
                             # Assume view-only initially, permission update will follow if granted
                             self.main_window.screen_display_widget.set_view_only(True)
                             self.main_window.update_control_status_display()
                    self._reset_fps_counter() # Reset FPS counter for new view
                else:
                    denial_message = message.get("message", f"User '{response_sender}' denied your view request.")
                    print(f"[DEBUG] View request denied by {response_sender}")
                    # Update UI to disconnected state (or show message)
                    if self.main_window:
                        self.main_window.set_disconnected_state(denial_message) # Show reason in status
                        # Inform the user more explicitly
                        QMessageBox.information(self.main_window,"View Request Denied", denial_message)

            # --- Handle other potential generic messages ---
            elif message_type == "error": # Generic error from backend/peer
                error_message = message.get("message", "Unknown error from peer/server")
                print(f"[ERROR] Received error message: {error_message}")
                if self.main_window:
                    self.main_window.show_status_message(f"Error: {error_message}")
                    QMessageBox.warning(self.main_window, "Error", error_message)

            else:
                print(f"[WARNING] Unhandled generic message type: {message_type}")

        except Exception as e:
            print(f"[ERROR] Error handling generic WebSocket message: {e}")
            traceback.print_exc()

    @pyqtSlot(bytes)
    def handle_websocket_binary_message(self, data_bytes):
        """Handles BINARY messages (screen frames + cursor) received from the WebSocket."""
        if not data_bytes or len(data_bytes) <= 8: # Check size for image + cursor data
            return

        if (
            self.main_window
            and hasattr(self.main_window, "update_remote_screen")
            and hasattr(self.main_window, "update_remote_cursor")
            and self.main_window.screen_display_widget # Ensure widget exists
        ):
             # If we are receiving frames, our role is VIEWING
             if self.main_window._current_role != ui.MainWindow.ROLE_VIEWING:
                 print("[DEBUG] Received first frame, setting role to VIEWING")
                 self.main_window.set_role(ui.MainWindow.ROLE_VIEWING)
                 # Update control status based on current permission
                 self.main_window.update_control_status_display()

             # --- Increment frame counter for FPS ---
             self._received_frame_counter += 1

             try:
                 # Separate image data and cursor data (JPEG + 4 bytes X + 4 bytes Y)
                 image_data = data_bytes[:-8]
                 cursor_x = int.from_bytes(data_bytes[-8:-4], "big", signed=False)
                 cursor_y = int.from_bytes(data_bytes[-4:], "big", signed=False)

                 # Update the UI
                 self.main_window.update_remote_screen(image_data)
                 self.main_window.update_remote_cursor(cursor_x, cursor_y)

             except Exception as e:
                 print(f"Error processing received binary frame data: {e}")
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
        # else:
            # print("[WARN] MainWindow not ready to display received binary frame.")


    # --- Specific WebSocket Signal Handlers (from WebSocketHandler) ---
    @pyqtSlot(bool, str)
    def _on_user_registered(self, success, message):
        """Called when registration with the server is complete"""
        print(f"User registration response: {success}, Message: {message}")
        if self.main_window:
            self.main_window.show_status_message(message)
        # TODO: Handle UI changes if registration fails/succeeds (e.g., back to login?)

    @pyqtSlot(list)
    def _on_users_list_updated(self, users):
        """Called when the server sends an updated user list"""
        print(f"Users list updated: {users}")
        # TODO: Implement user list display in MainWindow and update it here
        # if self.main_window:
        #     self.main_window.update_users_list(users)


    @pyqtSlot(str)
    def _on_peer_connection_requested(self, requesting_username):
        """Called when a peer requests a connection TO US (for viewing or control)"""
        print(f"Connection request received from: {requesting_username}")

        # Ask user for permission (using the signal to ensure it runs in UI thread)
        self.request_view_permission_signal.emit(requesting_username)


    @pyqtSlot(str)
    def _on_peer_connected(self, username):
        """Called when WebSocketHandler confirms a peer-to-peer connection is established
           (either initiated by us or accepted by us)."""
        print(f"Controller notified: Connected to peer: {username}")
        # This might be redundant if view_response already handles UI update for outgoing requests
        # And _ask_view_permission_slot handles UI update for incoming requests upon acceptance.
        # However, it's a good confirmation.
        if not self.current_peer_uid: # Only update if not already set by view_response/acceptance
             self.current_peer_uid = username
             if self.main_window:
                 self.main_window.set_connected_state(username)
                 # Role will be set based on whether we receive frames (viewing) or start sharing


    @pyqtSlot(str, str)
    def _on_peer_disconnected(self, username, reason):
        """Called when WebSocketHandler detects a peer disconnection."""
        print(f"Controller notified: Disconnected from peer: {username}, Reason: {reason}")
        if self.current_peer_uid == username:
            self.handle_disconnect(inform_peer=False) # Clean up local state
            if self.main_window:
                 self.main_window.show_status_message(f"Peer {username} disconnected: {reason}")
        else:
            print(f"[WARN] Received disconnect for non-current peer {username}")


    @pyqtSlot(str, str)
    def _on_chat_message_received(self, sender_username, message):
        """Called when a chat message is received"""
        print(f"Chat from {sender_username}: {message}")
        if self.main_window and sender_username == self.current_peer_uid:
            # Format message before appending
            formatted_message = f"{sender_username}: {message}"
            self.main_window.append_chat_message(formatted_message)
        elif not self.current_peer_uid:
             print("[WARN] Chat message received but no peer connected.")
        else:
             print(f"[WARN] Chat message received from {sender_username} but connected to {self.current_peer_uid}")

    # --- MainWindow Signal Handlers ---

    @pyqtSlot(str)
    def handle_request_view(self, target_uid):
        """Handles the 'Connect' button click from MainWindow to request viewing a peer."""
        print(f"[DEBUG Client {self.username}] UI requested to view UID: {target_uid}")

        if not target_uid or target_uid.strip() == "" or target_uid == self.username:
            QMessageBox.warning(self.main_window,"Error","Please enter a valid Peer UID to connect to (cannot connect to self).")
            # Ensure UI resets from connecting state if validation fails
            if self.main_window:
                self.main_window.set_peer_connection_status(ui.MainWindow.PEER_STATUS_DISCONNECTED)
                self.main_window.request_view_button.setEnabled(True)
            return

        if self.websocket_handler and self.websocket_handler.is_connected:
            # --- Send view request message via WebSocket ---
            message = {
                "type": "request_view",
                "target_uid": target_uid,
                "sender_uid": self.username,
            }
            success = self.websocket_handler.send_message(message)

            if success and self.main_window:
                # Update UI to show "Connecting..." status
                self.main_window.set_peer_connection_status(ui.MainWindow.PEER_STATUS_CONNECTING)
                self.main_window.show_status_message(f"Requesting to view {target_uid}'s screen...")
                # Disable the request button while waiting for response
                self.main_window.request_view_button.setEnabled(False)
                print(f"[DEBUG] Sent view request to {target_uid}, waiting for response")
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
        """Handles disconnection from current peer (button click or internal)."""
        if not self.current_peer_uid:
            print("Not currently connected to a peer.")
            return

        peer_to_disconnect = self.current_peer_uid
        print(f"Disconnecting from peer: {peer_to_disconnect}")

        try:
            # Stop sharing if active
            if self._is_sharing_screen:
                self.stop_screen_sharing(inform_peer=False) # Stop locally first

            # Send disconnect message via WebSocketHandler if requested
            if inform_peer and self.websocket_handler and self.websocket_handler.is_connected:
                 # Use WebSocketHandler method if it exists, otherwise send manually
                 if hasattr(self.websocket_handler, 'disconnect_from_peer'):
                     self.websocket_handler.disconnect_from_peer()
                 else:
                     self.websocket_handler.send_message({
                         "type": "disconnect",
                         "target_uid": peer_to_disconnect, # Inform the peer
                     })

        except Exception as e:
            print(f"Error during disconnect signalling: {e}")
            traceback.print_exc()
        finally:
             # --- Always clean up local state ---
             self.current_peer_uid = None
             self.control_permissions = {} # Clear permissions
             self._reset_fps_counter() # Reset viewing FPS counter

             # Update UI to disconnected state
             if self.main_window:
                 self.main_window.set_disconnected_state(f"Disconnected from {peer_to_disconnect}")
                 # Role should reset to IDLE within set_disconnected_state

    @pyqtSlot(str)
    def handle_send_chat(self, message):
        """Handles sending a chat message from MainWindow."""
        if not message or not message.strip():
            return
        if self.current_peer_uid and self.websocket_handler and self.websocket_handler.is_connected:
             print(f"Sending chat to {self.current_peer_uid}: {message}")
             # Use WebSocketHandler method for sending chat
             if hasattr(self.websocket_handler, 'send_chat_message'):
                 self.websocket_handler.send_chat_message(self.current_peer_uid, message)
                 # Add own message to UI immediately
                 if self.main_window:
                      self.main_window.append_chat_message(f"You: {message}")
             else:
                 print("[ERROR] WebSocketHandler missing send_chat_message method.")
                 if self.main_window:
                      self.main_window.append_chat_message("<i>Error: Cannot send message (internal error).</i>")
        else:
             print("[WARN] Cannot send chat: No peer connected or WebSocket disconnected.")
             if self.main_window:
                 self.main_window.append_chat_message("<i>Error: Not connected. Cannot send message.</i>")


    @pyqtSlot()
    def handle_logout(self):
        """Handles logout request from MainWindow."""
        print("Controller: Handling logout.")
        # 1. Disconnect from peer if connected
        if self.current_peer_uid:
            self.handle_disconnect(inform_peer=True) # Inform peer if possible

        # 2. Stop WebSocket handler
        if self.websocket_handler:
            self.websocket_handler.stop()
            self.websocket_handler = None

        # 3. Stop RemoteController if active
        if self.remote_controller:
             # Assuming RemoteController has a stop method for its thread/tasks
             if hasattr(self.remote_controller, 'stop'):
                  print("Stopping RemoteController...")
                  self.remote_controller.stop()
             self.remote_controller = None
        self._is_sharing_screen = False

        # 4. Close Main Window if open
        if self.main_window:
             try:
                  # Clear screen display before closing to avoid artifacts
                  if hasattr(self.main_window, "screen_display_widget") and self.main_window.screen_display_widget:
                      self.main_window.screen_display_widget.pixmap = QPixmap()
                      self.main_window.screen_display_widget.update()
             except Exception as e:
                  print(f"Error clearing screen during logout: {e}")
             self.main_window.close()
             self.main_window = None

        # 5. Clear user data
        self.jwt_token = None
        self.username = None
        self.current_peer_uid = None
        self.control_permissions = {}
        self.backend_base_url = None # Reset URL
        self._reset_fps_counter()

        # 6. Show Login Window again
        self.show_login_window()

    # --- Input Handling ---
    @pyqtSlot(dict)
    def handle_send_input_event(self, event_data):
        """Sends mouse/keyboard events captured by ScreenDisplayWidget to the peer."""
        # This client is acting as the 'Controller' sending input
        if (self.current_peer_uid and
            self.remote_controller and
            not self.main_window.screen_display_widget._view_only): # Check view_only status
            # print(f"[DEBUG CONTROLLER {self.username}] Sending input: {event_data} to {self.current_peer_uid}")
            # Use RemoteController to send the event via WebSocketHandler
            self.remote_controller.send_input_event(event_data)
        # else:
            # Reason for not sending (for debugging)
            # if not self.current_peer_uid: print(f"[DEBUG CONTROLLER {self.username}] Input ignored: No peer.")
            # if not self.remote_controller: print(f"[DEBUG CONTROLLER {self.username}] Input ignored: No RemoteController.")
            # if self.main_window and self.main_window.screen_display_widget._view_only: print(f"[DEBUG CONTROLLER {self.username}] Input ignored: View-Only mode.")
            # pass


    def simulate_received_input(self, controller_uid, event_data):
        """Simulates received input event IF permission is granted."""
        # This client is acting as the 'Sharer' receiving input
        # print(f"[DEBUG SHARER {self.username}] Received input event from {controller_uid}: {event_data}")
        if not event_data or not controller_uid:
            print(f"[DEBUG SHARER {self.username}] Ignoring input event: No event data or controller UID.")
            return

        # --- Check Permission ---
        permission_granted = self.control_permissions.get(controller_uid, False)

        if permission_granted:
            # print(f"[DEBUG SHARER {self.username}] Permission GRANTED for {controller_uid}. Simulating input...")
            try:
                # Delegate simulation to utils module
                utils.simulate_input(event_data)
            except Exception as e:
                print(f"[ERROR SHARER {self.username}] Failed to simulate input: {e}")
                # traceback.print_exc() # Optional detailed trace
        else:
             # Permission not granted - Request it via UI thread signal
             # Check if a request for this user is already pending
             if controller_uid in self._permission_requests_pending:
                 # print(f"[DEBUG SHARER {self.username}] Permission request already pending for {controller_uid}. Ignoring new event.")
                 return # Avoid spamming requests

             print(f"[DEBUG SHARER {self.username}] Permission NOT granted for {controller_uid}. Emitting request signal...")
             # Mark request as pending *before* emitting signal
             self._permission_requests_pending.add(controller_uid)
             print(f"[DEBUG SHARER {self.username}] Added {controller_uid} to pending requests: {self._permission_requests_pending}")
             # Emit signal to ask user in UI thread, pass event data for context if needed (currently not used in dialog)
             self.request_permission_signal.emit(controller_uid, event_data)


    @pyqtSlot(str, object)
    def show_permission_dialog_slot(self, controller_uid, pending_event):
        """Shows dialog asking the user for permission. Runs in UI thread."""
        allowed = False # Default to not allowed
        try:
            if not self.main_window:
                print(f"[ERROR] Cannot show permission dialog for {controller_uid}: MainWindow closed.")
                return # Can't ask if window is closed

            # Check if already granted (e.g., race condition, user clicked checkbox manually)
            if self.control_permissions.get(controller_uid):
                print(f"[DEBUG SHARER {self.username}] Permission already granted for {controller_uid} before dialog shown. Skipping.")
                return # Already allowed

            print(f"[UI SLOT {self.username}] Showing permission dialog for {controller_uid}")
            reply = QMessageBox.question(
                self.main_window,
                "Control Request",
                f"User '{controller_uid}' wants to control your desktop. Allow?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No, # Default button
            )

            if reply == QMessageBox.Yes:
                print(f"[UI SLOT {self.username}] Permission GRANTED for {controller_uid} by user.")
                self.control_permissions[controller_uid] = True
                allowed = True
                # Optionally simulate the original pending event now that permission is granted
                # if pending_event:
                #     print(f"[UI SLOT {self.username}] Simulating original pending event: {pending_event}")
                #     self.simulate_received_input(controller_uid, pending_event)
            else:
                print(f"[UI SLOT {self.username}] Permission DENIED for {controller_uid} by user.")
                self.control_permissions[controller_uid] = False
                allowed = False

            # Send permission update back to the controller peer
            if self.websocket_handler and self.websocket_handler.is_connected:
                response_message = {
                    "type": "input_permission_update",
                    "target_uid": controller_uid,
                    "sender_uid": self.username,
                    "allowed": allowed,
                }
                self.websocket_handler.send_message(response_message)
                print(f"[UI SLOT {self.username}] Sent permission update ({allowed}) to {controller_uid}")

            # Update our own UI checkbox state to reflect the decision
            if self.main_window:
                 # Block signals temporarily to avoid feedback loop
                 self.main_window.mouse_permission_checkbox.blockSignals(True)
                 self.main_window.mouse_permission_checkbox.setChecked(allowed)
                 self.main_window.mouse_permission_checkbox.blockSignals(False)
                 self.main_window.update_control_status_display() # Update status bar

        except Exception as e:
            print(f"[UI SLOT {self.username}] Error showing/handling permission dialog: {e}")
            traceback.print_exc()
        finally:
             # Remove from pending requests *after* handling is complete
             if controller_uid in self._permission_requests_pending:
                 self._permission_requests_pending.remove(controller_uid)
                 print(f"[UI SLOT {self.username}] Removed {controller_uid} from pending requests: {self._permission_requests_pending}")


    @pyqtSlot(bool)
    def handle_mouse_permission_change(self, allowed):
        """Handles the toggle of the 'Allow Peer Mouse Control' checkbox in MainWindow."""
        if not self.current_peer_uid:
            print("[DEBUG] Ignoring mouse permission change: No peer connected.")
            # Maybe revert checkbox state?
            if self.main_window:
                 self.main_window.mouse_permission_checkbox.blockSignals(True)
                 self.main_window.mouse_permission_checkbox.setChecked(False) # Revert if no peer
                 self.main_window.mouse_permission_checkbox.blockSignals(False)
            return

        print(f"[DEBUG SHARER {self.username}] UI changed mouse permission for {self.current_peer_uid} to: {allowed}")
        self.control_permissions[self.current_peer_uid] = allowed

        # Send permission update to the peer via WebSocket
        if self.websocket_handler and self.websocket_handler.is_connected:
            message = {
                "type": "input_permission_update",
                "target_uid": self.current_peer_uid,
                "sender_uid": self.username,
                "allowed": allowed,
            }
            self.websocket_handler.send_message(message)
            print(f"[DEBUG] Sent input permission update to {self.current_peer_uid}: {allowed}")

        # Update status bar display
        if self.main_window:
             self.main_window.update_control_status_display()


    # --- Screen Sharing Logic ---
    @pyqtSlot()
    def start_screen_sharing(self):
        """Initiates screen sharing if connected to a peer."""
        if not self.current_peer_uid:
            print("No peer connected. Cannot start sharing.")
            QMessageBox.warning(self.main_window, "Sharing Error", "Please connect to a peer first.")
            # Ensure UI state is correct if attempted without connection
            if self.main_window: self.main_window.set_sharing_state(False)
            return

        if self._is_sharing_screen:
            print("Already sharing screen. Ignoring request.")
            return

        if not self.remote_controller:
             print("[ERROR] RemoteController not initialized. Cannot start sharing.")
             QMessageBox.critical(self.main_window, "Error", "Internal error: Remote controller not ready.")
             return

        print(f"Attempting to start screen sharing to peer: {self.current_peer_uid}")
        try:
            # Update UI immediately to show "sharing" state
            # Role/Status update now handled by _on_screen_share_status_changed signal
            # if self.main_window:
            #     self.main_window.set_sharing_state(True)

            # Start sharing using RemoteController with current settings
            self.remote_controller.start_screen_sharing(
                quality=self._stream_quality,
                scale_factor=self._stream_scale_factor,
                fps=self._stream_fps,
                monitor_index=self._stream_monitor_index
            )
            # Success state (_is_sharing_screen = True) will be set by the signal handler
            # _on_screen_share_status_changed when RemoteController confirms start

        except Exception as e:
            print(f"Error starting screen sharing: {e}")
            traceback.print_exc()
            self._is_sharing_screen = False # Ensure state is reset on error
            if self.main_window:
                self.main_window.set_sharing_state(False) # Reset UI
                self.main_window.show_status_message(f"Error starting sharing: {e}")
                QMessageBox.critical(self.main_window, "Sharing Error", f"Failed to start screen sharing:\n{e}")


    @pyqtSlot()
    def stop_screen_sharing(self, inform_peer=True): # Added inform_peer flag
        """Stops active screen sharing."""
        if not self._is_sharing_screen:
            # print("Not currently sharing screen. Ignoring request.") # Can be noisy
            return

        if not self.remote_controller:
             print("[ERROR] RemoteController not initialized. Cannot stop sharing.")
             # Attempt to reset state anyway
             self._is_sharing_screen = False
             if self.main_window: self.main_window.set_sharing_state(False)
             return

        print("Stopping screen sharing...")
        try:
            # Stop sharing via RemoteController
            self.remote_controller.stop_screen_sharing()
            # Success state (_is_sharing_screen = False) will be set by the signal handler
            # _on_screen_share_status_changed when RemoteController confirms stop

            # TODO: Send a "stopped_sharing" message to peer? (Optional)
            # if inform_peer and self.current_peer_uid and self.websocket_handler and self.websocket_handler.is_connected:
            #     self.websocket_handler.send_message({
            #         "type": "sharing_stopped",
            #         "target_uid": self.current_peer_uid,
            #         "sender_uid": self.username
            #     })

        except Exception as e:
            print(f"Error stopping screen sharing: {e}")
            traceback.print_exc()
            # Still attempt to reset state even if error occurs during stop
            self._is_sharing_screen = False
            if self.main_window:
                self.main_window.set_sharing_state(False)
                self.main_window.show_status_message(f"Error stopping sharing: {e}")


    # --- RemoteController Signal Handlers ---
    @pyqtSlot(bytes)
    def _on_screen_captured(self, image_data):
        """Called when RemoteController captures a frame (when we are sharing)."""
        # This signal confirms a frame was captured. RemoteController handles sending it.
        # We might use this for local preview or stats if needed, but often not required.
        pass

    @pyqtSlot(bool)
    def _on_screen_share_status_changed(self, is_sharing):
        """Called by RemoteController when sharing actually starts or stops."""
        print(f"RemoteController reported sharing status changed to: {is_sharing}")
        self._is_sharing_screen = is_sharing
        if self.main_window:
            self.main_window.set_sharing_state(is_sharing) # Update UI based on actual status
            # Also update the mouse permission checkbox state based on role
            self.main_window.mouse_permission_checkbox.setEnabled(is_sharing)
            if not is_sharing:
                 # Ensure checkbox is unchecked when sharing stops
                 self.main_window.mouse_permission_checkbox.blockSignals(True)
                 self.main_window.mouse_permission_checkbox.setChecked(False)
                 self.main_window.mouse_permission_checkbox.blockSignals(False)
            self.main_window.update_control_status_display() # Update status bar

    @pyqtSlot(str)
    def _on_remote_controller_error(self, error_message):
        """Called when RemoteController encounters an error."""
        print(f"[ERROR] RemoteController error: {error_message}")
        # Stop sharing if an error occurs in the controller
        if self._is_sharing_screen:
             self.stop_screen_sharing(inform_peer=False)
        if self.main_window:
            self.main_window.show_status_message(f"Sharing Error: {error_message}")
            QMessageBox.warning(self.main_window, "Sharing Error", error_message)

    # --- Stream Settings Handlers ---
    @pyqtSlot(int)
    def _handle_quality_changed(self, quality):
        if self._stream_quality != quality:
            print(f"Stream quality setting changed to: {quality}%")
            self._stream_quality = quality
            if self.remote_controller and self._is_sharing_screen:
                self.remote_controller.update_sharing_settings(quality=quality)
            # Update status bar immediately
            if self.main_window:
                self.main_window.update_quality_display(quality)

    @pyqtSlot(int)
    def _handle_scale_changed(self, scale_percent):
        scale_factor = scale_percent / 100.0
        if self._stream_scale_factor != scale_factor:
            print(f"Stream scale setting changed to: {scale_percent}% (Factor: {scale_factor})")
            self._stream_scale_factor = scale_factor
            if self.remote_controller and self._is_sharing_screen:
                self.remote_controller.update_sharing_settings(scale_factor=scale_factor)

    @pyqtSlot(int)
    def _handle_fps_changed(self, fps):
         if self._stream_fps != fps:
            print(f"Stream Max FPS setting changed to: {fps}")
            self._stream_fps = fps
            if self.remote_controller and self._is_sharing_screen:
                self.remote_controller.update_sharing_settings(fps=fps)

    @pyqtSlot(int)
    def _handle_monitor_changed(self, monitor_index):
        """Handles signal when monitor selection changes (1-based index)."""
        if self._stream_monitor_index != monitor_index:
            print(f"Stream monitor setting changed to index: {monitor_index}")
            self._stream_monitor_index = monitor_index
            if self.remote_controller and self._is_sharing_screen:
                self.remote_controller.update_sharing_settings(monitor_index=monitor_index)

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

    # --- Auto Reconnect Slot ---
    @pyqtSlot()
    def _attempt_reconnect(self):
        """Attempts to reconnect to the WebSocket server."""
        self._reconnect_attempts += 1
        print(f"Attempting to reconnect (Attempt {self._reconnect_attempts}/{self.MAX_RECONNECT_ATTEMPTS})")

        # Update UI (show connecting status)
        if self.main_window:
            # self.main_window.update_ws_status(f"Reconnecting ({self._reconnect_attempts}/{self.MAX_RECONNECT_ATTEMPTS})...")
            self.main_window.show_status_message("Attempting WebSocket Reconnect...")
            # Ensure main window shows disconnected state during reconnect attempts
            self.main_window.set_disconnected_state("Attempting Reconnect...")

        # Try initializing the WebSocket again
        self.init_websocket()

        # Check if max attempts reached (do this *after* the attempt)
        if self._reconnect_attempts >= self.MAX_RECONNECT_ATTEMPTS and self._reconnect_timer.isActive():
            print("Max reconnect attempts reached. Giving up.")
            self._reconnect_timer.stop()
            if self.main_window:
                # self.main_window.update_ws_status("Disconnected (Failed)")
                self.main_window.show_status_message("WebSocket Disconnected. Max reconnect attempts reached.")
                # Ensure UI stays disconnected
                self.main_window.set_disconnected_state("WebSocket Reconnection Failed")


    # --- Slot for View Permission Request (Incoming) ---
    @pyqtSlot(str)
    def _ask_view_permission_slot(self, requester_uid):
        """Shows dialog asking user to allow viewing. Runs in UI thread."""
        allowed = False # Default
        try:
            if not self.main_window:
                print("[Error] Cannot ask view permission, main window missing.")
                # Reject automatically if UI isn't there?
                # self._send_view_response(requester_uid, False)
                return

            # Prevent accepting connection if already connected
            if self.current_peer_uid:
                 print(f"Already connected to {self.current_peer_uid}. Rejecting new request from {requester_uid}.")
                 QMessageBox.information(self.main_window, "Busy", f"Already connected to {self.current_peer_uid}. Please disconnect first.")
                 # Send rejection response
                 self._send_view_response(requester_uid, False)
                 return

            print(f"[UI SLOT] Asking user permission for view request from {requester_uid}")
            reply = QMessageBox.question(
                self.main_window,
                "View Request",
                f"User '{requester_uid}' wants to connect and view your screen. Allow?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No, # Default button
            )

            allowed = (reply == QMessageBox.Yes)

            # Send response back to the requester via WebSocketHandler
            self._send_view_response(requester_uid, allowed)

            if allowed:
                print(f"[UI SLOT] User ALLOWED view request from {requester_uid}")
                # Set peer connection state
                self.current_peer_uid = requester_uid
                self.control_permissions.clear() # Clear old permissions
                if self.main_window:
                     self.main_window.set_connected_state(requester_uid)
                     # Role will be set to SHARING when user starts sharing (or automatically?)
                     # For now, set to Idle. User needs to click "Share Screen"
                     self.main_window.set_role(ui.MainWindow.ROLE_IDLE)
                     # Enable the mouse permission checkbox, default to unchecked (peer cannot control yet)
                     self.main_window.mouse_permission_checkbox.setEnabled(True)
                     self.main_window.mouse_permission_checkbox.blockSignals(True)
                     self.main_window.mouse_permission_checkbox.setChecked(False)
                     self.main_window.mouse_permission_checkbox.blockSignals(False)
                     self.main_window.update_control_status_display()
            else:
                print(f"[UI SLOT] User DENIED view request from {requester_uid}")
                # No state change needed, UI remains disconnected

        except Exception as e:
            print(f"[UI SLOT] Error asking view permission: {e}")
            traceback.print_exc()
            # Ensure response is sent even on error? Maybe reject.
            if requester_uid:
                 self._send_view_response(requester_uid, False) # Reject on error

    def _send_view_response(self, target_uid, allowed):
        """Sends the view permission response back to the requester via WebSocket."""
        if self.websocket_handler and self.websocket_handler.is_connected:
            response_message = {
                "type": "view_response",
                "target_uid": target_uid, # The original requester
                "sender_uid": self.username, # Us
                "allowed": allowed,
                "message": ("View request accepted" if allowed else "View request denied"),
            }
            print(f"Sending view_response to {target_uid}: Allowed={allowed}")
            self.websocket_handler.send_message(response_message)
        else:
             print(f"[ERROR] Cannot send view response to {target_uid}: WebSocket disconnected.")


    # --- Application Lifecycle ---
    def run(self):
        """Starts the Qt application event loop."""
        self.app.aboutToQuit.connect(self.cleanup)
        sys.exit(self.app.exec_())

    def cleanup(self):
        """Ensures resources are cleaned up on application exit."""
        print("Cleaning up before exit...")
        # Stop screen sharing if active
        if self._is_sharing_screen:
             self.stop_screen_sharing(inform_peer=False) # Stop locally

        # Stop RemoteController thread/tasks
        if self.remote_controller:
             if hasattr(self.remote_controller, 'stop'):
                 self.remote_controller.stop()

        # Stop WebSocket handler
        if self.websocket_handler:
            self.websocket_handler.stop()

        print("Cleanup finished.")


if __name__ == "__main__":
    import mss # Ensure mss is imported if needed by RemoteController init
    controller = AppController()
    controller.run()