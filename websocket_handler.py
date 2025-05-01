# websocket_handler.py
import websocket # Use websocket-client library
import threading
import json
import time
from PyQt5.QtCore import QObject, pyqtSignal

class WebSocketHandler(QObject):
    """Handles WebSocket connection, message sending/receiving in a separate thread."""

    # Signals for various events
    connected_signal = pyqtSignal()
    disconnected_signal = pyqtSignal(str) # Reason for disconnection
    error_signal = pyqtSignal(str)        # Error message
    message_received_signal = pyqtSignal(dict) # Emits the received dictionary/JSON
    binary_message_received_signal = pyqtSignal(bytes) # Signal for raw binary data
    status_update_signal = pyqtSignal(str) # General status updates

    def __init__(self, ws_url, token):
        super().__init__()
        self.ws_url = self._prepare_ws_url(ws_url, token) # Prepare URL (e.g., add token)
        self.token = token
        self.ws = None
        self.thread = None
        self._is_running = False
        self._connection_established = False

    def _prepare_ws_url(self, http_url, token):
        """Converts HTTP URL to WS URL and potentially appends token."""
        # Basic conversion, adjust based on actual backend endpoint
        if http_url.startswith("https://"):
            ws_base = http_url.replace("https://", "wss://", 1)
        else:
            ws_base = http_url.replace("http://", "ws://", 1)

        # Append /ws or similar path as expected by backend
        # Example: ws://127.0.0.1:8000/ws/session
        # Example with token in path: ws://127.0.0.1:8000/ws/{token}
        # **Adjust this logic based on your backend's WebSocket endpoint structure**
        ws_endpoint = f"{ws_base}/ws/connect" # Example endpoint path
        print(f"Prepared WebSocket URL: {ws_endpoint}")
        return ws_endpoint
        # If token needs to be in header, it's added in _connect


    def connect_ws(self):
        """Connects to the WebSocket server in a separate thread."""
        if self._is_running:
            print("WebSocket connection already running or attempting.")
            return

        print(f"Attempting to connect WebSocket to {self.ws_url}")
        self.status_update_signal.emit("WebSocket: Connecting...")
        self._is_running = True
        self._connection_established = False # Reset flag

        # Start the connection in a separate thread
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        """Runs the WebSocketApp loop."""
        try:
            # Add token header if needed (adjust based on backend)
            headers = {f"Authorization": f"Bearer {self.token}"}

            self.ws = websocket.WebSocketApp(
                self.ws_url,
                header=headers, # Send token in header
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close
            )
            # run_forever will block this thread until connection closes
            # Increase timeout slightly for testing robustness
            self.ws.run_forever(ping_interval=20, ping_timeout=15)

        except Exception as e:
            print(f"WebSocket _run exception: {e}")
            self.status_update_signal.emit(f"WebSocket Error: {e}")
            self.error_signal.emit(str(e))
            self._is_running = False
            self._connection_established = False
            # Ensure disconnect signal if loop crashes before on_close
            self.disconnected_signal.emit(f"Connection failed: {e}")


        print("WebSocket thread finished.")
        # This part runs after run_forever returns (connection closed)
        self._is_running = False
        self._connection_established = False
        # on_close should have emitted the disconnected_signal already

    # --- WebSocket Callbacks ---
    # These run in the WebSocket thread

    def _on_open(self, ws):
        """Callback when WebSocket connection is established."""
        print("WebSocket connection opened.")
        self._connection_established = True
        self.status_update_signal.emit("WebSocket: Connected")
        self.connected_signal.emit()
        # Optional: Send an initial message (e.g., identify user or request connection)
        # self.send_message({'type': 'auth', 'token': self.token}) # Example

    def _on_message(self, ws, message):
        """Callback when a message is received. Differentiates text/binary."""
        if isinstance(message, bytes):
            # print(f"Received Binary Message: {len(message)} bytes")
            self.binary_message_received_signal.emit(message)
        elif isinstance(message, str):
            # Assume text messages are JSON
            # print(f"Raw Text Message Received: {message[:100]}...")
            try:
                data = json.loads(message)
                self.message_received_signal.emit(data)
            except json.JSONDecodeError:
                print(f"Received non-JSON text message: {message}")
            except Exception as e:
                print(f"Error processing text message: {e}")
        else:
            print(f"Received unexpected message type: {type(message)}")

    def _on_error(self, ws, error):
        """Callback when a WebSocket error occurs."""
        print(f"WebSocket Error: {error}")
        self.status_update_signal.emit(f"WebSocket Error: {error}")
        self.error_signal.emit(str(error))
        # Note: on_close usually gets called after an error too.

    def _on_close(self, ws, close_status_code, close_msg):
        """Callback when WebSocket connection is closed."""
        close_reason = f"Code: {close_status_code}, Msg: {close_msg}"
        print(f"WebSocket connection closed: {close_reason}")
        self._is_running = False # Ensure flag is reset
        # Only emit disconnected signal if it wasn't already closed intentionally via stop()
        # or if the connection was actually established.
        if self._connection_established:
            self.status_update_signal.emit(f"WebSocket: Disconnected ({close_reason})")
            self.disconnected_signal.emit(close_reason)
        else:
             # If it never opened, treat as a connection failure handled in _run exception
            self.status_update_signal.emit(f"WebSocket: Connection Attempt Failed ({close_reason})")
            # self.disconnected_signal.emit(f"Connection failed ({close_reason})") # Redundant with error handling in _run

        self._connection_established = False # Reset flag

    # --- Public Methods ---

    def send_message(self, data):
        """Sends a dictionary (as JSON string) over the WebSocket."""
        if self.ws and self._is_running and self._connection_established:
            try:
                message = json.dumps(data)
                self.ws.send(message, websocket.ABNF.OPCODE_TEXT) # Specify TEXT frame
            except Exception as e:
                print(f"Error sending text message: {e}")
                self.status_update_signal.emit(f"WebSocket Send Error: {e}")
                self.stop()
        else:
            print("Cannot send text message: WebSocket is not connected or running.")
            self.status_update_signal.emit("WebSocket: Cannot send, not connected.")

    def send_binary_message(self, data_bytes):
        """Sends raw bytes over the WebSocket."""
        if self.ws and self._is_running and self._connection_established:
            try:
                self.ws.send(data_bytes, websocket.ABNF.OPCODE_BINARY) # Specify BINARY frame
            except Exception as e:
                print(f"Error sending binary message: {e}")
                self.status_update_signal.emit(f"WebSocket Send Error: {e}")
                self.stop()
        else:
            print("Cannot send binary message: WebSocket is not connected or running.")
            self.status_update_signal.emit("WebSocket: Cannot send, not connected.")

    def stop(self):
        """Closes the WebSocket connection."""
        if self._is_running:
            print("Stopping WebSocket connection...")
            self._is_running = False # Signal intention to stop
            if self.ws:
                try:
                    self.ws.close()
                except Exception as e:
                     print(f"Error closing WebSocket: {e}")
            # Don't wait for thread join here, let on_close handle cleanup
        # else: print("WebSocket already stopped.") # Optional debug


    def is_connected(self):
        """Checks if the WebSocket connection is established."""
        return self._is_running and self._connection_established 