import sys
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import QObject, pyqtSignal # Import QObject and pyqtSignal
from PyQt5.QtGui import QPixmap

# Import local modules
import utils
import ui
import server # Keep for now, might be removed later
import client # Keep for now, might be removed later
import httpx # Import httpx
from websocket_handler import WebSocketHandler # Import WebSocketHandler
import base64 # For encoding image data
import threading # For screen sending thread
import time # For sleep

# Import necessary modules from Pillow
from PIL import Image
import io

class AppController(QObject): # Inherit from QObject for signal/slot usage if needed later
    # Signal to request showing the permission dialog in the GUI thread
    request_permission_signal = pyqtSignal(str, object) # controller_uid, pending_event

    def __init__(self):
        super().__init__() # Initialize the QObject base class
        self.app = QApplication(sys.argv)
        # Remove old attributes not needed immediately
        # self.local_ip = utils.get_local_ip()
        # self.default_port = utils.DEFAULT_PORT

        # New attributes for new architecture
        self.login_window = None
        self.main_window = None # Placeholder for the post-login window
        self.api_client = None # Placeholder for API interaction logic
        self.websocket_handler = None # Placeholder for WebSocket logic
        self.jwt_token = None
        self.backend_base_url = None # Will be set from LoginWindow
        self.username = None # Store username after login
        self.current_peer_uid = None # Store UID of the peer we are connected to
        self.control_permissions = {} # Store permission status: {peer_uid: bool}
        self._is_sharing_screen = False
        self._screen_sharing_thread = None
        self._screen_sharing_stopevent = threading.Event()
        # Default streaming settings (can be made configurable later)
        self.stream_quality = 95 # Increased JPEG quality further
        self.stream_fps = 15 # Back to 15 FPS
        self.stream_scale = 1.0 # Back to no scaling (or try 0.9)

        # Remove old window/instance attributes
        # self.initial_window = None
        # self.host_window = None
        # self.client_window = None
        # self.server_instance = None
        # self.client_instance = None

        self.show_login_window() # Start with login

        # Connect the new signal to its slot
        self.request_permission_signal.connect(self.show_permission_dialog_slot)

    def show_login_window(self):
        """Displays the login window."""
        if self.login_window is None:
            self.login_window = ui.LoginWindow()
            self.login_window.login_attempt_signal.connect(self.handle_login_attempt)
        self.login_window.show()

    def handle_login_attempt(self, backend_url, username, password):
        """Handles the login attempt signal from LoginWindow."""
        print(f"Attempting login to {backend_url} for user {username}")
        self.backend_base_url = backend_url
        self.username = username # Store username
        self.login_window.set_logging_in() # Update UI to show pending state

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
        time.sleep(1) # Simulate network delay
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
        print(f"Proceeding to main app for user {self.username} with token: {self.jwt_token}")
        self.show_main_window()
        # QMessageBox.information(None, "Login Success", "Login Successful! Main window placeholder.")
        # self.app.quit() # Don't quit anymore

        # --- Initialize WebSocket Handler after showing main window ---
        self.init_websocket()

    def init_websocket(self):
        """Initializes and connects the WebSocket handler."""
        if not self.backend_base_url or not self.jwt_token:
            print("Cannot initialize WebSocket: Missing Backend URL or Token.")
            QMessageBox.critical(self.main_window, "Error", "Cannot initialize connection: Missing Backend URL or Token.")
            return

        if self.websocket_handler and self.websocket_handler.is_connected():
            print("WebSocket already initialized and connected.")
            return

        print("Initializing WebSocket Handler...")
        self.websocket_handler = WebSocketHandler(self.backend_base_url, self.jwt_token)

        # Connect signals from WebSocketHandler
        self.websocket_handler.connected_signal.connect(self.on_websocket_connected)
        self.websocket_handler.disconnected_signal.connect(self.on_websocket_disconnected)
        self.websocket_handler.error_signal.connect(self.on_websocket_error)
        self.websocket_handler.message_received_signal.connect(self.handle_websocket_message) # Handles JSON
        self.websocket_handler.binary_message_received_signal.connect(self.handle_websocket_binary_message) # Handles Binary
        self.websocket_handler.status_update_signal.connect(self.main_window.update_status)

        # Attempt to connect
        self.websocket_handler.connect_ws()

    def show_main_window(self):
        """Creates and shows the main application window."""
        if self.main_window is None:
            print("[DEBUG] Creating MainWindow...")
            self.main_window = ui.MainWindow(self.username) # Pass username
            # Connect signals from MainWindow to controller methods
            print("[DEBUG] Connecting MainWindow signals...")
            self.main_window.connect_to_peer_signal.connect(self.handle_connect_to_peer)
            print("[DEBUG]  - connect_to_peer_signal connected.")
            self.main_window.disconnect_signal.connect(self.handle_disconnect)
            print("[DEBUG]  - disconnect_signal connected.")
            self.main_window.send_chat_message_signal.connect(self.handle_send_chat)
            print("[DEBUG]  - send_chat_message_signal connected.")
            self.main_window.logout_signal.connect(self.handle_logout)
            print("[DEBUG]  - logout_signal connected.")
            # --- TEMPORARY: Connect Sharing Signals ---
            self.main_window.start_sharing_signal.connect(self.start_screen_sharing)
            self.main_window.stop_sharing_signal.connect(self.stop_screen_sharing)
            print("[DEBUG]  - sharing signals connected.")
            # --- END TEMPORARY ---
            # --- Connect screen input signals --- 
            self.main_window.screen_widget.mouse_event_signal.connect(self.handle_send_input_event)
            print("[DEBUG]  - screen_widget.mouse_event_signal connected.")
            self.main_window.screen_widget.key_event_signal.connect(self.handle_send_input_event)
            print("[DEBUG]  - screen_widget.key_event_signal connected.")

            # Note: Connecting signals FROM websocket handler is now done in init_websocket
            print("[DEBUG] MainWindow signals connected.")

        self.main_window.show()
        print("[DEBUG] MainWindow shown.")

    # --- WebSocket Signal Handlers ---
    def on_websocket_connected(self):
        print("Controller: WebSocket Connected!")
        # UI is updated via status_update_signal connection
        # Maybe enable certain UI elements if needed
        # self.main_window.set_disconnected_state("WebSocket Connected. Ready to connect to peer.") # Or similar status
        # --- TEMPORARY: Enable disconnect button for testing WS closure ---
        if self.main_window:
             self.main_window.disconnect_button.setEnabled(True)
             self.main_window.update_status("WebSocket Connected. Ready.") # Update status too
        # --- END TEMPORARY ---
        pass

    def on_websocket_disconnected(self, reason):
        print(f"Controller: WebSocket Disconnected. Reason: {reason}")
        self.stop_screen_sharing() # Ensure screen sharing stops if active
        self.control_permissions = {} # Clear permissions on disconnect
        if self.main_window:
             # Use the main window's method to reset UI state
             self.main_window.set_disconnected_state(f"WebSocket Disconnected: {reason}")
        self.websocket_handler = None # Clear the handler

    def on_websocket_error(self, error_message):
        print(f"Controller: WebSocket Error: {error_message}")
        # Optionally show a message box
        QMessageBox.warning(self.main_window, "WebSocket Error", error_message)
        # Disconnect handler might be called automatically after error by the library
        # or we might need to call self.handle_disconnect() here

    def handle_websocket_message(self, data):
        """Handles JSON messages received from the WebSocket."""
        message_type = data.get('type')
        # print(f"Controller: Received WS message type: {message_type}, Data: {str(data)[:100]}...") # Less verbose logging

        # --- Routing based on message type ---
        if message_type == 'chat':
            sender = data.get('sender', 'Peer')
            message = data.get('message', '')
            if self.main_window:
                 self.main_window.append_chat_message(f"{sender}: {message}")
        elif message_type == 'input_event': # Received input to simulate
            event_data = data.get('event')
            sender_uid = data.get('sender_uid') # Get sender from message
            # print(f"[DEBUG Client {self.username}] Received input_event from {sender_uid}: {event_data}") # Less verbose now
            if self._is_sharing_screen:
                 # print(f"[DEBUG Client {self.username}] Sharing screen is TRUE, attempting simulation for {sender_uid}.")
                 self.simulate_received_input(sender_uid, event_data)
            # else:
            #      print(f"[DEBUG Client {self.username}] Sharing screen is FALSE, ignoring input event from {sender_uid}.")
        elif message_type == 'connection_status': # Example: Info from backend
            status = data.get('status')
            peer_uid = data.get('peer_uid')
            message = data.get('message')
            print(f"Connection Status from Backend: {status} - {message}")
            if status == 'connected_to_peer' and self.main_window:
                 self.main_window.set_connected_state(peer_uid)
            elif status == 'peer_disconnected' and self.main_window:
                 self.main_window.set_disconnected_state(f"Peer {peer_uid} disconnected.")
            elif status == 'error' and self.main_window:
                 self.main_window.set_disconnected_state(f"Connection Error: {message}") # Reset UI
                 QMessageBox.warning(self.main_window, "Connection Error", message)
        elif message_type == 'start_sharing': # Instruction from backend to start sharing
             print("Controller: Received instruction to start sharing.")
             self.start_screen_sharing()
        elif message_type == 'stop_sharing': # Instruction from backend to stop sharing
             print("Controller: Received instruction to stop sharing.")
             self.stop_screen_sharing()
        elif message_type == 'disconnect_notice': # Received from peer via server
            sender_uid = data.get('sender_uid')
            print(f"[DEBUG Client {self.username}] Received disconnect_notice from {sender_uid}")
            print(f"[DEBUG Client {self.username}] Permissions BEFORE clear: {self.control_permissions}")
            if sender_uid in self.control_permissions:
                del self.control_permissions[sender_uid]
                print(f"[DEBUG Client {self.username}] Cleared control permission for {sender_uid}.")
            else:
                 print(f"[DEBUG Client {self.username}] No permission found for {sender_uid} to clear.")
            print(f"[DEBUG Client {self.username}] Permissions AFTER clear: {self.control_permissions}")
            # Optionally, also reset the UI on this side if we were connected to them
            if self.main_window and self.current_peer_uid == sender_uid:
                self.current_peer_uid = None
                self.main_window.set_disconnected_state(f"Peer {sender_uid} disconnected.")

        # Add more handlers for other message types (settings, screen config etc.)

    def handle_websocket_binary_message(self, data_bytes):
        """Handles BINARY messages received from the WebSocket."""
        if not data_bytes:
            return
        
        # Assume first byte is the type identifier
        msg_type_byte = data_bytes[0:1]
        payload = data_bytes[1:]

        MSG_TYPE_SCREEN = b'\x01' # Must match the identifier used in _screen_sharing_loop

        if msg_type_byte == MSG_TYPE_SCREEN:
            # print(f"Received screen data: {len(payload)} bytes")
            if self.main_window:
                try:
                    # Pass the raw JPEG bytes directly
                    self.main_window.update_remote_screen(payload)
                except Exception as e:
                    print(f"Error displaying screen data: {e}")
        # Add elif for other binary message types later if needed
        else:
            print(f"Received unknown binary message type: {msg_type_byte}")

    # --- MainWindow Signal Handlers --- 
    def handle_connect_to_peer(self, target_uid):
        print(f"[DEBUG Client {self.username}] handle_connect_to_peer CALLED with UID: {target_uid}")
        if self.websocket_handler and self.websocket_handler.is_connected():
            # Send a message to the backend via WebSocket to initiate connection
            message = {
                'type': 'connect_request',
                'target_uid': target_uid
            }
            self.current_peer_uid = target_uid # Store target temporarily
            self.websocket_handler.send_message(message)
            # UI update (e.g., "Connecting...") should happen based on backend response
            # For now, MainWindow already set status in on_connect_clicked
        else:
            QMessageBox.warning(self.main_window, "Error", "WebSocket not connected. Cannot connect to peer.")

    def handle_disconnect(self):
        print(f"Controller: Request to disconnect from peer/session")
        self.stop_screen_sharing() 
        if self.websocket_handler and self.current_peer_uid:
             peer_to_notify = self.current_peer_uid
             print(f"[DEBUG Client {self.username}] Sending disconnect notice for peer {peer_to_notify}")
             disconnect_msg = {
                 'type': 'disconnect_notice',
                 'sender_uid': self.username
             }
             self.websocket_handler.send_message(disconnect_msg)
             print(f"[DEBUG Client {self.username}] Disconnect notice sent.")

        # Reset peer state FOR THIS CLIENT
        self.current_peer_uid = None
        
        # Reset UI via MainWindow method
        if self.main_window:
            self.main_window.set_disconnected_state("Disconnected from peer.")

    def handle_send_chat(self, message):
        print(f"Controller: Request to send chat message: {message}")
        if self.websocket_handler and self.websocket_handler.is_connected():
            chat_message = {
                'type': 'chat',
                'message': message
            }
            self.websocket_handler.send_message(chat_message)
        else:
             if self.main_window:
                  self.main_window.append_chat_message("<i>Error: Not connected. Cannot send message.</i>")

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
            self.main_window.screen_widget.pixmap = QPixmap()
            self.main_window.screen_widget.update()
            self.main_window.close()
            self.main_window = None

        # 3. Clear user data
        self.jwt_token = None
        self.username = None
        self.current_peer_uid = None
        self.control_permissions = {} # Clear permissions on logout
        # Keep backend_base_url? Or reset? Maybe keep.

        # 4. Show Login Window again
        self.show_login_window()

    # --- Input Handling --- 
    def handle_send_input_event(self, event_data):
        # This client is acting as the 'Controller'
        # --- MODIFIED: Only send if connected to a peer --- 
        if self.websocket_handler and self.websocket_handler.is_connected() and self.current_peer_uid:
            # Include sender's username in the message
            message = {
                'type': 'input_event',
                'sender_uid': self.username, # Add sender info
                'event': event_data 
                }
            # print(f"[DEBUG] Sending input: {message}") # Optional verbose log
            self.websocket_handler.send_message(message)
        else:
            # Optional: Log why it wasn't sent
            # if not self.current_peer_uid:
            #     print(f"[DEBUG Client {self.username}] Input event ignored: Not connected to a peer.")
            # else: 
            #     print(f"[DEBUG Client {self.username}] Input event ignored: WebSocket NOT connected.")
            pass # Silently ignore input if not connected to a peer

    def simulate_received_input(self, controller_uid, event_data):
         print(f"[DEBUG Client {self.username}] simulate_received_input CALLED for controller {controller_uid}")
         if not event_data or not controller_uid:
              print("[DEBUG] Ignoring input event: No event data or controller UID.")
              return

         # --- Check Permission using controller_uid --- 
         print(f"[DEBUG Client {self.username}] Checking permission for {controller_uid}. Current permissions: {self.control_permissions}")
         permission_granted = self.control_permissions.get(controller_uid)
         print(f"[DEBUG Client {self.username}] Permission status for {controller_uid}: {permission_granted}")
         
         if not permission_granted:
             print(f"[DEBUG {self.username}] Permission NOT granted for {controller_uid}. Emitting request signal...")
             # --- Add Log Before Emit --- 
             print(f"[FINAL CHECK] Emitting request_permission_signal for {controller_uid}")
             # --- End Log --- 
             self.request_permission_signal.emit(controller_uid, event_data) 
             return # Don't process event yet
         # --- Permission Granted --- 
         print(f"[DEBUG {self.username}] Permission GRANTED for {controller_uid}. Proceeding with simulation.")
         
         event_sub_type = event_data.get('type')
         print(f"[DEBUG Client {self.username}] Simulating input from {controller_uid}: {event_sub_type}, Data: {event_data}")
         try:
             if event_sub_type in ['move', 'click', 'press', 'release', 'scroll']:
                 # Call the function with only the event data now
                 print(f"[DEBUG Client {self.username}] Calling utils.simulate_mouse_event with x={event_data.get('x')}, y={event_data.get('y')}")
                 utils.simulate_mouse_event(event_data)
             elif event_sub_type in ['press', 'release'] and 'key' in event_data:
                  # Check if 'key' exists to differentiate from mouse press/release
                   print(f"[DEBUG Client {self.username}] Calling utils.simulate_keyboard_event with key={event_data.get('key')}")
                   utils.simulate_keyboard_event(event_data)
             else:
                  print(f"[DEBUG Client {self.username}] Unknown input event sub-type: {event_sub_type}")
         except Exception as e:
              print(f"[DEBUG Client {self.username}] Error during simulation call: {e}")

    def show_permission_dialog_slot(self, controller_uid, pending_event):
        """SLOT: Shows the permission dialog. Guaranteed to run in GUI thread."""
        print(f"[UI SLOT ENTRY] Requesting permission from user for {controller_uid}")
        if not self.main_window:
            print("[UI SLOT] MainWindow not available to show dialog.")
            return
        
        # --- Restore Flag Check --- 
        if hasattr(self.main_window, '_permission_dialog_open') and self.main_window._permission_dialog_open:
            print("[UI SLOT] Permission dialog already open. Ignoring request.")
            return 
        self.main_window._permission_dialog_open = True # Flag it
        # --- End Restore Flag Check ---

        try:
            print(f"[UI SLOT] About to show QMessageBox for {controller_uid}")
            reply = QMessageBox.question(self.main_window, 'Control Request', 
                                           f"User '{controller_uid}' wants to control your desktop. Allow?",
                                           QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            print(f"[UI SLOT] QMessageBox reply: {reply == QMessageBox.Yes}")

            if reply == QMessageBox.Yes:
                print(f"Permission GRANTED for {controller_uid}")
                self.control_permissions[controller_uid] = True
                # --- REMOVED RECURSIVE CALL --- 
                # Process the pending event, passing controller_uid again
                # print("Processing pending event after permission grant.")
                # self.simulate_received_input(controller_uid, pending_event)
                # --- END REMOVED --- 
                # Subsequent events will now pass the permission check naturally.
            else:
                print(f"Permission DENIED for {controller_uid}")
                self.control_permissions[controller_uid] = False # Explicitly deny
        except Exception as e:
             print(f"[UI SLOT] Error showing/handling permission dialog: {e}")
        finally:
            # --- Restore Flag Reset --- 
            # Ensure flag is reset regardless of outcome
             if hasattr(self.main_window, '_permission_dialog_open'):
                  self.main_window._permission_dialog_open = False
            # --- End Restore Flag Reset ---

    def run(self):
        """Starts the Qt application event loop."""
        self.app.aboutToQuit.connect(self.cleanup)
        sys.exit(self.app.exec_())

    def cleanup(self):
        """Ensures resources are cleaned up on application exit."""
        print("Cleaning up before exit...")
        self.stop_screen_sharing() # Ensure sharing stops on exit
        # Stop WebSocket handler if running
        if self.websocket_handler:
             self.websocket_handler.stop()

    # --- Screen Sharing Logic ---
    def start_screen_sharing(self):
        """Starts sending screen updates in a separate thread."""
        if self._is_sharing_screen:
            print("Screen sharing already active.")
            return
        if not self.websocket_handler or not self.websocket_handler.is_connected():
            print("Cannot start sharing: WebSocket not connected.")
            QMessageBox.warning(self.main_window, "Error", "WebSocket not connected. Cannot share screen.")
            if self.main_window: # Reset button state if failed
                self.main_window.stop_sharing_button.setEnabled(False)
                self.main_window.start_sharing_button.setEnabled(True)
            return

        print("Starting screen sharing...")
        self._is_sharing_screen = True
        self._screen_sharing_stopevent.clear() # Ensure stop event is clear
        self._screen_sharing_thread = threading.Thread(target=self._screen_sharing_loop, daemon=True)
        self._screen_sharing_thread.start()
        # Optional: Update UI state if not already done by button click
        if self.main_window:
             self.main_window.start_sharing_button.setEnabled(False)
             self.main_window.stop_sharing_button.setEnabled(True)

    def stop_screen_sharing(self):
        """Signals the screen sharing thread to stop."""
        if not self._is_sharing_screen:
            print("Screen sharing not active.")
            return

        print("Stopping screen sharing...")
        self._is_sharing_screen = False
        self._screen_sharing_stopevent.set() # Signal thread to stop

        # Wait briefly for thread to finish (optional, but good practice)
        if self._screen_sharing_thread and self._screen_sharing_thread.is_alive():
             self._screen_sharing_thread.join(timeout=0.5)
        self._screen_sharing_thread = None

        # Update UI state
        if self.main_window:
             self.main_window.start_sharing_button.setEnabled(True)
             self.main_window.stop_sharing_button.setEnabled(False)

    def _screen_sharing_loop(self):
        """The actual loop that captures, scales, compresses and sends the screen."""
        # Define message type identifiers (bytes)
        MSG_TYPE_SCREEN = b'\x01'

        # Get screen dimensions once (optional, can be inside loop if screen changes)
        # We might need utils.get_screen_size() or similar if not using pyautogui directly
        # screen_width, screen_height = pyautogui.size() 

        with mss.mss() as sct:
            monitor = sct.monitors[1] # Assuming primary monitor

            while self._is_sharing_screen and not self._screen_sharing_stopevent.is_set():
                start_time = time.time()
                try:
                    # 1. Capture raw screen data using mss
                    sct_img = sct.grab(monitor)
                    
                    # 2. Convert to PIL Image
                    img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

                    # 3. Scale the image if scale factor is not 1.0
                    scaled_img = img
                    if self.stream_scale != 1.0:
                        new_width = int(img.width * self.stream_scale)
                        new_height = int(img.height * self.stream_scale)
                        # Use LANCZOS for potentially better quality resizing
                        scaled_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS) 
                    
                    # 4. Compress the (potentially scaled) image to JPEG bytes
                    img_byte_arr = io.BytesIO()
                    scaled_img.save(img_byte_arr, format='JPEG', quality=self.stream_quality)
                    screenshot_bytes = img_byte_arr.getvalue()

                    if screenshot_bytes:
                        # 5. Send as Binary (prepend type byte)
                        message_to_send = MSG_TYPE_SCREEN + screenshot_bytes
                        if self.websocket_handler and self.websocket_handler.is_connected():
                            self.websocket_handler.send_binary_message(message_to_send)
                        else:
                            print("Screen sharing loop: WebSocket disconnected. Stopping.")
                            break
                    else:
                        print("Screen sharing loop: Failed to capture/compress screenshot.")
                        time.sleep(0.5)

                except Exception as e:
                    print(f"Error in screen sharing loop: {e}")
                    break

                # Control frame rate
                elapsed_time = time.time() - start_time
                sleep_time = (1.0 / self.stream_fps) - elapsed_time
                if sleep_time > 0:
                    self._screen_sharing_stopevent.wait(sleep_time)

        print("Screen sharing loop finished.")
        self._is_sharing_screen = False


if __name__ == '__main__':
    # Ensure utils are imported before creating AppController if default port is needed early
    # import utils # utils might not be needed directly at start anymore
    # Import mss here if used in the loop
    import mss 
    controller = AppController()
    controller.run() 