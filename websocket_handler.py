# websocket_handler.py
import websocket # Use websocket-client library
import threading
import json
import time
import traceback
from PyQt5.QtCore import QObject, pyqtSignal

class WebSocketHandler(QObject):
    """Handles WebSocket connections and messaging to the remote server.
    Acts as the low-level communication layer between the AppController and the backend.
    Responsible for establishing the connection, sending/receiving raw messages,
    and emitting signals to the AppController based on received message types.
    """
    
    # --- Signals Emitted to AppController ---
    # Connection signals
    connected_signal = pyqtSignal() # Emitted on successful WS connection AND user registration
    disconnected_signal = pyqtSignal(str) # Emitted on WS disconnect (reason)
    error_signal = pyqtSignal(str) # Emitted on WS errors (error message)
    
    # Message signals (parsed from incoming WS messages)
    message_received_signal = pyqtSignal(dict) # Generic JSON message for AppController processing
    binary_message_received_signal = pyqtSignal(bytes) # Raw binary data (screen frames)
    status_update_signal = pyqtSignal(str) # Status messages for UI display (e.g., connecting)
    
    # Specific signals based on message types from Backend
    # TODO (Backend): Ensure backend sends messages with these exact 'type' fields.
    user_registered_signal = pyqtSignal(bool, str) # Emitted after receiving 'register_response' {success, message}
    users_list_updated_signal = pyqtSignal(list) # Emitted after receiving 'users_list' {users: [...]} 
    peer_connection_requested_signal = pyqtSignal(str) # Emitted after receiving 'connection_request' {from_user}
    peer_connected_signal = pyqtSignal(str) # Emitted after receiving 'connection_response' {accepted: true, from_user}
    peer_disconnected_signal = pyqtSignal(str, str) # Emitted after receiving 'peer_disconnected' {peer, reason} or rejected 'connection_response'
    chat_message_received_signal = pyqtSignal(str, str) # Emitted after receiving 'chat_message' {from_user, text}
    
    def __init__(self, base_url, username):
        """Initialize WebSocket handler with the base server URL and username."""
        super().__init__()
        
        # --- Construct WebSocket URL (ws:// or wss://) --- 
        # Expects base_url like "http://127.0.0.1:8000"
        # TODO (Backend): Ensure the WebSocket server endpoint is correctly configured (e.g., /ws path).
        ws_scheme = ""
        http_scheme = ""
        if base_url.startswith("https://"):
            ws_scheme = "wss://"
            http_scheme = "https://"
        elif base_url.startswith("http://"):
            ws_scheme = "ws://"
            http_scheme = "http://"
        else:
            # Attempt a default guess or raise error if scheme is missing/invalid
            print(f"[WS WARNING] Invalid or missing scheme in base URL: {base_url}. Assuming ws://")
            ws_scheme = "ws://" # Assuming insecure ws if scheme missing
            http_scheme = "http://" # Needed for replace below
            # Or raise ValueError("Invalid base URL scheme")

        # Remove http(s):// prefix and potential trailing slash, append /ws path
        domain_part = base_url.replace(http_scheme, "", 1).rstrip('/')
        self.ws_url = f"{ws_scheme}{domain_part}/ws" # Standard path, adjust if backend differs
        print(f"[WS] Constructed WebSocket URL: {self.ws_url}")

        self.username = username
        self.ws = None # WebSocketApp instance
        self.is_running = False # Flag to control the run loop
        self.is_connected = False # Flag indicating successful connection AND registration
        self.ws_thread = None # Thread for running the WebSocketApp
        self.connect_lock = threading.Lock() # Lock for connect/stop operations
        self.send_lock = threading.Lock() # Lock for sending messages
        self._pending_registration = False # Flag during registration process
        self._retry_count = 0 # Reconnection attempt counter
        self._max_retries = 3 # Max reconnection attempts
        
        # Track current connected peer UID (optional, AppController primarily handles this)
        self.current_peer = None
        
    def connect_ws(self):
        """Establish a WebSocket connection in a separate thread."""
        with self.connect_lock:
            if self.is_running:
                print("[WS] Already running, ignoring connect request")
                return
                
            print("[WS] Starting WebSocket connection process...")
            self.is_running = True
            self.is_connected = False # Reset connected status
            self._retry_count = 0
            
            # Start WebSocket thread
            self.ws_thread = threading.Thread(target=self._run, daemon=True)
            self.ws_thread.start()
    
    def stop(self):
        """Stop the WebSocket connection and thread."""
        with self.connect_lock:
            if not self.is_running:
                print("[WS] Stop called but not running.")
                return
                
            print("[WS] Stopping WebSocket connection...")
            self.is_running = False # Signal the run loop to exit
            self.is_connected = False
            
            # Close WebSocket if it exists
            if self.ws:
                try:
                    # This will trigger the on_close callback eventually
                    self.ws.close()
                    print("[WS] WebSocket close requested.")
                except Exception as e:
                    print(f"[WS] Error closing WebSocket: {e}")
            
            # Wait for thread to end (with timeout)
            if self.ws_thread and self.ws_thread.is_alive():
                print("[WS] Waiting for WebSocket thread to join...")
                self.ws_thread.join(2.0)
                if self.ws_thread.is_alive():
                    print("[WS WARNING] WebSocket thread did not join cleanly.")
            self.ws_thread = None
            self.ws = None
            print("[WS] WebSocket stopped.")
    
    def _run(self):
        """WebSocket connection loop running in a separate thread.
           Handles connection, ping/pong, and reconnection logic.
        """
        while self.is_running:
            try:
                # Connect to WebSocket server
                print(f"[WS] Attempting connection to {self.ws_url} (Attempt: {self._retry_count + 1})" )
                self.status_update_signal.emit(f"Connecting to server...")
                
                # Define WebSocket callbacks
                # `websocket-client` library handles ping/pong automatically if server supports it.
                self.ws = websocket.WebSocketApp(
                    self.ws_url,
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                    # on_ping=self._on_ping, # Usually not needed
                    # on_pong=self._on_pong # Usually not needed
                )
                
                # Run WebSocket client (this is a blocking call)
                # It internally handles receiving messages and calling callbacks.
                # ping_interval sends pings every 30s, ping_timeout waits 10s for pong.
                self.ws.run_forever(ping_interval=30, ping_timeout=10)
                # If run_forever exits cleanly, it means on_close was called.
                
            except websocket.WebSocketException as e:
                print(f"[WS] WebSocketException in run loop: {e}")
                self.error_signal.emit(f"WebSocket Connection Error: {str(e)}")
            except Exception as e:
                print(f"[WS] Unexpected Error in WebSocket run loop: {e}")
                traceback.print_exc()
                self.error_signal.emit(f"WebSocket Internal Error: {str(e)}")
            
            # --- Reconnection Logic --- 
            # If loop continues and we are still supposed to be running... 
            if self.is_running:
                self.is_connected = False # Mark as disconnected
                # Check if max retries exceeded
                self._retry_count += 1
                if self._retry_count > self._max_retries:
                    print(f"[WS] Max retries ({self._max_retries}) exceeded. Stopping.")
                    self.status_update_signal.emit("Connection failed. Retry manually.")
                    self.error_signal.emit(f"Failed to connect after {self._max_retries} attempts")
                    self.is_running = False # Stop trying
                    self.disconnected_signal.emit("Connection failed (Max retries)")
                    break # Exit the while loop
                
                # Wait before next retry attempt
                retry_delay = min(30, 2 ** self._retry_count) # Exponential backoff up to 30s
                print(f"[WS] Disconnected. Reconnecting in {retry_delay} seconds...")
                self.status_update_signal.emit(f"Connection lost. Retry in {retry_delay}s...")
                # Emit disconnected signal on retry attempt as well?
                # self.disconnected_signal.emit(f"Connection lost, retrying ({self._retry_count})")
                time.sleep(retry_delay)
            else:
                # Stop was requested, break the loop
                break
        
        print("[WS] WebSocket thread terminated")
        # Final state ensurence
        self.is_running = False
        self.is_connected = False
        self.ws = None
    
    # Note: This property shadows the method name used previously in AppController checks.
    # AppController should access this via `self.websocket_handler.is_connected` (no parentheses).
    # @property
    # def is_connected(self):
    #     """Property to check if WebSocket is connected AND registered."""
    #     return self._is_connected_and_registered
    
    # --- WebSocket Event Callbacks (Called by WebSocketApp thread) --- 
    def _on_open(self, ws):
        """Called when WebSocket connection is initially established (TCP connection)."""
        print("[WS] WebSocket connection opened (TCP established)")
        # Connection isn't fully ready until user is registered with backend.
        # self.is_connected = True # Set this only after successful registration
        self.status_update_signal.emit("Connection established. Registering user...")
        self._retry_count = 0 # Reset retry counter on successful TCP connection
        
        # Register the user with the server immediately after opening
        self._register_user()
    
    def _on_message(self, ws, message):
        """Called when a text or binary message is received from the WebSocket."""
        try:
            # --- Handle Binary Data --- 
            # TODO (Backend): Backend relays binary screen frames+cursor directly.
            if isinstance(message, bytes):
                data_size_kb = len(message) / 1024
                # Avoid excessive logging for large binary frames
                # print(f"[WS] Received binary data: {data_size_kb:.1f} KB") 
                self.binary_message_received_signal.emit(message)
                return # Stop processing here for binary
            
            # --- Handle Text Messages (Assume JSON) --- 
            data = json.loads(message)
            msg_type = data.get("type", "unknown")
            print(f"[WS] Received JSON message: Type='{msg_type}', Data={data}")
            
            # --- Process known message types and emit specific signals --- 
            # TODO (Backend): Ensure backend sends these message types with specified fields.
            
            # Backend response to our registration request
            if msg_type == "register_response":
                success = data.get("success", False)
                response_message = data.get("message", "")
                print(f"[WS] Register Response: Success={success}, Msg={response_message}")
                self._pending_registration = False
                if success:
                    self.is_connected = True # Mark as fully connected ONLY after registration
                    self.connected_signal.emit() # Signal AppController: We are ready
                self.user_registered_signal.emit(success, response_message)
                
            # Backend sent updated list of online users
            elif msg_type == "users_list":
                users = data.get("users", [])
                print(f"[WS] Users List Received: {users}")
                self.users_list_updated_signal.emit(users)
                
            # Backend relaying a connection request from another user TO us
            elif msg_type == "connection_request":
                requester = data.get("from_user")
                print(f"[WS] Connection Request Received from: {requester}")
                if requester:
                    self.peer_connection_requested_signal.emit(requester)
                
            # Backend relaying the response TO our connection request
            elif msg_type == "connection_response":
                accepted = data.get("accepted", False)
                from_user = data.get("from_user") # User who responded
                reason = data.get("reason", "")
                print(f"[WS] Connection Response Received from {from_user}: Accepted={accepted}, Reason={reason}")
                if accepted:
                    self.current_peer = from_user # Track peer locally (optional)
                    self.peer_connected_signal.emit(from_user)
                else:
                    # Emit disconnected signal even for rejection, includes reason
                    self.peer_disconnected_signal.emit(from_user, f"Connection rejected: {reason}")
                
            # Backend informing us that the peer disconnected (explicitly or abruptly)
            elif msg_type == "peer_disconnected":
                peer = data.get("peer")
                reason = data.get("reason", "Peer disconnected")
                print(f"[WS] Peer Disconnected message received: Peer={peer}, Reason={reason}")
                if peer == self.current_peer:
                    self.current_peer = None # Clear local peer tracking
                self.peer_disconnected_signal.emit(peer, reason)
                
            # Backend relaying a chat message FROM another user TO us
            elif msg_type == "chat_message":
                sender = data.get("from_user")
                text = data.get("text", "")
                print(f"[WS] Chat Message Received from {sender}: {text}")
                self.chat_message_received_signal.emit(sender, text)
                
            # --- Emit generic signal for AppController --- 
            # This allows AppController to handle other message types if needed
            # (e.g., 'input_permission_update', 'error' from backend)
            elif msg_type in ["input_permission_update", "view_response", "error", "stream_settings_peer_update"]:
                 print(f"[WS] Emitting generic message signal for type: {msg_type}")
                 self.message_received_signal.emit(data)
                
            # Handle internal ping/pong if necessary (usually handled by library)
            elif msg_type == "ping":
                print("[WS] Received ping from server, sending pong")
                self.send_message({"type": "pong"})
            elif msg_type == "pong":
                print("[WS] Received pong from server")
                
            else:
                 print(f"[WS WARNING] Received unhandled message type: {msg_type}")
                 # Optionally emit generic signal even for unhandled types?
                 # self.message_received_signal.emit(data)
            
        except json.JSONDecodeError:
            print(f"[WS ERROR] Received non-JSON text message: {message}")
        except Exception as e:
            print(f"[WS ERROR] Error processing message: {e}")
            traceback.print_exc()
    
    # Note: _on_binary_message callback is not standard in websocket-client's WebSocketApp.
    # Binary messages are handled within the _on_message callback using `isinstance(message, bytes)`.
    # def _on_binary_message(self, ws, data): ...
    
    def _on_error(self, ws, error):
        """Called when a WebSocket error occurs (e.g., connection refused, protocol error)."""
        # This is often called *before* on_close when connection fails.
        print(f"[WS] WebSocket error reported: {error}")
        self.is_connected = False # Ensure connection status is false
        self.error_signal.emit(str(error))
        # The run_forever loop will likely exit after this, triggering reconnection logic in _run
    
    def _on_close(self, ws, close_status_code, close_msg):
        """Called when WebSocket connection is closed."""
        print(f"[WS] WebSocket connection closed: Code={close_status_code}, Msg='{close_msg}'")
        was_connected = self.is_connected
        self.is_connected = False
        self.ws = None # Clear the ws instance
        # Only emit disconnected signal if we weren't already stopped externally
        # and if we were previously considered fully connected (i.e. registered)
        if self.is_running and was_connected:
             reason = f"Connection closed: {close_msg} (Code: {close_status_code})"
             self.disconnected_signal.emit(reason)
        # Reconnection logic is handled by the _run loop exiting.
    
    # Usually not needed as websocket-client handles pings/pongs internally
    # def _on_ping(self, ws, data): ...
    # def _on_pong(self, ws, data): ...
    
    # --- Methods to Send Messages (Called by AppController) --- 
    
    def send_message(self, message):
        """Send a JSON message (dict) to the WebSocket server."""
        # TODO (Backend): Define expected incoming message types and fields.
        if not self.is_connected or not self.ws:
            print(f"[WS] Cannot send message (JSON): Not connected. Msg: {message}")
            return False
        
        try:
            with self.send_lock:
                message_json = json.dumps(message)
                msg_type = message.get("type", "unknown")
                # Avoid logging sensitive data if necessary
                print(f"[WS] Sending JSON: Type='{msg_type}', Data={message_json}")
                self.ws.send(message_json)
                return True
        except websocket.WebSocketConnectionClosedException:
            print(f"[WS ERROR] Connection closed while sending JSON message: {message}")
            self._handle_send_disconnect("Connection closed during send")
            return False
        except Exception as e:
            print(f"[WS ERROR] Error sending JSON message: {e}")
            traceback.print_exc()
            # Potentially signal an error or attempt disconnect? Seems serious.
            # self.error_signal.emit(f"Failed to send message: {e}")
            return False
    
    def send_binary_message(self, data):
        """Send raw binary data to the WebSocket server."""
        # TODO (Backend): Backend needs to know how to handle raw binary data.
        # It likely needs context (e.g., who is the sender/receiver pair) established
        # through previous JSON messages to relay this correctly.
        if not self.is_connected or not self.ws:
            # Avoid flooding logs for screen frames
            # print("[WS] Cannot send binary message: Not connected")
            return False
        
        try:
            data_size_kb = len(data) / 1024
            with self.send_lock:
                # Use a timeout? run_forever might handle this.
                # Log minimally for binary data unless debugging
                # print(f"[WS] Sending Binary: {data_size_kb:.1f} KB")
                self.ws.send(data, websocket.ABNF.OPCODE_BINARY)
                return True
        except websocket.WebSocketConnectionClosedException:
            # Avoid flooding logs for screen frames
            # print(f"[WS ERROR] Connection closed while sending binary message ({data_size_kb:.1f} KB)")
            self._handle_send_disconnect("Connection closed during binary send")
            return False
        except Exception as e:
            print(f"[WS ERROR] Error sending binary message: {e}")
            # traceback.print_exc()
            return False
    
    def _handle_send_disconnect(self, reason):
        """Helper to manage state when send fails due to disconnection."""
        print(f"[WS] Handling disconnection during send: {reason}")
        self.is_connected = False
        # Trigger the disconnect signal so AppController knows
        self.disconnected_signal.emit(reason)
        # The _run loop should detect the closure and handle reconnection attempts.
    
    # --- Specific Message Sending Methods (Convenience wrappers) --- 
    
    def _register_user(self):
        """Send the initial registration message to the server."""
        # TODO (Backend): Backend needs to handle `register` message type.
        # It should associate the username with this WebSocket connection.
        if self._pending_registration:
            print("[WS] Registration already pending")
            return
        
        if not self.ws:
             print("[WS ERROR] Cannot register user, WebSocket not initialized.")
             return
        
        print(f"[WS] Attempting to register user: {self.username}")
        self._pending_registration = True
        message = {
            "type": "register",
            "username": self.username
            # TODO (Backend): Add token here if WS needs auth: "token": self.jwt_token (requires passing token to __init__)
        }
        # Use internal send method which uses the lock
        if not self.send_message(message):
             print("[WS ERROR] Failed to send registration message.")
             # What happens now? Connection might be dead. _run loop should handle it.
             self._pending_registration = False # Allow retry if connection comes back
    
    # --- Methods below are examples of how AppController *could* interact --- 
    # --- AppController currently uses send_message directly for these --- 
    
    # def request_connection(self, target_username):
    #     """Request a connection to another user."""
    #     # TODO (Backend): Handle `request_connection` {to_user}
    #     message = {
    #         "type": "request_connection",
    #         "to_user": target_username
    #         # Backend infers sender from connection
    #     }
    #     return self.send_message(message)
    
    # def accept_connection(self, from_username):
    #     """Accept a connection request from another user."""
    #     # TODO (Backend): Handle `connection_response` {to_user, accepted: true}
    #     message = {
    #         "type": "connection_response",
    #         "to_user": from_username,
    #         "accepted": True
    #     }
    #     return self.send_message(message)
    
    # def reject_connection(self, from_username, reason="Connection rejected"):
    #     """Reject a connection request from another user."""
    #     # TODO (Backend): Handle `connection_response` {to_user, accepted: false, reason}
    #     message = {
    #         "type": "connection_response",
    #         "to_user": from_username,
    #         "accepted": False,
    #         "reason": reason
    #     }
    #     return self.send_message(message)
    
    # def disconnect_from_peer(self):
    #     """Disconnect from the current peer."""
    #     # TODO (Backend): Handle `disconnect_peer` {no target needed, backend knows sender/peer}
    #     message = {
    #         "type": "disconnect_peer"
    #     }
    #     return self.send_message(message)
    
    # def send_chat_message(self, to_username, text):
    #     """Send a chat message to another user."""
    #     # TODO (Backend): Handle `chat_message` {to_user, text}
    #     message = {
    #         "type": "chat_message",
    #         "to_user": to_username,
    #         "text": text
    #     }
    #     return self.send_message(message)
    
    # def send_input_event(self, to_username, event_data):
    #     """Send an input event to another user."""
    #     # TODO (Backend): Handle `input_event` {to_user, event}
    #     # Backend MUST verify permission before relaying.
    #     message = {
    #         "type": "input_event",
    #         "to_user": to_username,
    #         "event": event_data
    #     }
    #     return self.send_message(message)
    
    # Sending binary data (like screen frames) uses send_binary_message directly.
    # def send_screen_frame(self, to_username, frame_data):
    #     # Backend doesn't receive a JSON message for this, just raw bytes.
    #     # It needs to know which peer to send it to based on established connection.
    #     return self.send_binary_message(frame_data) 