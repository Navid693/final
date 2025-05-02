import sys
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import QObject, pyqtSignal, QTimer, pyqtSlot
from PyQt5.QtGui import QPixmap

# Import local modules
import utils
import ui
import server  # Keep for now, might be removed later
import client  # Keep for now, might be removed later
import httpx  # Import httpx
from websocket_handler import WebSocketHandler  # Import WebSocketHandler
import base64  # For encoding image data
import threading  # For screen sending thread
import time  # For sleep
import traceback  # For detailed error printing
import json  # For JSON handling

# Import necessary modules from Pillow
from PIL import Image
import io


# --- Function to load stylesheet ---
def load_stylesheet(theme_name="dark"):
    """Loads and returns the content of a QSS file based on theme name."""
    filename = f"{theme_name}_styles.qss" if theme_name == "light" else "styles.qss"
    print(f"[DEBUG] Attempting to load stylesheet: {filename}")
    try:
        with open(filename, "r") as f:
            return f.read()
    except FileNotFoundError:
        print(f"[WARNING] Stylesheet file '{filename}' not found.")
        return ""  # Return empty string if file not found
    except Exception as e:
        print(f"[ERROR] Failed to load stylesheet '{filename}': {e}")
        return ""


class AppController(
    QObject
):  # Inherit from QObject for signal/slot usage if needed later
    # Signal to request showing the permission dialog in the GUI thread
    request_permission_signal = pyqtSignal(str, object)  # controller_uid, pending_event
    # --- New Signal for FPS updates ---
    fps_updated_signal = pyqtSignal(float)  # Emits calculated FPS
    # Add signals related to view request
    request_view_permission_signal = pyqtSignal(str)  # Ask user if peer can view

    RECONNECT_DELAY_MS = 5000  # Delay between reconnect attempts (5 seconds)
    MAX_RECONNECT_ATTEMPTS = 5  # Max number of attempts

    def __init__(self):
        super().__init__()  # Initialize the QObject base class
        self.app = QApplication(sys.argv)
        self.current_theme = "dark"  # Start with dark theme
        
        # New attributes for new architecture
        self.login_window = None  # Initialize login_window to None before calling apply_theme
        self.main_window = None  # Placeholder for the post-login window
        self.api_client = None  # Placeholder for API interaction logic
        self.websocket_handler = None  # Placeholder for WebSocket logic
        self.jwt_token = None
        self.backend_base_url = None  # Will be set from LoginWindow
        self.username = None  # Store username after login
        self.current_peer_uid = None  # Store UID of the peer we are connected to
        self.control_permissions = {}  # Store permission status: {peer_uid: bool}
        self._is_sharing_screen = False
        self._screen_sharing_thread = None
        self._screen_sharing_stopevent = threading.Event()
        
        # --- Apply Stylesheet --- (moved after initializing login_window attribute)
        self.apply_theme()
        
        # Default streaming settings (can be made configurable later)
        self._stream_quality = ui.MainWindow.DEFAULT_QUALITY
        self._stream_scale_factor = ui.MainWindow.DEFAULT_SCALE / 100.0
        self._stream_fps = ui.MainWindow.DEFAULT_FPS
        self._stream_monitor_index = (
            ui.MainWindow.DEFAULT_MONITOR_INDEX
        )  # Add monitor index

        # --- Attributes for FPS calculation ---
        self._received_frame_counter = 0
        self._fps_calc_start_time = time.perf_counter()
        self._last_status_message = "Initializing..."  # Store last base status

        # --- Auto-Reconnect Attributes ---
        self._reconnect_attempts = 0
        self._reconnect_timer = QTimer()
        self._reconnect_timer.timeout.connect(self._attempt_reconnect)

        # Remove old window/instance attributes
        # self.initial_window = None
        # self.host_window = None
        # self.client_window = None
        # self.server_instance = None
        # self.client_instance = None

        self.show_login_window()  # Start with login

        # Connect the new signal to its slot
        self.request_permission_signal.connect(self.show_permission_dialog_slot)
        # Connect the new FPS signal to the MainWindow slot
        self.fps_updated_signal.connect(
            self._handle_fps_update_to_ui
        )  # Connect to intermediate handler
        # Connect the new view request permission signal
        self.request_view_permission_signal.connect(self._ask_view_permission_slot)

        self._permission_requests_pending = set()  # Track pending requests {peer_uid}

    def apply_theme(self):
        """Loads and applies the stylesheet for the current theme."""
        stylesheet = load_stylesheet(self.current_theme)
        if stylesheet:
            self.app.setStyleSheet(stylesheet)
            print(f"[DEBUG] Applied {self.current_theme} theme stylesheet.")
        else:
            self.app.setStyleSheet("")  # Clear stylesheet if loading fails
            print(
                f"[WARNING] Failed to load {self.current_theme} stylesheet, cleared styles."
            )

        # Update UI elements that need explicit theme changes (like icons)
        if self.login_window:
            self.login_window._update_theme_icon(self.current_theme)
        # Add similar checks for main_window if it gets a theme toggle
        # if self.main_window:
        #     self.main_window._update_theme_icon(self.current_theme)

    def show_login_window(self):
        """Displays the login window."""
        if self.login_window is None:
            self.login_window = ui.LoginWindow()
            self.login_window.login_attempt_signal.connect(self.handle_login_attempt)
            # Connect the theme toggle signal
            self.login_window.toggle_theme_signal.connect(self.toggle_theme)
        self.login_window._update_theme_icon(
            self.current_theme
        )  # Ensure icon is correct on show
        self.login_window.show()

    def handle_login_attempt(self, backend_url, username, password):
        """Handles the login attempt signal from LoginWindow."""
        print(f"Attempting login to {backend_url} for user {username}")
        self.backend_base_url = backend_url
        self.username = username  # Store username
        self.login_window.set_logging_in()  # Update UI to show pending state

        # --- Simulate API Call (Replace with actual httpx call) ---
        # In a real scenario, you would use httpx here:
        # try:
        #     async with httpx.AsyncClient() as client:
        #         response = await client.post(f"{self.backend_base_url}/login", json={'username': username, 'password': password})
        #         response.raise_for_status() # Raise exception for 4xx/5xx errors
        #         data = response.json()
        #         self.jwt_token = data.get('access_token') # Assuming token is returned this way
        #         if not self.jwt_token:
        #              raise ValueError("Token not found in response")
        #         print("Login successful!")
        #         self.on_login_success()
        # except httpx.HTTPStatusError as e:
        #     print(f"Login failed: {e.response.status_code} - {e.response.text}")
        #     self.login_window.show_error(f"Login Failed: {e.response.json().get('detail', e.response.status_code)}")
        # except httpx.RequestError as e:
        #     print(f"Login failed: Network error - {e}")
        #     self.login_window.show_error(f"Network Error: Cannot reach {self.backend_base_url}")
        # except Exception as e:
        #     print(f"Login failed: {e}")
        #     self.login_window.show_error(f"Login failed: {e}")

        # ** TEMPORARY: Simulate successful login **
        import time

        time.sleep(1)  # Simulate network delay
        print("Login successful (Simulated)!")
        self.jwt_token = "fake_jwt_token_for_testing"
        self.on_login_success()
        # ** END TEMPORARY **

        # ** TEMPORARY: Simulate failed login (Uncomment to test) **
        # import time
        # time.sleep(1)
        # print("Login failed (Simulated)!")
        # self.login_window.show_error("Invalid credentials (Simulated)")
        # ** END TEMPORARY **

    def on_login_success(self):
        """Called after successful login."""
        if self.login_window:
            self.login_window.close()
        self.login_window = None

        # Show the main application window
        print(
            f"Proceeding to main app for user {self.username} with token: {self.jwt_token}"
        )
        self.show_main_window()
        # QMessageBox.information(None, "Login Success", "Login Successful! Main window placeholder.")
        # self.app.quit() # Don't quit anymore

        # --- Initialize WebSocket Handler after showing main window ---
        self.init_websocket()

    def init_websocket(self):
        """Initializes and attempts to connect the WebSocket handler."""
        if not self.backend_base_url or not self.jwt_token:
            print("Cannot initialize WebSocket: Missing Backend URL or Token.")
            QMessageBox.critical(
                self.main_window,
                "Error",
                "Cannot initialize connection: Missing Backend URL or Token.",
            )
            return

        if self.websocket_handler and self.websocket_handler.is_connected():
            print("WebSocket already connected.")
            # If called during reconnect, stop timer
            if self._reconnect_timer.isActive():
                print("Stopping reconnect timer as connection established.")
                self._reconnect_timer.stop()
            self._reconnect_attempts = 0  # Reset attempts on successful manual init
            return

        print(
            f"Initializing WebSocket Handler (Attempt: {self._reconnect_attempts + 1})..."
        )
        # Stop existing timer if starting a new connection attempt manually
        if self._reconnect_attempts == 0 and self._reconnect_timer.isActive():
            self._reconnect_timer.stop()

        self.websocket_handler = WebSocketHandler(self.backend_base_url, self.jwt_token)
        self.websocket_handler.connected_signal.connect(self.on_websocket_connected)
        self.websocket_handler.disconnected_signal.connect(
            self.on_websocket_disconnected
        )
        self.websocket_handler.error_signal.connect(self.on_websocket_error)
        self.websocket_handler.message_received_signal.connect(
            self.handle_websocket_message
        )
        self.websocket_handler.binary_message_received_signal.connect(
            self.handle_websocket_binary_message
        )
        if self.main_window:  # Connect status only if window exists
            # Connect the handler's status signal to the main window's message display
            self.websocket_handler.status_update_signal.connect(
                self.main_window.show_status_message
            )

        # Attempt to connect
        print(f"Attempting WebSocket connection to {self.backend_base_url}...")
        # Set UI status to connecting before starting the connection attempt
        if self.main_window:
            self.main_window.update_ws_status("Connecting...")
            self.main_window.show_status_message("Connecting to WebSocket...")
            
        self.websocket_handler.connect_ws()  # connect_ws starts the thread

    def show_main_window(self):
        """Creates and shows the main application window."""
        if self.main_window is None:
            print("[DEBUG] Creating MainWindow...")
            self.main_window = ui.MainWindow(self.username, self.current_theme)  # Pass username and theme

            # Ensure screen display widget is in view-only mode by default
            if (
                hasattr(self.main_window, "screen_display_widget")
                and self.main_window.screen_display_widget
            ):
                print(
                    "[DEBUG] Setting screen display widget to view-only mode by default"
                )
                self.main_window.screen_display_widget.view_only = True
                # Add more direct property access for debugging
                print(
                    f"[DEBUG] Screen display view_only property set to: {self.main_window.screen_display_widget.view_only}"
                )

                # Explicitly call any methods needed to ensure view-only state
                if hasattr(self.main_window.screen_display_widget, "set_view_only"):
                    self.main_window.screen_display_widget.set_view_only(True)
                    print(
                        "[DEBUG] Also called set_view_only(True) method to ensure view-only mode"
                    )
            else:
                print(
                    "[WARN] screen_display_widget not available yet during main window creation"
                )

            # Connect signals from MainWindow to controller methods
            print("[DEBUG] Connecting MainWindow signals...")
            self.main_window.disconnect_signal.connect(self.handle_disconnect)
            print("[DEBUG]  - disconnect_signal connected.")
            self.main_window.send_chat_message_signal.connect(self.handle_send_chat)
            print("[DEBUG]  - send_chat_message_signal connected.")
            self.main_window.logout_signal.connect(self.handle_logout)
            print("[DEBUG]  - logout_signal connected.")
            
            # Connect theme toggle signal
            self.main_window.toggle_theme_signal.connect(self.toggle_theme)
            print("[DEBUG]  - toggle_theme_signal connected.")
            
            # --- TEMPORARY: Connect Sharing Signals ---
            self.main_window.start_sharing_signal.connect(self.start_screen_sharing)
            self.main_window.stop_sharing_signal.connect(self.stop_screen_sharing)
            print("[DEBUG]  - sharing signals connected.")
            # --- END TEMPORARY ---
            # --- Connect screen input signals --- Use correct attribute name
            # Ensure screen_display_widget exists before connecting
            if hasattr(self.main_window, "screen_display_widget"):
                self.main_window.screen_display_widget.mouse_event_signal.connect(
                    self.handle_send_input_event
                )
                print("[DEBUG]  - screen_display_widget.mouse_event_signal connected.")
                self.main_window.screen_display_widget.key_event_signal.connect(
                    self.handle_send_input_event
                )
                print("[DEBUG]  - screen_display_widget.key_event_signal connected.")
            else:
                print(
                    "[WARN] screen_display_widget not found on main_window during signal connection."
                )
            # --- Connect Stream Settings Signals --- Correctly connect
            self.main_window.quality_changed_signal.connect(
                self._handle_quality_changed
            )
            print("[DEBUG]  - quality_changed_signal connected.")
            self.main_window.scale_changed_signal.connect(self._handle_scale_changed)
            print("[DEBUG]  - scale_changed_signal connected.")
            self.main_window.fps_changed_signal.connect(self._handle_fps_changed)
            print("[DEBUG]  - fps_changed_signal connected.")
            # --- Connect Monitor Signal ---
            self.main_window.monitor_changed_signal.connect(
                self._handle_monitor_changed
            )
            print("[DEBUG]  - monitor_changed_signal connected.")
            # Connect RENAMED signal from MainWindow
            self.main_window.request_view_signal.connect(
                self.handle_request_view
            )  # Renamed handler
            print("[DEBUG]  - request_view_signal connected.")  # Update log message

            # Note: Connecting signals FROM websocket handler is now done in init_websocket
            print("[DEBUG] MainWindow signals connected.")

        self.main_window.show()
        print("[DEBUG] MainWindow shown.")

        # Connect the AppController's FPS signal AFTER main_window is created
        # Note: We connected it in __init__ now, assuming main_window is created before signal is needed.
        # If timing issues arise, move connection here.
        # self.fps_updated_signal.connect(self.main_window.update_fps_display)

    # --- WebSocket Signal Handlers ---
    def on_websocket_connected(self):
        """Called when WebSocket connection is established."""
        print("WebSocket connected successfully!")
        # If called during reconnect, stop timer
        if self._reconnect_timer.isActive():
            print("Stopping reconnect timer as connection established.")
            self._reconnect_timer.stop()
        
        self._reconnect_attempts = 0  # Reset attempts on successful connection
        
        # Update connection status in UI (Only the status bar)
        if self.main_window:
            # Update the main status bar, but don't imply peer connection
            self.main_window.update_ws_status("Connected")
            self.main_window.show_status_message("WebSocket Connected. Ready.")
            
    def on_websocket_disconnected(self, reason):
        """Called when WebSocket connection is lost."""
        print(f"WebSocket disconnected: {reason}")
        
        # Start reconnect timer if not already trying to reconnect
        if (not self._reconnect_timer.isActive() and 
            self._reconnect_attempts < self.MAX_RECONNECT_ATTEMPTS):
            print(f"Starting reconnect timer. Attempt {self._reconnect_attempts + 1}/{self.MAX_RECONNECT_ATTEMPTS}")
            self._reconnect_timer.start(self.RECONNECT_DELAY_MS)
            
            # Update UI to show connecting status (Only the status bar)
            if self.main_window:
                self.main_window.update_ws_status("Reconnecting...")
                self.main_window.show_status_message(f"WebSocket Disconnected: {reason}. Retrying...")
        else:
            # If we've reached max attempts, show disconnected (Only the status bar)
            if self.main_window:
                self.main_window.update_ws_status("Disconnected (Failed)")
                self.main_window.show_status_message("WebSocket Disconnected. Reconnection failed.")
                
        # Disconnect from peer if connected
        if self.current_peer_uid:
            self.handle_disconnect() # This will update the peer indicator to disconnected
            
    def on_websocket_error(self, error_message):
        """Called when a WebSocket error occurs."""
        print(f"WebSocket error: {error_message}")
        
        # Update connection status in UI (Only the status bar)
        if self.main_window:
            self.main_window.update_ws_status("Error")
            self.main_window.show_status_message(f"WebSocket Error: {error_message}")
            
    def handle_websocket_message(self, message):
        """Handle incoming WebSocket messages"""
        print(
            f"[DEBUG Client {self.username}] Received WebSocket message: {json.dumps(message)[:100]}{'...' if len(json.dumps(message)) > 100 else ''}"
        )
        try:
            message_type = message.get("type")

            # Handling various message types
            if message_type == "connection_status":
                self.handle_connection_status(message)

            elif message_type == "login_response":
                self.handle_login_response(message)

            elif message_type == "input_permission_update":
                # Handle permission update from peer
                sender_uid = message.get("sender_uid")
                allowed = message.get("allowed", False)

                if not sender_uid:
                    print("[ERROR] input_permission_update message missing sender_uid")
                    return

                print(
                    f"[DEBUG] Received input permission update from {sender_uid}: {allowed}"
                )

                # Update internal permissions tracking
                self.control_permissions[sender_uid] = allowed

                # Update UI if applicable
                if hasattr(self, "main_window") and self.main_window:
                    if sender_uid == self.current_peer_uid:
                        # Update the mouse permission checkbox without triggering its signal
                        self.main_window.mouse_permission_checkbox.blockSignals(True)
                        self.main_window.mouse_permission_checkbox.setChecked(allowed)
                        self.main_window.mouse_permission_checkbox.blockSignals(False)

                # Show notification to user
                status = "allowed" if allowed else "denied"
                QMessageBox.information(
                    self.main_window,
                    "Input Permission Update",
                    f"User '{sender_uid}' has {status} mouse control.",
                )

            elif message_type == "screen_frame":
                if hasattr(self, "main_window") and self.main_window:
                    if (
                        hasattr(self.main_window, "screen_display_widget")
                        and self.main_window.screen_display_widget
                    ):
                        # Check if we should have mouse control permissions for this peer
                        sender_uid = message.get("sender_uid")
                        has_permission = False

                        if sender_uid:
                            has_permission = self.control_permissions.get(
                                sender_uid, False
                            )
                            print(
                                f"[DEBUG] Screen frame from {sender_uid}, mouse permission: {has_permission}"
                            )

                        # Update view-only mode based on permissions
                        current_view_only = (
                            self.main_window.screen_display_widget.view_only
                        )
                        if current_view_only == has_permission:  # These are opposites
                            print(f"[DEBUG] Setting view_only to {not has_permission}")
                            self.main_window.screen_display_widget.set_view_only(
                                not has_permission
                            )

                            # Update UI checkbox to match (if it exists) without triggering signals
                            if hasattr(self.main_window, "mouse_permission_checkbox"):
                                self.main_window.mouse_permission_checkbox.blockSignals(
                                    True
                                )
                                self.main_window.mouse_permission_checkbox.setChecked(
                                    has_permission
                                )
                                self.main_window.mouse_permission_checkbox.blockSignals(
                                    False
                                )

                        # Process the screen frame
                        self.handle_screen_frame(message)
                    else:
                        print("[WARNING] screen_display_widget not available")
                else:
                    print("[WARNING] main_window not available for screen_frame")

            elif message_type == "request_view":
                # New handler for incoming view requests
                sender_uid = message.get("sender_uid")
                if not sender_uid:
                    print("[ERROR] request_view message missing sender_uid")
                    return

                print(f"[DEBUG] Received view request from {sender_uid}")

                # Ask user for permission
                if (
                    QMessageBox.question(
                        self.main_window,
                        "View Request",
                        f"User '{sender_uid}' is requesting to view your screen. Allow?",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.No,
                    )
                    == QMessageBox.Yes
                ):
                    # User allowed the view request
                    self.current_peer_uid = sender_uid
                    print(f"[DEBUG] Allowing view request from {sender_uid}")

                    # Send permission response
                    response = {
                        "type": "view_response",
                        "allowed": True,
                        "target_uid": sender_uid,
                        "sender_uid": self.username,
                    }
                    self.websocket_handler.send_message(response)

                    # Start sharing automatically
                    if self.main_window:
                        # Update UI
                        self.main_window.update_status(
                            f"Sharing screen with {sender_uid}"
                        )
                        # Start sharing
                        self.start_screen_sharing()
                else:
                    # User denied the view request
                    print(f"[DEBUG] Denying view request from {sender_uid}")
                    # Send denial response
                    response = {
                        "type": "view_response",
                        "allowed": False,
                        "target_uid": sender_uid,
                        "sender_uid": self.username,
                    }
                    self.websocket_handler.send_message(response)

            elif message_type == "view_response":
                # Handle response to our view request
                allowed = message.get("allowed", False)
                sender_uid = message.get("sender_uid")
                if not sender_uid:
                    print("[ERROR] view_response message missing sender_uid")
                    return

                if allowed:
                    print(f"[DEBUG] View request accepted by {sender_uid}")
                    # Set peer uid and update UI
                    self.current_peer_uid = sender_uid

                    if self.main_window:
                        self._last_status_message = f"Connected to {sender_uid}"
                        self.main_window.update_status(self._last_status_message)
                        self.main_window.request_view_button.setEnabled(True)
                        self.main_window.set_connected_state(True)

                        # Reset FPS counter for new connection
                        self._reset_fps_counter()
                else:
                    print(f"[DEBUG] View request denied by {sender_uid}")
                    # Reset the peer uid and update UI
                    self.current_peer_uid = None

                    if self.main_window:
                        self._last_status_message = (
                            f"{sender_uid} denied your view request"
                        )
                        self.main_window.update_status(self._last_status_message)
                        self.main_window.request_view_button.setEnabled(True)
                        self.main_window.set_connected_state(False)

                        # Inform the user
                        QMessageBox.information(
                            self.main_window,
                            "View Request Denied",
                            f"User '{sender_uid}' denied your request to view their screen.",
                        )

            elif message_type == "request_share_permission":
                # Handle incoming share permission requests
                requester_uid = message.get("sender_uid")
                if not requester_uid:
                    print("[ERROR] request_share_permission message missing sender_uid")
                    return

                print(
                    f"[DEBUG] Received screen sharing permission request from {requester_uid}"
                )

                # Ask user if they want to allow the peer to share their screen
                if (
                    QMessageBox.question(
                        self.main_window,
                        "Share Permission Request",
                        f"User '{requester_uid}' wants to share their screen with you. Allow?",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.Yes,
                    )
                    == QMessageBox.Yes
                ):
                    # User allowed screen sharing
                    print(f"[DEBUG] Allowing screen sharing from {requester_uid}")

                    # Send permission response
                    response = {
                        "type": "share_permission_response",
                        "allowed": True,
                        "target_uid": requester_uid,
                        "sender_uid": self.username,
                        "message": "Share permission granted",
                    }
                    self.websocket_handler.send_message(response)
                else:
                    # User denied screen sharing
                    print(f"[DEBUG] Denying screen sharing from {requester_uid}")

                    # Send denial response
                    response = {
                        "type": "share_permission_response",
                        "allowed": False,
                        "target_uid": requester_uid,
                        "sender_uid": self.username,
                        "message": "Share permission denied",
                    }
                    self.websocket_handler.send_message(response)

            elif message_type == "share_permission_response":
                # Handle responses to our share permission requests
                allowed = message.get("allowed", False)
                sender_uid = message.get("sender_uid")

                if not sender_uid:
                    print(
                        "[ERROR] share_permission_response message missing sender_uid"
                    )
                    return

                if allowed:
                    print(f"[DEBUG] Screen sharing permission granted by {sender_uid}")
                    # Start sharing after permission granted
                    self._start_sharing_after_permission()
                else:
                    print(f"[DEBUG] Screen sharing permission denied by {sender_uid}")
                    # Inform the user
                    QMessageBox.information(
                        self.main_window,
                        "Share Permission Denied",
                        f"User '{sender_uid}' denied your request to share your screen.",
                    )

                    # Reset UI state
                    if self.main_window:
                        self.main_window.start_sharing_button.setEnabled(True)
                        self.main_window.stop_sharing_button.setEnabled(False)
                        self.set_sharing_state(False)

            elif message_type == "input_event":
                self.handle_input_event(message)

            elif message_type == "error":
                error_message = message.get("message", "Unknown error")
                print(f"[ERROR] Received error message: {error_message}")
                if self.main_window:
                    self.main_window.update_status(f"Error: {error_message}")

            elif message_type == "peer_disconnected":
                if self.main_window:
                    self.main_window.update_status("Peer disconnected")
                    self.main_window.set_connected_state(False)

                    # Disable input when peer disconnects
                    if (
                        hasattr(self.main_window, "screen_display_widget")
                        and self.main_window.screen_display_widget
                    ):
                        print("[DEBUG] Disabling mouse input as peer disconnected")
                        self.main_window.screen_display_widget.view_only = True

                    self.current_peer_uid = None

            else:
                print(f"[WARNING] Unknown message type: {message_type}")

        except Exception as e:
            print(f"[ERROR] Error handling WebSocket message: {str(e)}")
            traceback.print_exc()

    def handle_websocket_binary_message(self, data_bytes):
        """Handles BINARY messages (screen frames + cursor) received from the WebSocket."""
        if not data_bytes or len(data_bytes) <= 8:
            # Ignore empty messages or messages too small to contain image + cursor
            # print("[WARN] Received invalid binary message (too small or empty).")
            return

        # --- Direct processing of image + cursor data ---
        # Assumes the format is: [JPEG Bytes] + [Cursor X (4 bytes)] + [Cursor Y (4 bytes)]
        # No message type byte is expected here based on the current sending loop.

        if (
            self.main_window
            and hasattr(self.main_window, "update_remote_screen")
            and hasattr(self.main_window, "update_remote_cursor")
        ):
            # --- Set Role to Viewing if Idle --- 
            # Do this *before* processing the frame, only once when starting to view
            if self.main_window._current_role == ui.MainWindow.ROLE_IDLE:
                print("[DEBUG] Received first frame, setting role to VIEWING")
                self.main_window.set_viewing_state(True)
            
            # --- Increment frame counter ---
            self._received_frame_counter += 1

            try:
                # Separate image data and cursor data
                image_data = data_bytes[:-8]
                cursor_x = int.from_bytes(
                    data_bytes[-8:-4], "big", signed=False
                )  # Use signed=False if coords are always positive
                cursor_y = int.from_bytes(data_bytes[-4:], "big", signed=False)

                # print(f"Received frame: {len(image_data)} bytes, Cursor: ({cursor_x}, {cursor_y})") # Debug

                # Update the UI
                self.main_window.update_remote_screen(
                    image_data
                )  # Pass the extracted image bytes
                self.main_window.update_remote_cursor(cursor_x, cursor_y)
            except OverflowError as oe:
                print(
                    f"Error unpacking cursor coordinates: {oe}. Data length: {len(data_bytes)}"
                )
            except Exception as e:
                print(f"Error processing received binary frame data: {e}")
                # Don't count frames with errors?
                # self._received_frame_counter -= 1

            # --- Calculate and emit FPS periodically ---
            current_time = time.perf_counter()
            time_elapsed = current_time - self._fps_calc_start_time
            if time_elapsed >= 1.0:  # Calculate every second
                calculated_fps = self._received_frame_counter / time_elapsed
                self.fps_updated_signal.emit(calculated_fps)
                # Reset counter and timer
                self._received_frame_counter = 0
                self._fps_calc_start_time = current_time
        # else:
        # print("[WARN] MainWindow not ready to display received binary frame.")

    # --- MainWindow Signal Handlers ---
    def handle_connect_to_peer(self, target_uid):
        """Handles connection to another peer."""
        if not target_uid:
            print("Empty target UID provided. Cannot connect.")
            QMessageBox.warning(
                self.main_window, "Connection Error", "Please enter a valid peer username."
            )
            return
        
        if not self.websocket_handler or not self.websocket_handler.is_connected():
            print("Cannot connect to peer: WebSocket not connected.")
            QMessageBox.warning(
                self.main_window, "Connection Error", "WebSocket connection is not established."
            )
            if self.main_window:
                self.main_window.set_connection_status(ui.MainWindow.CONNECTION_STATUS_DISCONNECTED)
            return
        
        print(f"Attempting to connect to peer: {target_uid}")
        
        # Disconnect from current peer first if there is one
        if self.current_peer_uid:
            print(f"Already connected to {self.current_peer_uid}. Disconnecting first.")
            self.handle_disconnect()
        
        try:
            # Store the target UID and update UI
            self.current_peer_uid = target_uid
            
            # Send 'connect' message to server
            self.websocket_handler.send_message(
                {
                    "type": "connect",
                    "target_uid": target_uid,
                }
            )
            
            # Update UI
            if self.main_window:
                self.main_window.set_connected_state(target_uid)
                
        except Exception as e:
            print(f"Error connecting to peer: {e}")
            self.current_peer_uid = None
            if self.main_window:
                self.main_window.set_disconnected_state(f"Connection failed: {e}")
                
    def handle_disconnect(self):
        """Handles disconnection from current peer."""
        if not self.current_peer_uid:
            print("Not currently connected to a peer.")
            return
            
        print(f"Disconnecting from peer: {self.current_peer_uid}")
        
        try:
            # Stop sharing if active
            if self._is_sharing_screen:
                self.stop_screen_sharing()
                
            # Send disconnect message
            if self.websocket_handler and self.websocket_handler.is_connected():
                self.websocket_handler.send_message(
                    {
                        "type": "disconnect",
                        "target_uid": self.current_peer_uid,
                    }
                )
            
            # Update state and UI
            previous_peer = self.current_peer_uid
            self.current_peer_uid = None
            
            if self.main_window:
                self.main_window.set_disconnected_state(f"Disconnected from {previous_peer}")
                self.main_window.set_viewing_state(False)  # Ensure viewing state is reset
            
        except Exception as e:
            print(f"Error during disconnect: {e}")
            # Still reset state even if error occurs
            self.current_peer_uid = None
            if self.main_window:
                self.main_window.set_disconnected_state(f"Error during disconnect: {e}")
                
    def handle_send_chat(self, message):
        print(f"Controller: Request to send chat message: {message}")
        if self.websocket_handler and self.websocket_handler.is_connected():
            chat_message = {"type": "chat", "message": message}
            self.websocket_handler.send_message(chat_message)
        else:
            if self.main_window:
                self.main_window.append_chat_message(
                    "<i>Error: Not connected. Cannot send message.</i>"
                )

    def handle_logout(self):
        """Handles logout request."""
        print("Controller: Handling logout.")
        # 1. Disconnect WebSocket if connected
        if self.websocket_handler:
            self.websocket_handler.stop()
            self.websocket_handler = None

        # 2. Clear screen and Close Main Window if open
        if self.main_window:
            # Clear the screen display before closing
            self.main_window.screen_display_widget.pixmap = QPixmap()
            self.main_window.screen_display_widget.update()
            self.main_window.close()
            self.main_window = None

        # 3. Clear user data
        self.jwt_token = None
        self.username = None
        self.current_peer_uid = None
        self.control_permissions = {}  # Clear permissions on logout
        # Reset backend_base_url to prevent "Missing Backend URL" error
        self.backend_base_url = None

        # 4. Show Login Window again
        self.show_login_window()
        self._reset_fps_counter()

    # --- Input Handling ---
    def handle_send_input_event(self, event_data):
        # This client is acting as the 'Controller'
        if (
            self.websocket_handler
            and self.websocket_handler.is_connected()
            and self.current_peer_uid
        ):
            message = {
                "type": "input_event",
                "sender_uid": self.username,
                "event": event_data,
            }
            print(
                f"[DEBUG CONTROLLER {self.username}] Sending input: {event_data}"
            )  # LOG: Log sent event
            self.websocket_handler.send_message(message)
        else:
            # LOG: Log why not sent
            if not self.current_peer_uid:
                print(
                    f"[DEBUG CONTROLLER {self.username}] Input event ignored: Not connected to a peer."
                )
            elif (
                not self.websocket_handler or not self.websocket_handler.is_connected()
            ):
                print(
                    f"[DEBUG CONTROLLER {self.username}] Input event ignored: WebSocket NOT connected."
                )

    def simulate_received_input(self, controller_uid, event_data):
        print(
            f"[DEBUG SHARER {self.username}] Received input event from {controller_uid}: {event_data}"
        )  # LOG: Log received event
        if not event_data or not controller_uid:
            print(
                f"[DEBUG SHARER {self.username}] Ignoring input event: No event data or controller UID."
            )
            return

        # --- Check Permission ---
        permission_granted = self.control_permissions.get(controller_uid)
        # ... LOG: Log status ...

        if not permission_granted:
            # --- Check if request is already pending ---
            if controller_uid in self._permission_requests_pending:
                print(
                    f"[DEBUG SHARER {self.username}] Permission request already pending for {controller_uid}. Ignoring new event."
                )  # LOG
                return  # Don't spam requests

            print(
                f"[DEBUG SHARER {self.username}] Permission NOT granted for {controller_uid}. Emitting request signal..."
            )
            # --- Mark request as pending BEFORE emitting ---
            self._permission_requests_pending.add(controller_uid)
            print(
                f"[DEBUG SHARER {self.username}] Added {controller_uid} to pending requests: {self._permission_requests_pending}"
            )  # LOG
            self.request_permission_signal.emit(controller_uid, event_data)
            return

        # --- Permission Granted ---
        # ... LOG: Log grant ...
        # ... LOG: Log simulation attempt ...
        try:
            utils.simulate_input(event_data)
            # ... LOG: Log success ...
        except Exception as e:
            # ... LOG: Log error ...
            pass  # Add a pass statement here to fix the indentation error

    @pyqtSlot(str, object)
    def show_permission_dialog_slot(self, controller_uid, pending_event):
        """Shows a dialog asking the user for permission to allow remote control."""
        if not self.main_window:
            # --- Remove from pending if window closed ---
            if controller_uid in self._permission_requests_pending:
                self._permission_requests_pending.remove(controller_uid)
            # ... Log error ...
            return

        # Check if already granted (race condition)
        if self.control_permissions.get(controller_uid):
            # --- Remove from pending if already granted ---
            if controller_uid in self._permission_requests_pending:
                self._permission_requests_pending.remove(controller_uid)
            # ... Log skip ...
            return

        try:
            # ... LOG: Log showing dialog ...
            reply = QMessageBox.question(
                self.main_window,
                "Control Request",
                f"User '{controller_uid}' wants to control your desktop. Allow?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            # ... LOG: Log user response ...

            if reply == QMessageBox.Yes:
                print(
                    f"[UI SLOT {self.username}] Permission GRANTED for {controller_uid} by user."
                )
                self.control_permissions[controller_uid] = True
            else:
                print(
                    f"[UI SLOT {self.username}] Permission DENIED for {controller_uid} by user."
                )
                self.control_permissions[controller_uid] = False
        except Exception as e:
            print(
                f"[UI SLOT {self.username}] Error showing/handling permission dialog: {e}"
            )
            traceback.print_exc()
        finally:
            # Correctly indented block:
            if controller_uid in self._permission_requests_pending:
                self._permission_requests_pending.remove(controller_uid)
                print(
                    f"[UI SLOT {self.username}] Removed {controller_uid} from pending requests: {self._permission_requests_pending}"
                )  # LOG

    def run(self):
        """Starts the Qt application event loop."""
        self.app.aboutToQuit.connect(self.cleanup)
        sys.exit(self.app.exec_())

    def cleanup(self):
        """Ensures resources are cleaned up on application exit."""
        print("Cleaning up before exit...")
        self.stop_screen_sharing()  # Ensure sharing stops on exit
        # Stop WebSocket handler if running
        if self.websocket_handler:
            self.websocket_handler.stop()

    # --- Screen Sharing Logic ---
    def start_screen_sharing(self):
        """Initiates screen sharing if permissions allow."""
        if not self.current_peer_uid:
            print("No peer connected. Cannot start sharing.")
            QMessageBox.warning(
                self.main_window, "Sharing Error", "No peer connected. Please connect to a peer first."
            )
            return
            
        if self._is_sharing_screen:
            print("Already sharing screen. Ignoring request.")
            return
            
        print(f"Starting screen sharing to peer: {self.current_peer_uid}")
        
        try:
            # Set sharing state in UI
            if self.main_window:
                self.main_window.set_sharing_state(True)
                
            # Start sharing thread
            self._screen_sharing_stopevent.clear()
            self.start_screen_sharing_thread()
            
            # Update state
            self._is_sharing_screen = True
            
        except Exception as e:
            print(f"Error starting screen sharing: {e}")
            self._is_sharing_screen = False
            if self.main_window:
                self.main_window.set_sharing_state(False)
                self.main_window.show_status_message(f"Error starting screen sharing: {e}")
                
    def start_screen_sharing_thread(self):
        """Actually start the screen sharing thread after permission is granted"""
        print(f"[DEBUG Client {self.username}] Starting screen sharing thread")

        # Set state flags
        self._stop_sharing_flag = False
        self._is_sharing_screen = True

        # Create and start the sharing thread
        self._sharing_thread = threading.Thread(
            target=self._screen_sharing_loop, daemon=True
        )
        self._sharing_thread.start()

        # Update UI
        if self.main_window:
            self.main_window.update_status(
                f"Sharing screen with {self.current_peer_uid}"
            )
            # UI buttons should already be updated

    def _start_sharing_after_permission(self):
        """Actually starts the screen sharing after permission is granted."""
        print(
            f"Starting screen sharing (Target: Backend/Peer {self.current_peer_uid})..."
        )
        self._is_sharing_screen = True
        self._screen_sharing_stopevent.clear()
        self._screen_sharing_thread = threading.Thread(
            target=self._screen_sharing_loop, daemon=True
        )
        self._screen_sharing_thread.start()
        self.set_sharing_state(True)  # Use the new method
        # --- Send status message to peer ---
        if self.websocket_handler and self.websocket_handler.is_connected():
            print(f"[DEBUG {self.username}] Sending sharing_started notice.")
            status_msg = {"type": "sharing_started", "sender_uid": self.username}
            self.websocket_handler.send_message(status_msg)
        # --- End Send status message ---
        self._last_status_message = "Sharing screen..."
        if self.main_window:
            self.main_window.update_status(self._last_status_message)

    def stop_screen_sharing(self):
        """Stops active screen sharing."""
        if not self._is_sharing_screen:
            print("Not currently sharing screen. Ignoring request.")
            return
            
        print("Stopping screen sharing")
        
        try:
            # Signal the thread to stop
            self._screen_sharing_stopevent.set()
            
            # Wait for thread to finish if it exists
            if self._screen_sharing_thread and self._screen_sharing_thread.is_alive():
                self._screen_sharing_thread.join(2.0)  # Wait up to 2 seconds
                if self._screen_sharing_thread.is_alive():
                    print("Warning: Screen sharing thread did not terminate gracefully.")
                    
            # Clean up
            self._screen_sharing_thread = None
            self._is_sharing_screen = False
            
            # Update UI
            if self.main_window:
                self.main_window.set_sharing_state(False)
                
        except Exception as e:
            print(f"Error stopping screen sharing: {e}")
            # Still reset state even if error occurs
            self._is_sharing_screen = False
            if self.main_window:
                self.main_window.set_sharing_state(False)
                self.main_window.show_status_message(f"Error stopping screen sharing: {e}")

    def _screen_sharing_loop(self):
        print(
            f"Screen sharing loop started for monitor {self._stream_monitor_index}."
        )  # Log monitor
        while not self._screen_sharing_stopevent.is_set():
            start_time = time.perf_counter()
            try:
                # --- Use current settings including monitor index ---
                frame_data, cursor_pos = utils.capture_screen_frame(
                    monitor_number=self._stream_monitor_index,  # Pass monitor index
                    quality=self._stream_quality,
                    scale=self._stream_scale_factor,
                )

                if (
                    frame_data
                    and self.websocket_handler
                    and self.websocket_handler.is_connected()
                ):
                    cursor_bytes = b""
                    if isinstance(cursor_pos, (tuple, list)) and len(cursor_pos) == 2:
                        try:
                            cursor_bytes = cursor_pos[0].to_bytes(
                                4, "big"
                            ) + cursor_pos[1].to_bytes(4, "big")
                        except OverflowError:
                            print(
                                f"[WARN] Cursor position {cursor_pos} out of range for 4-byte int."
                            )
                            cursor_bytes = (0).to_bytes(4, "big") + (0).to_bytes(
                                4, "big"
                            )
                    else:
                        cursor_bytes = (0).to_bytes(4, "big") + (0).to_bytes(4, "big")

                    message_bytes = frame_data + cursor_bytes
                    self.websocket_handler.send_binary_message(message_bytes)

            except Exception as e:
                print(f"Error in screen sharing loop: {e}")
                import traceback

                traceback.print_exc()
                time.sleep(0.5)

            end_time = time.perf_counter()
            time_taken = end_time - start_time

            # --- FPS Limiting using current setting ---
            target_fps = max(1, self._stream_fps)  # Use internal attribute
            target_delay = 1.0 / target_fps
            sleep_time = max(0, target_delay - time_taken)

            if sleep_time > 0:
                self._screen_sharing_stopevent.wait(timeout=sleep_time)

        print("Screen sharing loop finished.")

    # --- Stream Settings Handlers --- Use correct attribute names
    @pyqtSlot(int)
    def _handle_quality_changed(self, quality):
        print(f"Stream quality set to: {quality}%")
        self._stream_quality = quality

    @pyqtSlot(int)
    def _handle_scale_changed(self, scale_percent):
        self._stream_scale_factor = scale_percent / 100.0
        print(
            f"Stream scale set to: {scale_percent}% (Factor: {self._stream_scale_factor})"
        )

    @pyqtSlot(int)
    def _handle_fps_changed(self, fps):
        print(f"Stream Max FPS set to: {fps}")
        self._stream_fps = fps

    @pyqtSlot(int)
    def _handle_monitor_changed(self, monitor_index):
        """Handles signal when monitor selection changes."""
        print(f"Stream monitor set to index: {monitor_index}")
        self._stream_monitor_index = monitor_index
        # If already sharing, maybe restart to apply immediately?
        # Or just use the new index for the next frame capture.

    # --- Add the missing set_sharing_state method ---
    def set_sharing_state(self, is_sharing):
        """Updates the main window's UI based on sharing state."""
        self._is_sharing_screen = is_sharing  # Keep internal state sync'd
        if self.main_window:
            # Pass the state to the main window's method
            self.main_window.set_sharing_state(is_sharing)
        # Reset FPS counter when stopping/starting sharing
        self._reset_fps_counter()

    # --- Intermediate slot to prevent errors if main_window is None ---
    @pyqtSlot(float)
    def _handle_fps_update_to_ui(self, fps):
        if self.main_window:
            self.main_window.update_fps_display(fps)

    # --- Helper for FPS counter ---
    def _reset_fps_counter(self):
        """Reset the FPS counter for new connections or disconnections"""
        self._frame_count = 0
        self._last_fps_update = time.time()
        if self.main_window:
            if hasattr(self.main_window, "update_fps_display"):
                self.main_window.update_fps_display(0.0)
            else:
                print("[DEBUG] update_fps_display method not found on main_window")

    # --- New Slot for Reconnect Timer ---
    @pyqtSlot()
    def _attempt_reconnect(self):
        """Attempts to reconnect to the WebSocket server."""
        self._reconnect_attempts += 1
        
        # Update UI to show connecting status
        if self.main_window:
            self.main_window.set_connection_status(ui.MainWindow.CONNECTION_STATUS_CONNECTING)
            self.main_window.update_ws_status(f"Reconnecting ({self._reconnect_attempts}/{self.MAX_RECONNECT_ATTEMPTS})...")
            self.main_window.show_status_message("Attempting WebSocket Reconnect...")
            
        print(f"Attempting to reconnect (Attempt {self._reconnect_attempts}/{self.MAX_RECONNECT_ATTEMPTS})")
        
        # Attempt to reconnect
        self.init_websocket()
        
        # If we've reached max attempts, stop trying
        if self._reconnect_attempts >= self.MAX_RECONNECT_ATTEMPTS:
            print("Max reconnect attempts reached. Giving up.")
            self._reconnect_timer.stop()
            
            # Update UI to show disconnected status
            if self.main_window:
                self.main_window.set_connection_status(ui.MainWindow.CONNECTION_STATUS_DISCONNECTED)
                self.main_window.update_ws_status("Disconnected (Failed)")
                self.main_window.show_status_message("WebSocket Disconnected. Max reconnect attempts reached.")

    # --- New Slot for View Permission ---
    @pyqtSlot(str)
    def _ask_view_permission_slot(self, requester_uid):
        """Shows dialog asking user to allow viewing."""
        if not self.main_window:
            print("[Error] Cannot ask view permission, main window missing.")
            self._send_view_response(requester_uid, False)
            return

        reply = QMessageBox.question(
            self.main_window,
            "View Request",
            f"User '{requester_uid}' wants to view your screen. Allow?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        allow_view = reply == QMessageBox.Yes
        self._send_view_response(requester_uid, allow_view)

        if allow_view:
            self.current_peer_uid = requester_uid
            self._last_status_message = f"Allowing {requester_uid} to view."
            self.main_window.set_connected_state(requester_uid)
        else:
            # Correctly indented:
            print(f"Denied view request from {requester_uid}")

    def _send_view_response(self, target_uid, allowed):
        """Sends the view response back to the requester via backend."""
        if self.websocket_handler and self.websocket_handler.is_connected():
            response_message = {
                "type": "view_response",
                "target_uid": target_uid,
                "allowed": allowed,
                "message": (
                    "View request accepted" if allowed else "View request denied"
                ),
            }
            self.websocket_handler.send_message(response_message)

    # --- Rename and Modify MainWindow Signal Handler ---
    def handle_request_view(self, target_uid):
        print(
            f"[DEBUG Client {self.username}] handle_request_view CALLED with UID: {target_uid}"
        )

        # Validate that a target UID was provided
        if not target_uid or target_uid.strip() == "":
            QMessageBox.warning(
                self.main_window,
                "Error",
                "Please enter a valid Peer UID to request view.",
            )
            return

        if self.websocket_handler and self.websocket_handler.is_connected():
            # Send view request message
            message = {
                "type": "request_view",
                "target_uid": target_uid,
                "sender_uid": self.username,
            }
            # Don't store current_peer_uid until connection is confirmed
            # self.current_peer_uid = target_uid 
            self.websocket_handler.send_message(message)

            if self.main_window:
                # Set Peer Status to Connecting (Yellow)
                self.main_window.set_peer_connection_status(ui.MainWindow.PEER_STATUS_CONNECTING)
                self._last_status_message = (
                    f"Requesting to view {target_uid}'s screen..."
                )
                self.main_window.show_status_message(self._last_status_message)
                # Disable the request button while waiting for response
                self.main_window.request_view_button.setEnabled(False)

            print(f"[DEBUG] Sent view request to {target_uid}, waiting for response")

            # REMOVE AUTO-CONNECTION - Wait for proper view_response
        else:
            QMessageBox.warning(
                self.main_window,
                "Error",
                "WebSocket not connected. Cannot request view.",
            )

    def handle_screen_frame(self, message):
        """Process received screen frames from peers"""
        try:
            # Extract frame data
            frame_data = message.get("frame")
            if not frame_data:
                print("[WARNING] Received screen_frame message without frame data")
                return

            # Decode the base64 image data
            image_bytes = base64.b64decode(frame_data)

            # Display the frame
            if self.main_window:
                self.main_window.update_remote_screen(image_bytes)

                # Update FPS counter
                self._frame_count += 1
                current_time = time.time()
                elapsed = current_time - self._last_fps_update

                # Update FPS display every second
                if elapsed >= 1.0:
                    fps = self._frame_count / elapsed
                    self.fps_updated_signal.emit(fps)
                    self._frame_count = 0
                    self._last_fps_update = current_time
        except Exception as e:
            print(f"[ERROR] Error handling screen frame: {str(e)}")
            traceback.print_exc()

    def handle_input_event(self, message):
        """Process input events from the viewer"""
        try:
            event_data = message.get("event")
            sender_uid = message.get("sender_uid")

            if not sender_uid:
                print("[ERROR] Input event missing sender_uid")
                return

            if not event_data:
                print("[ERROR] Input event missing event data")
                return

            # Only process input if we're sharing our screen
            if self._is_sharing_screen:
                # Check if this sender has permission
                if sender_uid in self.control_permissions:
                    print(f"[DEBUG] Processing input event from {sender_uid}")
                    self.simulate_received_input(sender_uid, event_data)
                else:
                    print(
                        f"[DEBUG] Ignoring input event from {sender_uid} (no permission)"
                    )
            else:
                print(
                    f"[DEBUG] Ignoring input event from {sender_uid} (not sharing screen)"
                )

        except Exception as e:
            print(f"[ERROR] Error handling input event: {str(e)}")
            traceback.print_exc()

    def handle_connection_status(self, message):
        """Process connection status updates from the server (regarding PEERS)"""
        try:
            status = message.get("status")
            peer_uid = message.get("peer_uid")
            message_text = message.get("message", "")

            print(f"[DEBUG] Peer Connection status: {status} - Peer: {peer_uid} - Msg: {message_text}")

            if status == "connected_to_peer":
                self.current_peer_uid = peer_uid
                if self.main_window:
                    # This call now updates the peer indicator to Green
                    self.main_window.set_connected_state(peer_uid)
                    self.main_window.request_view_button.setEnabled(True) # Re-enable button

            elif status == "peer_disconnected" or status == "disconnect_success":
                if self.main_window:
                     # This call now updates the peer indicator to Red
                    self.main_window.set_disconnected_state(f"Peer {peer_uid} disconnected. {message_text}")
                    self.main_window.request_view_button.setEnabled(True) # Re-enable button
                if self.current_peer_uid == peer_uid:
                    self.current_peer_uid = None

            elif status == "error" or status == "connection_failed":
                if self.main_window:
                    # Update status bar and show message box
                    self.main_window.show_status_message(f"Peer Connection Error: {message_text}")
                    QMessageBox.warning(
                        self.main_window, "Peer Connection Error", message_text
                    )
                    # Ensure UI is in disconnected state (indicator turns Red)
                    self.main_window.set_disconnected_state(f"Peer Connection Failed: {message_text}")
                    self.main_window.request_view_button.setEnabled(True) # Re-enable button
                # Clear potential peer uid if connection failed
                if self.current_peer_uid == peer_uid:
                     self.current_peer_uid = None

        except Exception as e:
            print(f"[ERROR] Error handling peer connection status: {str(e)}")
            traceback.print_exc()

    def handle_login_response(self, message):
        """Process login response from the server"""
        try:
            success = message.get("success", False)
            message_text = message.get("message", "")

            if success:
                print(f"[DEBUG] Login successful: {message_text}")
                self.is_logged_in = True
                if self.main_window:
                    self.main_window.show_status_message("Logged in successfully", 3000)
                    self.main_window.set_logged_in_state(True)
            else:
                print(f"[ERROR] Login failed: {message_text}")
                self.is_logged_in = False
                if self.main_window:
                    self.main_window.show_status_message(f"Login failed: {message_text}")
                    self.main_window.set_logged_in_state(False)

        except Exception as e:
            print(f"[ERROR] Error handling login response: {str(e)}")
            traceback.print_exc()

    def _start_sharing_after_permission(self):
        """Start sharing screen after permission has been granted"""
        print("[DEBUG] Starting screen sharing after permission granted")
        if self.main_window:
            # Update UI state
            self.main_window.show_status_message("Screen sharing started")
            self.main_window.start_sharing_button.setEnabled(False)
            self.main_window.stop_sharing_button.setEnabled(True)

            # Actually start sharing
            self.set_sharing_state(True)
            self.start_screen_sharing_thread()

    def initialize_ui(self):
        """Initialize the UI and create main window"""
        print(f"[DEBUG Client {self.username}] Initializing UI")

        # Create main window
        self.main_window = ui.MainWindow(self.username)  # Pass username

        # Ensure screen display widget is in view-only mode by default
        if (
            hasattr(self.main_window, "screen_display_widget")
            and self.main_window.screen_display_widget
        ):
            print("[DEBUG] Setting screen display widget to view-only mode by default")
            self.main_window.screen_display_widget.view_only = True

        # Set up UI signal connections
        self.main_window.request_view_signal.connect(self.handle_request_view)
        self.main_window.logout_signal.connect(self.handle_logout)
        self.main_window.start_sharing_signal.connect(self.start_screen_sharing)
        self.main_window.stop_sharing_signal.connect(self.stop_screen_sharing)
        self.main_window.mouse_permission_signal.connect(
            self.handle_mouse_permission_change
        )

    # Adding the missing method to handle mouse permission changes
    def handle_mouse_permission_change(self, allowed):
        """Handle mouse permission changes from the UI."""
        print(f"[DEBUG] Mouse permission changed to: {allowed}")

        if not self.current_peer_uid:
            print("[DEBUG] No peer connected, ignoring mouse permission change")
            return

        if (
            hasattr(self, "main_window")
            and self.main_window
            and hasattr(self.main_window, "screen_display_widget")
        ):
            # Update the view_only state of the screen_display_widget
            self.main_window.screen_display_widget.set_view_only(not allowed)
            print(f"[DEBUG] Set screen display view_only to: {not allowed}")

            # Update permissions dictionary
            self.control_permissions[self.current_peer_uid] = allowed

            # Send permission update to the peer
            if self.websocket_handler and self.websocket_handler.is_connected():
                message = {
                    "type": "input_permission_update",
                    "target_uid": self.current_peer_uid,
                    "sender_uid": self.username,
                    "allowed": allowed,
                }
                self.websocket_handler.send_message(message)
                print(
                    f"[DEBUG] Sent input permission update to {self.current_peer_uid}: {allowed}"
                )

    @pyqtSlot()
    def toggle_theme(self):
        """Switches between light and dark themes and reapplies styles."""
        print("[DEBUG] Toggling theme...")
        if self.current_theme == "dark":
            self.current_theme = "light"
        else:
            self.current_theme = "dark"

        self.apply_theme()  # Reload and apply the new stylesheet
        
        # Update main window theme button if it exists
        if self.main_window:
            self.main_window._update_theme_icon(self.current_theme)


if __name__ == "__main__":
    # Ensure utils are imported before creating AppController if default port is needed early
    # import utils # utils might not be needed directly at start anymore
    # Import mss here if used in the loop
    import mss

    controller = AppController()
    controller.run()
