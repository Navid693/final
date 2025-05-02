# websocket_handler.py
import websocket # Use websocket-client library
import threading
import json
import time
import traceback
from PyQt5.QtCore import QObject, pyqtSignal

class WebSocketHandler(QObject):
    """Handles WebSocket connections and messaging to the remote server."""
    
    # Connection signals
    connected_signal = pyqtSignal()
    disconnected_signal = pyqtSignal(str)  # reason
    error_signal = pyqtSignal(str)  # error message
    
    # Message signals
    message_received_signal = pyqtSignal(dict)  # JSON message
    binary_message_received_signal = pyqtSignal(bytes)  # Binary data
    status_update_signal = pyqtSignal(str)  # Status message for UI
    
    # New signals for the updated server API
    user_registered_signal = pyqtSignal(bool, str)  # success, message
    users_list_updated_signal = pyqtSignal(list)  # List of usernames
    peer_connection_requested_signal = pyqtSignal(str)  # requesting username
    peer_connected_signal = pyqtSignal(str)  # connected username
    peer_disconnected_signal = pyqtSignal(str, str)  # username, reason
    chat_message_received_signal = pyqtSignal(str, str)  # sender, message
    
    def __init__(self, base_url, username):
        """Initialize WebSocket handler with the base server URL and username."""
        super().__init__()
        
        # Construct WebSocket URL from base URL
        if base_url.startswith("https://"):
            ws_scheme = "wss://"
            http_scheme = "https://"
        elif base_url.startswith("http://"):
            ws_scheme = "ws://"
            http_scheme = "http://"
        else:
            # Attempt a default guess or raise error if scheme is missing/invalid
            print(f"[WS WARNING] Invalid or missing scheme in base URL: {base_url}. Assuming ws://")
            ws_scheme = "ws://"
            # Or raise ValueError("Invalid base URL scheme")

        # Remove http(s):// prefix and potential trailing slash
        domain_part = base_url.replace(http_scheme, "", 1).rstrip('/')
        self.ws_url = f"{ws_scheme}{domain_part}/ws" # Append common WebSocket path

        self.username = username
        self.ws = None
        self.is_running = False
        self.is_connected = False
        self.ws_thread = None
        self.connect_lock = threading.Lock()
        self.send_lock = threading.Lock()
        self._pending_registration = False
        self._retry_count = 0
        self._max_retries = 3
        
        # Track current connected peer
        self.current_peer = None
        
    def connect_ws(self):
        """Establish a WebSocket connection to the server."""
        with self.connect_lock:
            if self.is_running:
                print("[WS] Already running, ignoring connect request")
                return
                
            self.is_running = True
            self._retry_count = 0
            
            # Start WebSocket thread
            self.ws_thread = threading.Thread(target=self._run, daemon=True)
            self.ws_thread.start()
    
    def stop(self):
        """Stop the WebSocket connection."""
        with self.connect_lock:
            if not self.is_running:
                return
                
            self.is_running = False
            
            # Close WebSocket if it exists
            if self.ws:
                try:
                    self.ws.close()
                except Exception as e:
                    print(f"[WS] Error closing WebSocket: {e}")
                    
            # Wait for thread to end
            if self.ws_thread and self.ws_thread.is_alive():
                self.ws_thread.join(2.0)
    
    def _run(self):
        """WebSocket connection loop running in a separate thread."""
        while self.is_running:
            try:
                # Connect to WebSocket server
                print(f"[WS] Connecting to {self.ws_url}...")
                self.status_update_signal.emit(f"Connecting to server...")
                
                # Define WebSocket callbacks
                self.ws = websocket.WebSocketApp(
                    self.ws_url,
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                    on_ping=self._on_ping,
                    on_pong=self._on_pong
                )
                
                # Run WebSocket client (blocking call)
                self.ws.run_forever(ping_interval=30, ping_timeout=5)
                
                # If we get here, the connection was closed
                if not self.is_running:
                    # Clean exit requested
                    break
                    
                # Attempt to reconnect
                self._retry_count += 1
                if self._retry_count > self._max_retries:
                    print(f"[WS] Max retries ({self._max_retries}) exceeded. Giving up.")
                    self.status_update_signal.emit("Connection failed. Retry manually.")
                    self.error_signal.emit(f"Failed to connect after {self._max_retries} attempts")
                    break
                    
                retry_delay = min(30, 2 ** self._retry_count)  # Exponential backoff
                print(f"[WS] Reconnecting in {retry_delay} seconds...")
                self.status_update_signal.emit(f"Connection lost. Retry in {retry_delay}s...")
                time.sleep(retry_delay)
                
            except Exception as e:
                print(f"[WS] Error in WebSocket thread: {e}")
                traceback.print_exc()
                if self.is_running:
                    self.error_signal.emit(f"WebSocket error: {str(e)}")
                    time.sleep(5)  # Wait before retry
                else:
                    break
                    
        print("[WS] WebSocket thread terminated")
        self.is_connected = False
    
    def is_connected(self):
        """Check if WebSocket is connected."""
        return self.is_connected
    
    def _on_open(self, ws):
        """Called when WebSocket connection is established."""
        print("[WS] WebSocket connection opened")
        self.is_connected = True
        self.connected_signal.emit()
        self.status_update_signal.emit("Connected to server")
        self._retry_count = 0  # Reset retry counter on successful connection
        
        # Register the user with the server
        self._register_user()
    
    def _on_message(self, ws, message):
        """Called when a message is received from the WebSocket."""
        try:
            # Check if this is binary data
            if isinstance(message, bytes):
                # For large binary messages, just log the size, not detailed info
                data_size_kb = len(message) / 1024
                print(f"[WS] Received binary data: {data_size_kb:.1f} KB")
                self.binary_message_received_signal.emit(message)
                return
                
            # Handle text messages (JSON)
            data = json.loads(message)
            msg_type = data.get("type", "unknown")
            
            # Handle ping message from server to keep connection alive
            if msg_type == "ping":
                print("[WS] Received ping from server, sending pong")
                self.send_message({"type": "pong"})
                return
                
            print(f"[WS] Received message: {msg_type}")
            
            # Process message based on type
            if msg_type == "register_response":
                success = data.get("success", False)
                message = data.get("message", "")
                self._pending_registration = False
                self.user_registered_signal.emit(success, message)
                
            elif msg_type == "users_list":
                users = data.get("users", [])
                self.users_list_updated_signal.emit(users)
                
            elif msg_type == "connection_request":
                requester = data.get("from_user")
                if requester:
                    self.peer_connection_requested_signal.emit(requester)
                
            elif msg_type == "connection_response":
                accepted = data.get("accepted", False)
                from_user = data.get("from_user")
                reason = data.get("reason", "")
                
                if accepted:
                    self.current_peer = from_user  # Set current peer when connection accepted
                    self.peer_connected_signal.emit(from_user)
                else:
                    self.peer_disconnected_signal.emit(from_user, f"Connection rejected: {reason}")
                
            elif msg_type == "peer_disconnected":
                peer = data.get("peer")
                reason = data.get("reason", "Peer disconnected")
                if peer == self.current_peer:
                    self.current_peer = None  # Clear current peer when disconnected
                self.peer_disconnected_signal.emit(peer, reason)
                
            elif msg_type == "chat_message":
                sender = data.get("from_user")
                text = data.get("text", "")
                self.chat_message_received_signal.emit(sender, text)
                
            # Also emit the generic message signal for other handlers
            self.message_received_signal.emit(data)
                
        except json.JSONDecodeError:
            print("[WS] Received non-JSON message")
        except Exception as e:
            print(f"[WS] Error processing message: {e}")
            import traceback
            traceback.print_exc()
    
    def _on_binary_message(self, ws, data):
        """Called when binary data is received from the WebSocket."""
        try:
            # Emit signal with the binary data
            self.binary_message_received_signal.emit(data)
        except Exception as e:
            print(f"[WS] Error processing binary message: {e}")
            traceback.print_exc()
    
    def _on_error(self, ws, error):
        """Called when a WebSocket error occurs."""
        print(f"[WS] WebSocket error: {error}")
        self.error_signal.emit(str(error))
    
    def _on_close(self, ws, close_status_code, close_msg):
        """Called when WebSocket connection is closed."""
        print(f"[WS] WebSocket closed: {close_status_code} - {close_msg}")
        self.is_connected = False
        self.disconnected_signal.emit(f"Connection closed: {close_msg}")
    
    def _on_ping(self, ws, data):
        """Called when a ping is received."""
        print("[WS] Ping received")
    
    def _on_pong(self, ws, data):
        """Called when a pong is received."""
        print("[WS] Pong received")
    
    def send_message(self, message):
        """Send a JSON message to the WebSocket server."""
        if not self.is_connected or not self.ws:
            print("[WS] Cannot send message: Not connected")
            return False
            
        try:
            with self.send_lock:
                message_json = json.dumps(message)
                self.ws.send(message_json)
                return True
        except Exception as e:
            print(f"[WS] Error sending message: {e}")
            return False
    
    def send_binary_message(self, data):
        """Send binary data to the WebSocket server."""
        if not self.is_connected or not self.ws:
            print("[WS] Cannot send binary message: Not connected")
            return False
            
        try:
            # Get data size in KB for logging
            data_size_kb = len(data) / 1024
            
            with self.send_lock:
                # Use a timeout to prevent blocking forever
                try:
                    # Send with opcode for binary data
                    self.ws.send(data, websocket.ABNF.OPCODE_BINARY)
                    
                    # Log large frames or if debug is enabled
                    if data_size_kb > 500:  # Log if larger than 500KB
                        print(f"[WS] Large binary message sent ({data_size_kb:.1f} KB)")
                    
                    return True
                except websocket.WebSocketConnectionClosedException:
                    print(f"[WS] Connection closed while sending binary message ({data_size_kb:.1f} KB)")
                    self.is_connected = False
                    # Signal disconnection to restart if needed
                    self.disconnected_signal.emit("Connection closed while sending data")
                    return False
                except Exception as e:
                    print(f"[WS] Error sending binary message: {e}")
                    # More detailed error information
                    import traceback
                    traceback.print_exc()
                    return False
        except Exception as e:
            print(f"[WS] Unexpected error in send_binary_message: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _register_user(self):
        """Register the user with the server."""
        if self._pending_registration:
            print("[WS] Registration already pending")
            return
            
        self._pending_registration = True
        message = {
            "type": "register",
            "username": self.username
        }
        self.send_message(message)
        print(f"[WS] Sent registration request for user {self.username}")
    
    def request_connection(self, target_username):
        """Request a connection to another user."""
        message = {
            "type": "request_connection",
            "to_user": target_username
        }
        success = self.send_message(message)
        if success:
            # Set temporarily, will be confirmed when we get the connection_response
            self.current_peer = target_username
        print(f"[WS] Requested connection to {target_username}: {'Sent' if success else 'Failed'}")
        return success
    
    def accept_connection(self, from_username):
        """Accept a connection request from another user."""
        message = {
            "type": "connection_response",
            "to_user": from_username,
            "accepted": True
        }
        success = self.send_message(message)
        if success:
            self.current_peer = from_username  # Set current peer when we accept a connection
        print(f"[WS] Accepted connection from {from_username}: {'Sent' if success else 'Failed'}")
        return success
    
    def reject_connection(self, from_username, reason="Connection rejected"):
        """Reject a connection request from another user."""
        message = {
            "type": "connection_response",
            "to_user": from_username,
            "accepted": False,
            "reason": reason
        }
        success = self.send_message(message)
        print(f"[WS] Rejected connection from {from_username}: {'Sent' if success else 'Failed'}")
        return success
    
    def disconnect_from_peer(self):
        """Disconnect from the current peer."""
        message = {
            "type": "disconnect_peer"
        }
        success = self.send_message(message)
        if success:
            self.current_peer = None  # Clear current peer on disconnect
        print(f"[WS] Sent disconnect request: {'Sent' if success else 'Failed'}")
        return success
    
    def send_chat_message(self, to_username, text):
        """Send a chat message to another user."""
        message = {
            "type": "chat_message",
            "to_user": to_username,
            "text": text
        }
        success = self.send_message(message)
        print(f"[WS] Sent chat message to {to_username}: {'Sent' if success else 'Failed'}")
        return success
    
    def send_screen_frame(self, to_username, frame_data):
        """Send a screen frame to another user."""
        message = {
            "type": "screen_frame",
            "to_user": to_username,
            "data": frame_data
        }
        success = self.send_message(message)
        return success
    
    def send_input_event(self, to_username, event_data):
        """Send an input event to another user."""
        message = {
            "type": "input_event",
            "to_user": to_username,
            "event": event_data
        }
        success = self.send_message(message)
        return success 