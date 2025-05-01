import socket
import threading
import time
import pyautogui
from PyQt5.QtCore import QObject, pyqtSignal

# Assuming utils.py and ui.py are in the same directory
import utils

# --- Server Worker Thread ---
class ServerWorker(threading.Thread):
    """Handles a single client connection: sends screen, receives input."""

    def __init__(self, client_socket, client_address, status_callback, disconnect_callback):
        super().__init__()
        self.client_socket = client_socket
        self.client_address = client_address
        self.status_callback = status_callback # Function to update UI status
        self.disconnect_callback = disconnect_callback # Function to call when client disconnects
        self._running = True
        self.quality = utils.DEFAULT_QUALITY # Initial quality
        self.view_only = False # Initial control mode
        self.screen_width, self.screen_height = pyautogui.size() # Host screen dimensions

        # Separate threads for sending screen and receiving input
        self.send_thread = threading.Thread(target=self._send_screen, daemon=True)
        self.recv_thread = threading.Thread(target=self._receive_input, daemon=True)

        print(f"[*] Worker created for {self.client_address}")

    def run(self):
        """Starts the screen sending and input receiving threads."""
        self.status_callback(f"Connected to Client: {self.client_address[0]}")
        self.send_thread.start()
        self.recv_thread.start()

        # Keep the worker thread alive while sub-threads are running
        self.send_thread.join()
        self.recv_thread.join()

        # Clean up when threads finish (e.g., due to error or stop signal)
        print(f"[*] Worker threads for {self.client_address} finished.")
        self.cleanup()
        self.disconnect_callback(self.client_address) # Notify main server


    def _send_screen(self):
        """Continuously captures and sends screen updates."""
        while self._running:
            try:
                screenshot = utils.capture_screenshot(quality=self.quality)
                if screenshot:
                    # Send screen data with a header indicating it's an image
                    data_to_send = {'type': 'screen', 'image': screenshot}
                    utils.send_data(self.client_socket, data_to_send)
                else:
                    print("Error capturing screenshot, stopping send loop.")
                    self._running = False # Stop if capture fails persistently
                    break
                time.sleep(1/15) # Aim for ~15 FPS, adjust as needed
            except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, EOFError) as e:
                print(f"Send Screen Error: Connection lost ({e}).")
                self._running = False
            except Exception as e:
                print(f"Send Screen Error: {e}")
                self._running = False # Stop on other errors too
        print("[*] Send screen loop terminated.")


    def _receive_input(self):
        """Receives and processes input events or settings from the client."""
        while self._running:
            try:
                data = utils.recv_data(self.client_socket)
                if data is None:
                    print("Receive Input Error: Connection closed by client.")
                    self._running = False
                    break # Exit loop if connection is closed

                event_type = data.get('type')

                if event_type == 'settings':
                    self.quality = data.get('quality', self.quality)
                    self.view_only = data.get('view_only', self.view_only)
                    print(f"[*] Settings updated: Quality={self.quality}, ViewOnly={self.view_only}")
                elif not self.view_only: # Only process if not in view-only mode
                    if event_type == 'mouse':
                        utils.simulate_mouse_event(data, self.screen_width, self.screen_height)
                        # Send back cursor position for client to draw
                        try:
                           cursor_x, cursor_y = pyautogui.position()
                           cursor_data = {'type': 'cursor', 'x': cursor_x, 'y': cursor_y}
                           utils.send_data(self.client_socket, cursor_data)
                        except Exception as cursor_e:
                            print(f"Failed to get/send cursor position: {cursor_e}")

                    elif event_type == 'key':
                        utils.simulate_keyboard_event(data)
                    # else: ignore unknown types

            except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, EOFError) as e:
                print(f"Receive Input Error: Connection lost ({e}).")
                self._running = False
            except Exception as e:
                print(f"Receive Input Error: {e}")
                self._running = False # Stop on other errors
        print("[*] Receive input loop terminated.")

    def stop(self):
        """Signals the worker and its threads to stop."""
        print(f"[*] Stopping worker for {self.client_address}...")
        self._running = False
        # No need to explicitly join here as the run method handles joining.
        # Closing the socket might help interrupt blocking calls in threads.
        self.cleanup()


    def cleanup(self):
        """Closes the client socket."""
        try:
            self.client_socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass # Ignore if socket is already closed/invalid
        except Exception as e:
             print(f"Error shutting down socket: {e}")

        try:
            self.client_socket.close()
            print(f"[*] Client socket {self.client_address} closed.")
        except Exception as e:
            print(f"Error closing client socket: {e}")


# --- Main Server Logic ---
class Server(QObject):
    """Manages the server socket and client connections."""
    status_update_signal = pyqtSignal(str) # Signal to update UI

    def __init__(self, host_window, port=utils.DEFAULT_PORT):
        super().__init__()
        self.host_window = host_window
        self.host_ip = utils.get_local_ip()
        self.port = port # Use provided port
        self.server_socket = None
        self._is_running = False
        self.server_thread = None # Thread for the main accept loop
        self.client_handler = None # Holds the current ServerWorker instance

    def start(self):
        """Starts the server listening thread."""
        if self._is_running:
            print("Server already running.")
            return
        print(f"Starting server on {self.host_ip}:{self.port}")
        self._is_running = True
        self.server_thread = threading.Thread(target=self._run_server, daemon=True)
        self.server_thread.start()

    def _run_server(self):
        """Binds, listens, and accepts client connections."""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # Allow reusing address shortly after closing
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host_ip, self.port))
            self.server_socket.listen(1) # Listen for one connection at a time
            self.server_socket.settimeout(1.0) # Timeout for accept() to allow checking _is_running
            self.update_status(f"Hosting on {self.host_ip}:{self.port}\nWaiting for connection...")
            print("[*] Server listening...")
        except Exception as e:
            error_msg = f"Server Error: Failed to start listening ({e})"
            print(error_msg)
            self.update_status(error_msg)
            self._is_running = False
            if self.server_socket:
                self.server_socket.close()
            return # Stop the thread if setup failed

        while self._is_running:
            try:
                # Wait for a connection with timeout
                conn, addr = self.server_socket.accept()
                print(f"[*] Accepted connection from {addr}")

                # If another client is already connected, disconnect them first
                if self.client_handler and self.client_handler.is_alive():
                    print("[*] Disconnecting previous client...")
                    self.client_handler.stop()
                    # Give previous worker a moment to clean up (optional)
                    # self.client_handler.join(timeout=0.5)
                    self.client_handler = None

                # Create and start a new worker for the connected client
                self.client_handler = ServerWorker(conn, addr, self.update_status, self._handle_client_disconnect)
                self.client_handler.start()

            except socket.timeout:
                # Just loop again if accept timed out, checking self._is_running
                continue
            except OSError as e:
                 # Socket might have been closed by stop()
                 if self._is_running:
                     print(f"Server socket error: {e}")
                 break # Exit loop if socket is closed or error occurs
            except Exception as e:
                if self._is_running: # Avoid error message if stopped intentionally
                    print(f"Server Accept Error: {e}")
                break # Exit loop on other errors

        # --- Server loop finished ---
        if self.client_handler and self.client_handler.is_alive():
            self.client_handler.stop()
            # self.client_handler.join(timeout=1.0) # Optional wait

        if self.server_socket:
             try:
                 self.server_socket.close()
                 print("[*] Server socket closed.")
             except Exception as e:
                  print(f"Error closing server socket: {e}")

        self.server_socket = None
        self.client_handler = None
        self._is_running = False
        self.update_status("Server Stopped")
        print("[*] Server stopped.")


    def stop(self):
        """Stops the server and disconnects any client."""
        if not self._is_running:
            return
        print("[*] Stopping server...")
        self._is_running = False # Signal the server loop to stop

        # Closing the server socket will interrupt the blocking accept() call
        if self.server_socket:
            try:
                # Shutdown might not be needed if close handles it
                # self.server_socket.shutdown(socket.SHUT_RDWR)
                self.server_socket.close()
            except Exception as e:
                print(f"Error closing server socket during stop: {e}")

        # Wait briefly for the server thread to finish (optional, avoid blocking UI for too long)
        # if self.server_thread and self.server_thread.is_alive():
        #     self.server_thread.join(timeout=1.0)


    def _handle_client_disconnect(self, address):
        """Callback when a client worker finishes/disconnects."""
        print(f"[*] Client {address} disconnected.")
        self.update_status(f"Client {address[0]} Disconnected.\nWaiting for connection...")
        if self.client_handler and self.client_handler.client_address == address:
             self.client_handler = None # Clear the handler reference


    def update_status(self, message):
        """Emits the status update signal to the UI thread."""
        try:
            self.status_update_signal.emit(message)
        except RuntimeError:
             print("RuntimeError: Cannot emit signal from non-GUI thread directly (or window closed). Status:", message)
        except Exception as e:
             print(f"Error emitting status signal: {e}") 