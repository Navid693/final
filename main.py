import sys
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import QObject # Import QObject

# Import local modules
import utils
import ui
import server # Keep for now, might be removed later
import client # Keep for now, might be removed later
import httpx # Import httpx
from websocket_handler import WebSocketHandler # Import WebSocketHandler

class AppController(QObject): # Inherit from QObject for signal/slot usage if needed later
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

        # Remove old window/instance attributes
        # self.initial_window = None
        # self.host_window = None
        # self.client_window = None
        # self.server_instance = None
        # self.client_instance = None

        self.show_login_window() # Start with login

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

        # --- Connect signals from WebSocketHandler to Controller/UI --- 
        self.websocket_handler.connected_signal.connect(self.on_websocket_connected)
        self.websocket_handler.disconnected_signal.connect(self.on_websocket_disconnected)
        self.websocket_handler.error_signal.connect(self.on_websocket_error)
        self.websocket_handler.message_received_signal.connect(self.handle_websocket_message)
        self.websocket_handler.status_update_signal.connect(self.main_window.update_status) # Update status bar directly

        # Attempt to connect
        self.websocket_handler.connect_ws()

    def show_main_window(self):
        """Creates and shows the main application window."""
        if self.main_window is None:
            self.main_window = ui.MainWindow(self.username) # Pass username
            # Connect signals from MainWindow to controller methods
            self.main_window.connect_to_peer_signal.connect(self.handle_connect_to_peer)
            self.main_window.disconnect_signal.connect(self.handle_disconnect)
            self.main_window.send_chat_message_signal.connect(self.handle_send_chat)
            # Connect screen input signals (to be implemented later)
            # self.main_window.screen_widget.mouse_event_signal.connect(self.handle_send_mouse_event)
            # self.main_window.screen_widget.key_event_signal.connect(self.handle_send_key_event)

            # Note: Connecting signals FROM websocket handler is now done in init_websocket

        self.main_window.show()

    # --- WebSocket Signal Handlers ---
    def on_websocket_connected(self):
        print("Controller: WebSocket Connected!")
        # UI is updated via status_update_signal connection
        # Maybe enable certain UI elements if needed
        # self.main_window.set_disconnected_state("WebSocket Connected. Ready to connect to peer.") # Or similar status
        pass

    def on_websocket_disconnected(self, reason):
        print(f"Controller: WebSocket Disconnected. Reason: {reason}")
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
        """Handles messages received from the WebSocket."""
        message_type = data.get('type')
        print(f"Controller: Received WS message type: {message_type}, Data: {str(data)[:100]}...")

        # TODO: Implement routing based on message type
        if message_type == 'chat':
            sender = data.get('sender', 'Peer')
            message = data.get('message', '')
            if self.main_window:
                 self.main_window.append_chat_message(f"{sender}: {message}")
        elif message_type == 'screen':
            # Assuming image data is base64 encoded or similar in JSON
            # image_data_base64 = data.get('image_data')
            # if image_data_base64 and self.main_window:
            #     import base64
            #     try:
            #         image_data = base64.b64decode(image_data_base64)
            #         self.main_window.update_remote_screen(image_data)
            #     except Exception as e:
            #         print(f"Error decoding screen data: {e}")
            pass # Screen handling needs more definition
        elif message_type == 'cursor':
            # x = data.get('x')
            # y = data.get('y')
            # if x is not None and y is not None and self.main_window:
            #     self.main_window.update_remote_cursor(x, y)
            pass # Cursor handling needs more definition
        elif message_type == 'input_event': # Example: Host receives input
            # event_data = data.get('event')
            # if event_data:
            #    self.simulate_input(event_data) # Need a simulation method
            pass
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

        # Add more handlers for other message types (settings, screen config etc.)


    # --- MainWindow Signal Handlers --- 
    def handle_connect_to_peer(self, target_uid):
        print(f"Controller: Request to connect to UID: {target_uid}")
        if self.websocket_handler and self.websocket_handler.is_connected():
            # Send a message to the backend via WebSocket to initiate connection
            message = {
                'type': 'connect_request',
                'target_uid': target_uid
            }
            self.websocket_handler.send_message(message)
            # UI update (e.g., "Connecting...") should happen based on backend response
            # For now, MainWindow already set status in on_connect_clicked
        else:
            QMessageBox.warning(self.main_window, "Error", "WebSocket not connected. Cannot connect to peer.")

    def handle_disconnect(self):
        print(f"Controller: Request to disconnect from peer/session")
        if self.websocket_handler:
            # Send a message to backend *if* needed to end session gracefully
            # self.websocket_handler.send_message({'type': 'disconnect_request'})
            # Then stop the handler, which will trigger on_websocket_disconnected
            self.websocket_handler.stop()
        # Update UI immediately if needed
        if self.main_window:
            self.main_window.set_disconnected_state("Disconnected by user.")

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

    # --- Input Handling (Placeholder for later) ---
    # def handle_send_mouse_event(self, event_data):
    #     if self.websocket_handler and self.websocket_handler.is_connected():
    #         message = {'type': 'input_event', 'event': event_data}
    #         self.websocket_handler.send_message(message)

    # def handle_send_key_event(self, event_data):
    #     if self.websocket_handler and self.websocket_handler.is_connected():
    #         message = {'type': 'input_event', 'event': event_data}
    #         self.websocket_handler.send_message(message)

    # def simulate_input(self, event_data):
    #      # This would call utils.simulate_mouse_event or simulate_keyboard_event
    #      # Needs screen dimensions etc.
    #      print(f"Simulating input: {event_data}")
    #      pass

    def run(self):
        """Starts the Qt application event loop."""
        self.app.aboutToQuit.connect(self.cleanup)
        sys.exit(self.app.exec_())

    def cleanup(self):
        """Ensures resources are cleaned up on application exit."""
        print("Cleaning up before exit...")
        # Stop WebSocket handler if running
        if self.websocket_handler:
             self.websocket_handler.stop()


if __name__ == '__main__':
    # Ensure utils are imported before creating AppController if default port is needed early
    # import utils # utils might not be needed directly at start anymore
    controller = AppController()
    controller.run() 