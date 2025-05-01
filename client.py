import socket
import threading
from PyQt5.QtCore import QObject, pyqtSignal, QThread

# Assuming utils.py and ui.py are in the same directory
import utils

class ClientReceiver(QObject):
    """Worker object to handle receiving data in a separate thread."""
    screen_update_signal = pyqtSignal(bytes) # Emits raw image data
    cursor_update_signal = pyqtSignal(int, int) # Emits x, y coordinates
    disconnected_signal = pyqtSignal(str) # Emits disconnection reason
    status_update_signal = pyqtSignal(str) # Emits status messages

    def __init__(self, client_socket):
        super().__init__()
        self.client_socket = client_socket
        self._running = False

    def run(self):
        """Receives data from the server."""
        self._running = True
        print("[*] Client receiver thread started.")
        while self._running:
            try:
                data = utils.recv_data(self.client_socket)
                if data is None:
                    # Connection closed by server or error during receive
                    if self._running: # Avoid signaling if stopped intentionally
                        self.status_update_signal.emit("Disconnected by host or network error.")
                        self.disconnected_signal.emit("Host disconnected")
                    break

                # Process received data based on its type
                data_type = data.get('type')
                if data_type == 'screen':
                    image_data = data.get('image')
                    if image_data:
                        self.screen_update_signal.emit(image_data)
                elif data_type == 'cursor':
                    x = data.get('x')
                    y = data.get('y')
                    if x is not None and y is not None:
                        self.cursor_update_signal.emit(x, y)
                # Add handling for other data types if needed

            except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, EOFError) as e:
                if self._running:
                    print(f"Client Receive Error: Connection lost ({e}).")
                    self.status_update_signal.emit("Disconnected: Connection lost.")
                    self.disconnected_signal.emit(f"Connection error: {e}")
                break # Exit loop on connection error
            except Exception as e:
                if self._running:
                    print(f"Client Receive Error: {e}")
                    self.status_update_signal.emit(f"Error: {e}")
                    self.disconnected_signal.emit(f"Receive error: {e}")
                break # Exit loop on other errors

        self._running = False
        print("[*] Client receiver thread finished.")
        # Ensure disconnect signal is emitted if loop exits unexpectedly while running
        # (This might be redundant depending on where the disconnect signal originates)
        # if self._running:
        #    self.disconnected_signal.emit("Receiver loop exited unexpectedly")


    def stop(self):
        """Signals the receiver loop to stop."""
        self._running = False
        print("[*] Stopping client receiver...")
        # Closing the socket from the main thread (in Client.disconnect)
        # should interrupt the blocking recv call.


class Client(QObject):
    """Manages the client connection and communication."""
    # Signals for UI updates
    connection_failed_signal = pyqtSignal(str) # Emits error message
    connection_success_signal = pyqtSignal()   # Signals successful connection
    disconnected_signal = pyqtSignal(str)      # Emits reason for disconnection
    screen_update_signal = pyqtSignal(bytes)   # Forwarded from receiver
    cursor_update_signal = pyqtSignal(int, int)# Forwarded from receiver
    status_update_signal = pyqtSignal(str)     # Forwarded from receiver


    def __init__(self, client_window, port=utils.DEFAULT_PORT):
        super().__init__()
        self.client_window = client_window
        self.host_ip = None
        self.port = port # Store the specific port for this client connection
        self.client_socket = None
        self._is_connected = False
        self.receiver_thread = None
        self.receiver_worker = None

    def connect_to_host(self, host_ip):
        """Attempts to connect to the specified host IP (port is stored in self.port)."""
        self.host_ip = host_ip # host_ip is received from the UI input
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            print(f"[*] Attempting to connect to {self.host_ip}:{self.port}...") # Uses self.port correctly
            self.status_update_signal.emit(f"Connecting to {self.host_ip}:{self.port}...") # Use specific port in status
            # The connect call uses host_ip and self.port separately
            self.client_socket.connect((self.host_ip, self.port))
            self._is_connected = True
            print("[*] Connection successful.")
            self.status_update_signal.emit(f"Connected to {self.host_ip}:{self.port}") # Use specific port in status

            # Send initial settings
            initial_settings = self.client_window.get_initial_settings()
            self.send_settings(initial_settings)


            # Start the receiver thread
            self.receiver_worker = ClientReceiver(self.client_socket)
            self.receiver_thread = QThread()
            self.receiver_worker.moveToThread(self.receiver_thread)

            # Connect signals from worker to client's signals (or directly to window slots)
            self.receiver_worker.screen_update_signal.connect(self.screen_update_signal)
            self.receiver_worker.cursor_update_signal.connect(self.cursor_update_signal)
            self.receiver_worker.status_update_signal.connect(self.status_update_signal)
             # Handle disconnection signaled by the worker
            self.receiver_worker.disconnected_signal.connect(self.handle_disconnection)


            # Start the thread and trigger the worker's run method
            self.receiver_thread.started.connect(self.receiver_worker.run)
            self.receiver_thread.start()

            self.connection_success_signal.emit()

        except socket.timeout:
            print(f"Connection Error: Timeout connecting to {self.host_ip}")
            self.status_update_signal.emit("Connection Failed: Timeout")
            self.connection_failed_signal.emit("Connection timed out. Check IP and firewall.")
            self._is_connected = False
            self.cleanup_socket()
        except ConnectionRefusedError:
            print(f"Connection Error: Connection refused by {self.host_ip}")
            self.status_update_signal.emit("Connection Failed: Refused")
            self.connection_failed_signal.emit("Connection refused. Is the host running?")
            self._is_connected = False
            self.cleanup_socket()
        except Exception as e:
            error_msg = f"Connection failed: {e}"
            print(f"Connection Error: {error_msg}")
            self.status_update_signal.emit(f"Connection Failed: {e}")
            self.connection_failed_signal.emit(error_msg)
            self._is_connected = False
            self.cleanup_socket()

    def send_event(self, event_data):
        """Sends mouse or keyboard event data to the host."""
        if self._is_connected and self.client_socket:
            # Add the type ('mouse' or 'key') if not already present
            if 'type' not in event_data:
                 if 'button' in event_data or 'delta_y' in event_data:
                     event_data['type'] = 'mouse'
                 elif 'key' in event_data:
                     event_data['type'] = 'key'
                 else:
                      print("Warning: Unknown event type to send:", event_data)
                      return

            # Prepend 'input' type for the server to distinguish from settings etc.
            # message = {'type': 'input', 'event': event_data} # Or send directly
            message = event_data # Send mouse/key event directly based on server logic

            try:
                utils.send_data(self.client_socket, message)
            except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError) as e:
                 print(f"Send Event Error: Connection lost ({e}). Triggering disconnect.")
                 self.handle_disconnection("Send error: Connection lost")
            except Exception as e:
                print(f"Error sending event data: {e}")
                # Consider disconnecting if sending fails persistently
                self.handle_disconnection(f"Send error: {e}")


    def send_settings(self, settings_data):
        """Sends settings changes (quality, view_only) to the host."""
        if self._is_connected and self.client_socket:
            message = {'type': 'settings', **settings_data}
            try:
                print(f"[*] Sending settings: {message}")
                utils.send_data(self.client_socket, message)
            except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError) as e:
                 print(f"Send Settings Error: Connection lost ({e}). Triggering disconnect.")
                 self.handle_disconnection("Send error: Connection lost")
            except Exception as e:
                print(f"Error sending settings data: {e}")
                self.handle_disconnection(f"Send error: {e}")

    def handle_disconnection(self, reason="Unknown"):
         """Handles disconnection initiated by receiver or send errors."""
         if self._is_connected:
             print(f"[*] Disconnecting due to: {reason}")
             self._is_connected = False # Prevent further sends
             self.disconnect(emit_signal=False) # Clean up resources, don't re-emit signal
             self.disconnected_signal.emit(reason) # Emit the signal to the UI


    def disconnect(self, emit_signal=True):
        """Disconnects from the host and cleans up resources."""
        print("[*] Disconnecting client...")
        # Signal the receiver thread to stop
        if self.receiver_worker:
             self.receiver_worker.stop()

        # Quit and wait for the receiver thread to finish
        if self.receiver_thread:
            if self.receiver_thread.isRunning():
                 self.receiver_thread.quit()
                 if not self.receiver_thread.wait(1000): # Wait max 1 sec
                     print("Warning: Receiver thread did not finish gracefully.")
                     # self.receiver_thread.terminate() # Force terminate if necessary
            self.receiver_thread = None
            self.receiver_worker = None


        self._is_connected = False
        self.cleanup_socket()


        if emit_signal:
            self.disconnected_signal.emit("User disconnected") # Signal UI if user initiated


    def cleanup_socket(self):
        """Closes the socket."""
        if self.client_socket:
            try:
                self.client_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                 pass # Ignore if already closed or not connected
            except Exception as e:
                 print(f"Error shutting down client socket: {e}")

            try:
                self.client_socket.close()
                print("[*] Client socket closed.")
            except Exception as e:
                print(f"Error closing client socket: {e}")
            self.client_socket = None


    def is_connected(self):
        return self._is_connected 