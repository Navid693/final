import threading
import time
import json
import base64
import io
from PyQt5.QtCore import QObject, pyqtSignal, Qt, QTimer
from PyQt5.QtGui import QImage, QPixmap
import pyautogui
import screeninfo
from PIL import ImageGrab, Image

class RemoteController(QObject):
    """
    Handles screen sharing and remote control between peers.
    This class captures the screen, sends mouse/keyboard events,
    and processes incoming events from the remote peer.
    """
    
    # Signals
    screen_captured_signal = pyqtSignal(bytes)  # Emits captured screen as bytes
    screen_share_status_signal = pyqtSignal(bool)  # Indicates if sharing is active
    fps_updated_signal = pyqtSignal(float)  # Actual FPS for statistics
    error_signal = pyqtSignal(str)  # Error messages
    
    def __init__(self, websocket_handler):
        super().__init__()
        self.ws_handler = websocket_handler
        
        # Screen sharing state
        self._is_sharing = False
        self._screen_thread = None
        self._stop_sharing_flag = threading.Event()
        
        # Screen sharing settings
        self.quality = 75  # JPEG quality (0-100)
        self.scale_factor = 0.75  # Scale factor (0.25-1.0)
        self.fps = 15      # Target frames per second
        self.monitor_index = 0  # 0-based index
        
        # Metrics for FPS calculation
        self._frame_count = 0
        self._last_fps_time = 0
        self._current_fps = 0
        
        # Debug settings
        self._debug = True
        self._log_prefix = "[Remote] "
        
        # Connect to websocket signals
        self.ws_handler.message_received_signal.connect(self._handle_message)
        self.ws_handler.binary_message_received_signal.connect(self._handle_binary_message)
        self.ws_handler.disconnected_signal.connect(self._on_ws_disconnected)
        
        # Create FPS update timer
        self._fps_timer = QTimer(self)
        self._fps_timer.setInterval(1000)  # Update every second
        self._fps_timer.timeout.connect(self._update_fps_display)
        
        self._log("RemoteController initialized")
        
    def _log(self, message, level="info"):
        """Log a message with the specified level."""
        if not self._debug and level != "error":
            return
            
        prefix = self._log_prefix
        
        if level == "error":
            print(f"{prefix}ERROR: {message}")
        elif level == "warning":
            print(f"{prefix}WARNING: {message}")
        elif level == "debug":
            if self._debug:
                print(f"{prefix}DEBUG: {message}")
        else:
            print(f"{prefix}{message}")
            
    # --- Screen Sharing Methods ---
    
    def start_screen_sharing(self, quality=None, scale_factor=None, fps=None, monitor_index=None):
        """Start capturing and sharing the screen."""
        if self._is_sharing:
            self._log("Already sharing screen.", "warning")
            return
        
        # Update settings if provided
        if quality is not None:
            self.quality = quality
        if scale_factor is not None:
            self.scale_factor = scale_factor
        if fps is not None:
            self.fps = fps
        if monitor_index is not None:
            self.monitor_index = monitor_index
            
        self._is_sharing = True
        self._stop_sharing_flag.clear()
        self._frame_count = 0
        self._last_fps_time = time.time()
        
        self._log(f"Starting screen sharing with: Quality={self.quality}, Scale={self.scale_factor}, "
              f"FPS={self.fps}, Monitor={self.monitor_index}")
        
        # Start screen sharing in a separate thread
        self._screen_thread = threading.Thread(target=self._screen_sharing_loop, daemon=True)
        self._screen_thread.start()
        
        # Start FPS timer
        self._fps_timer.start()
        
        # Emit status signal
        self.screen_share_status_signal.emit(True)
        
    def stop_screen_sharing(self):
        """Stop screen sharing."""
        if not self._is_sharing:
            return
            
        self._log("Stopping screen sharing")
        self._stop_sharing_flag.set()
        
        # Wait for thread to finish if it exists
        if self._screen_thread and self._screen_thread.is_alive():
            self._screen_thread.join(2.0)  # Wait up to 2 seconds
            if self._screen_thread.is_alive():
                self._log("Screen sharing thread did not terminate gracefully.", "warning")
                
        # Clean up
        self._screen_thread = None
        self._is_sharing = False
        
        # Stop FPS timer
        self._fps_timer.stop()
        
        # Emit status signal
        self.screen_share_status_signal.emit(False)
    
    def update_sharing_settings(self, quality=None, scale_factor=None, fps=None, monitor_index=None):
        """Update screen sharing settings."""
        if quality is not None:
            self.quality = max(10, min(100, quality))
        
        if scale_factor is not None:
            self.scale_factor = max(0.25, min(1.0, scale_factor))
        
        if fps is not None:
            self.fps = max(1, min(30, fps))
        
        if monitor_index is not None:
            self.monitor_index = monitor_index
        
        self._log(f"Updated sharing settings: Quality={self.quality}%, Scale={self.scale_factor}, FPS={self.fps}")
    
    def _screen_sharing_loop(self):
        """Main loop for capturing and sending screen."""
        try:
            # Get the current peer username from the WebSocket handler
            target_peer = None
            
            # Check if WebSocket handler has current_peer
            if hasattr(self.ws_handler, 'current_peer'):
                target_peer = self.ws_handler.current_peer
                
            # If not, try to get it from a connected_peers list if it exists
            if not target_peer and hasattr(self.ws_handler, 'connected_peers') and self.ws_handler.connected_peers:
                target_peer = self.ws_handler.connected_peers[0]  # Use first connected peer
                
            # If we still don't have a target peer, try to get it from the WebSocket handler directly
            if not target_peer:
                # Try to get peer from connected_to attribute that might exist
                if hasattr(self.ws_handler, 'connected_to') and self.ws_handler.connected_to:
                    target_peer = self.ws_handler.connected_to
            
            if not target_peer:
                self._log("No target peer found for screen sharing.", "warning")
                self.error_signal.emit("No target peer found for screen sharing. Please connect to a peer first.")
                self.stop_screen_sharing()
                return
            else:
                self._log(f"Starting screen sharing to peer: {target_peer}")
            
            frame_count = 0
            error_count = 0
            max_consecutive_errors = 10  # Increased tolerance for errors
            frame_batch = 10  # Log stats every 10 frames
            last_stats_time = time.time()
            
            while not self._stop_sharing_flag.is_set() and self._is_sharing:
                start_time = time.time()
                
                # Check if the peer is still connected
                if hasattr(self.ws_handler, 'current_peer') and not self.ws_handler.current_peer:
                    self._log("Peer disconnected, stopping screen sharing", "warning")
                    self.error_signal.emit("Peer disconnected, stopping screen sharing")
                    break
                
                try:
                    # Capture screen
                    screen_bytes, cursor_pos = self._capture_screen()
                    
                    if screen_bytes:
                        # Emit locally for potential preview
                        self.screen_captured_signal.emit(screen_bytes)
                        
                        # Send binary data to peer
                        success = self.ws_handler.send_binary_message(screen_bytes)
                        
                        if success:
                            # Reset error count on successful send
                            error_count = 0
                            # Update frame count for FPS calculation
                            self._frame_count += 1
                            frame_count += 1
                            
                            # Log performance stats periodically
                            if frame_count % frame_batch == 0:
                                now = time.time()
                                elapsed = now - last_stats_time
                                if elapsed > 0:
                                    batch_fps = frame_batch / elapsed
                                    self._log(f"Sent {frame_count} frames, current FPS: {batch_fps:.1f}", "debug")
                                    last_stats_time = now
                        else:
                            error_count += 1
                            self._log(f"Failed to send frame {frame_count+1}, error count: {error_count}/{max_consecutive_errors}", "warning")
                            # Brief pause on send error
                            time.sleep(0.1)
                    else:
                        error_count += 1
                        self._log(f"No screen data captured, error count: {error_count}/{max_consecutive_errors}", "warning")
                        # Brief pause on capture error
                        time.sleep(0.1)
                    
                    # Stop sharing if too many consecutive errors
                    if error_count >= max_consecutive_errors:
                        self._log(f"Too many consecutive errors ({error_count}), stopping screen sharing", "error")
                        self.error_signal.emit(f"Screen sharing stopped due to {error_count} consecutive errors")
                        break
                        
                except Exception as e:
                    error_count += 1
                    self._log(f"Error in screen capture: {e}", "error")
                    import traceback
                    traceback.print_exc()
                    
                    # More detailed error reporting
                    import sys
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    if exc_traceback:
                        frame = exc_traceback.tb_frame
                        line_no = exc_traceback.tb_lineno
                        self._log(f"Error at line {line_no} in {frame.f_code.co_filename}", "error")
                    
                    # Stop sharing if too many consecutive errors
                    if error_count >= max_consecutive_errors:
                        self._log(f"Too many consecutive errors ({error_count}), stopping screen sharing", "error")
                        self.error_signal.emit(f"Screen sharing stopped due to consecutive errors: {e}")
                        break
                    
                    # Delay on error to prevent rapid retry
                    time.sleep(0.5)
                
                # Calculate sleep time to maintain target FPS
                elapsed = time.time() - start_time
                sleep_time = max(0, (1.0 / self.fps) - elapsed)
                
                if sleep_time > 0:
                    # Use short waits to check for stop flag more frequently
                    small_sleep = 0.05  # 50ms chunks
                    chunks = int(sleep_time / small_sleep)
                    
                    for _ in range(chunks):
                        if self._stop_sharing_flag.is_set():
                            break
                        time.sleep(small_sleep)
                        
                    # Sleep any remaining time
                    remainder = sleep_time - (chunks * small_sleep)
                    if remainder > 0 and not self._stop_sharing_flag.is_set():
                        time.sleep(remainder)
            
            self._log(f"Screen sharing loop ended. Frames sent: {frame_count}")
            
        except Exception as e:
            self._log(f"Fatal screen sharing error: {e}", "error")
            self.error_signal.emit(f"Screen sharing error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._is_sharing = False
            self.screen_share_status_signal.emit(False)
            self._log("Screen sharing thread stopped.")
    
    def _get_monitor_by_index(self, index):
        """Get monitor info by index."""
        try:
            monitors = screeninfo.get_monitors()
            
            if not monitors:
                self._log("No monitors detected", "warning")
                return None
            
            self._log(f"Found {len(monitors)} monitors: {[f'{m.name} ({m.width}x{m.height})' for m in monitors]}", "debug")
                
            # Check if the requested index is valid
            if 0 <= index < len(monitors):
                monitor = monitors[index]
                self._log(f"Selected monitor {index}: {monitor.name} ({monitor.width}x{monitor.height}) at ({monitor.x},{monitor.y})", "debug")
                return monitor
            # If invalid index, fall back to primary monitor
            elif monitors:
                primary = next((m for m in monitors if getattr(m, 'is_primary', False)), monitors[0])
                self._log(f"Invalid monitor index {index}, using primary: {primary.name}", "warning")
                return primary
                
        except Exception as e:
            self._log(f"Error getting monitor info: {e}", "error")
            import traceback
            traceback.print_exc()
            
        return None
    
    def _update_fps_display(self):
        """Update and emit the actual FPS."""
        now = time.time()
        elapsed = now - self._last_fps_time
        
        if elapsed > 0:
            self._current_fps = self._frame_count / elapsed
            self.fps_updated_signal.emit(self._current_fps)
            
            # Reset for next calculation
            self._frame_count = 0
            self._last_fps_time = now
    
    # --- Input Handling Methods ---
    
    def send_input_event(self, event_data):
        """Send input event to peer."""
        if not self.ws_handler or not self.ws_handler.is_connected():
            print("Cannot send input event: WebSocket not connected")
            return
            
        # Send the input event to the peer
        self.ws_handler.send_message({
            "type": "input_event",
            "event": event_data
        })
        
    def _handle_message(self, message):
        """Handle JSON messages from the websocket"""
        # Process input events
        if message.get("type") == "input_event":
            event_data = message.get("event", {})
            self._process_input_event(event_data)
    
    def _process_input_event(self, event_data):
        """Process input events from remote peer"""
        try:
            event_type = event_data.get("type")
            
            # Log received event
            self._log(f"Received input event: {event_type}", "debug")
            
            # Only process events when we're the one sharing our screen
            if not self._is_sharing:
                self._log(f"Ignoring input event {event_type} - not sharing screen", "debug")
                return
            
            # Handle mouse events
            if event_type in ["move", "down", "up"]:
                x = event_data.get("x", 0)
                y = event_data.get("y", 0)
                button = event_data.get("button", 0)
                
                self._log(f"Processing mouse {event_type} at ({x},{y}) button={button}", "debug")
                
                # Get current monitor to adjust coordinates
                monitor = self._get_monitor_by_index(self.monitor_index)
                if not monitor:
                    self._log("No monitor found for coordinate adjustment", "warning")
                    return
                
                # Scale coordinates back to full size if needed
                if self.scale_factor < 1.0:
                    x = int(x / self.scale_factor)
                    y = int(y / self.scale_factor)
                
                # Adjust for monitor position
                x += getattr(monitor, 'x', 0)
                y += getattr(monitor, 'y', 0)
                
                self._log(f"Adjusted coordinates: ({x},{y})", "debug")
                
                # Execute the mouse action
                if event_type == "move":
                    # Move mouse to position
                    try:
                        pyautogui.moveTo(x, y)
                    except Exception as e:
                        self._log(f"Error moving mouse: {e}", "error")
                elif event_type == "down":
                    # Map button numbers to pyautogui buttons
                    btn = "left"
                    if button == 2:
                        btn = "right"
                    elif button == 3:
                        btn = "middle"
                    
                    # Move and click (down) at position
                    try:
                        pyautogui.moveTo(x, y)
                        pyautogui.mouseDown(button=btn)
                    except Exception as e:
                        self._log(f"Error with mouseDown: {e}", "error")
                elif event_type == "up":
                    # Map button numbers to pyautogui buttons
                    btn = "left"
                    if button == 2:
                        btn = "right"
                    elif button == 3:
                        btn = "middle"
                    
                    # Release button at position
                    try:
                        pyautogui.moveTo(x, y)
                        pyautogui.mouseUp(button=btn)
                    except Exception as e:
                        self._log(f"Error with mouseUp: {e}", "error")
                    
            # Handle keyboard events
            elif event_type in ["down", "up"]:
                key = event_data.get("key", 0)
                modifiers = event_data.get("modifiers", 0)
                
                self._log(f"Processing key {event_type}: key={key} modifiers={modifiers}", "debug")
                
                # Convert Qt key code to pyautogui key code
                key_char = self._qt_key_to_pyautogui(key)
                if not key_char:
                    self._log(f"Could not convert key code: {key}", "warning")
                    return
                
                self._log(f"Mapped key: {key_char}", "debug")
                    
                # Handle key action
                if event_type == "down":
                    try:
                        pyautogui.keyDown(key_char)
                    except Exception as e:
                        self._log(f"Error with keyDown: {e}", "error")
                elif event_type == "up":
                    try:
                        pyautogui.keyUp(key_char)
                    except Exception as e:
                        self._log(f"Error with keyUp: {e}", "error")
                    
        except Exception as e:
            self._log(f"Error processing input event: {e}", "error")
            import traceback
            traceback.print_exc()
    
    def _qt_key_to_pyautogui(self, qt_key):
        """Convert Qt key code to pyautogui key name"""
        from PyQt5.QtCore import Qt
        
        # Map of Qt key codes to pyautogui key names
        key_map = {
            Qt.Key_Escape: "esc",
            Qt.Key_Tab: "tab",
            Qt.Key_Backtab: "tab",
            Qt.Key_Backspace: "backspace",
            Qt.Key_Return: "enter",
            Qt.Key_Enter: "enter",
            Qt.Key_Insert: "insert",
            Qt.Key_Delete: "delete",
            Qt.Key_Pause: "pause",
            Qt.Key_Print: "printscreen",
            Qt.Key_Home: "home",
            Qt.Key_End: "end",
            Qt.Key_Left: "left",
            Qt.Key_Up: "up",
            Qt.Key_Right: "right",
            Qt.Key_Down: "down",
            Qt.Key_PageUp: "pageup",
            Qt.Key_PageDown: "pagedown",
            Qt.Key_F1: "f1",
            Qt.Key_F2: "f2",
            Qt.Key_F3: "f3",
            Qt.Key_F4: "f4",
            Qt.Key_F5: "f5",
            Qt.Key_F6: "f6",
            Qt.Key_F7: "f7",
            Qt.Key_F8: "f8",
            Qt.Key_F9: "f9",
            Qt.Key_F10: "f10",
            Qt.Key_F11: "f11",
            Qt.Key_F12: "f12",
            Qt.Key_Space: "space",
            Qt.Key_Control: "ctrl",
            Qt.Key_Alt: "alt",
            Qt.Key_Shift: "shift",
            Qt.Key_Meta: "win",
        }
        
        # Check for special keys
        if qt_key in key_map:
            return key_map[qt_key]
            
        # Handle printable characters
        try:
            return chr(qt_key).lower()
        except:
            print(f"Could not convert Qt key code: {qt_key}")
            return None
    
    # --- Message Handling Methods ---
    
    def _handle_binary_message(self, data):
        """Handle incoming binary messages (screen frames)."""
        try:
            # Only process the screen frame if we're not the sender
            # This prevents showing our own screen frames that we're sending
            if not self._is_sharing:
                # Process the screen frame data directly - no need to extract cursor position
                # Emit the binary data to be displayed
                self.screen_captured_signal.emit(data)
                
                # Update FPS calculation
                self._frame_count += 1
            else:
                # If we're sharing, we should not be receiving frames
                self._log("Received screen frame while sharing - unexpected behavior", "warning")
            
        except Exception as e:
            print(f"Error processing binary message: {e}")
            self.error_signal.emit(f"Error processing screen frame: {e}")
            import traceback
            traceback.print_exc()
    
    def _on_ws_disconnected(self, reason):
        """Handle WebSocket disconnection."""
        # Stop sharing if active
        if self._is_sharing:
            self.stop_screen_sharing()
            
        print(f"WebSocket disconnected ({reason}), sharing stopped.") 

    def _capture_screen(self):
        """Capture the screen and return as JPEG bytes and cursor position."""
        try:
            # Get monitor bounds based on monitor_index
            monitor = self._get_monitor_by_index(self.monitor_index)
            
            if not monitor:
                self._log(f"Monitor {self.monitor_index} not found, using primary monitor", "warning")
                # Try to get primary monitor or first available
                monitors = screeninfo.get_monitors()
                if monitors:
                    monitor = monitors[0]
                else:
                    # Fallback to hardcoded values if no monitors detected
                    self._log("No monitors detected, using default screen size", "warning")
                    monitor = type('obj', (object,), {
                        'x': 0,
                        'y': 0,
                        'width': 1920,
                        'height': 1080
                    })
            
            # Ensure monitor coordinates are valid
            x = getattr(monitor, 'x', 0)
            y = getattr(monitor, 'y', 0)
            width = getattr(monitor, 'width', 1920)
            height = getattr(monitor, 'height', 1080)
            
            # Validate dimensions to avoid errors
            width = max(width, 1)
            height = max(height, 1)
            
            self._log(f"Capturing screen region: ({x}, {y}, {width}, {height})", "debug")
            
            # Capture screen region for the specified monitor
            try:
                # Try different capture methods based on platform for better multi-monitor support
                import platform
                system = platform.system()
                
                # Windows-specific optimizations for multi-monitor setups
                if system == 'Windows':
                    self._log(f"Using Windows-specific capture method", "debug")
                    # First try MSS for more reliable multi-monitor capture
                    try:
                        import mss
                        with mss.mss() as sct:
                            # MSS uses a different coordinate system for monitors
                            # Convert to MSS format: {"left": x, "top": y, "width": w, "height": h}
                            monitor_dict = {
                                "left": x, 
                                "top": y, 
                                "width": width, 
                                "height": height
                            }
                            
                            # Attempt capture
                            sct_img = sct.grab(monitor_dict)
                            # Convert to PIL Image
                            screenshot = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                            self._log(f"MSS capture successful: {screenshot.width}x{screenshot.height}", "debug")
                    except Exception as mss_error:
                        self._log(f"MSS capture failed, falling back to ImageGrab: {mss_error}", "warning")
                        # Fall back to ImageGrab
                        # On Windows, ImageGrab has issues with negative coordinates
                        # Adjust to use absolute screen coordinates
                        actual_x = max(0, x)
                        actual_y = max(0, y)
                        actual_width = min(width, 1920 - actual_x)  # Ensure we don't go beyond screen boundaries
                        actual_height = min(height, 1080 - actual_y)
                        
                        self._log(f"Adjusted capture region: ({actual_x}, {actual_y}, {actual_width}, {actual_height})", "debug")
                        screenshot = ImageGrab.grab(bbox=(actual_x, actual_y, 
                                                        actual_x + actual_width, 
                                                        actual_y + actual_height))
                else:
                    # For other platforms just use ImageGrab
                    screenshot = ImageGrab.grab(bbox=(x, y, x + width, y + height))
                
                # Verify that we got a valid image
                if not screenshot or screenshot.width <= 0 or screenshot.height <= 0:
                    raise ValueError(f"Invalid screenshot dimensions: {screenshot.width}x{screenshot.height}")
                    
            except Exception as e:
                self._log(f"Error grabbing screen with bbox: {e}. Trying full screen capture.", "warning")
                # Fall back to full screen capture if region fails
                try:
                    self._log("Attempting full screen capture", "debug")
                    screenshot = ImageGrab.grab()
                    
                    # Verify that we got a valid image
                    if not screenshot or screenshot.width <= 0 or screenshot.height <= 0:
                        raise ValueError("Invalid screenshot dimensions from full screen grab")
                        
                except Exception as e2:
                    self._log(f"Fatal error in full screen capture: {e2}", "error")
                    # Return a blank image as a last resort to avoid crashes
                    self._log("Creating blank image with error message", "debug")
                    screenshot = Image.new('RGB', (640, 480), color='black')
                    # Add text to indicate error
                    from PIL import ImageDraw, ImageFont
                    draw = ImageDraw.Draw(screenshot)
                    draw.rectangle([210, 210, 430, 270], fill='red')
                    try:
                        # Try to use a font, but don't crash if not available
                        font = ImageFont.truetype("arial.ttf", 20)
                        draw.text((220, 220), "Screen Capture Error", fill="white", font=font)
                        draw.text((220, 245), "Check logs for details", fill="white", font=font)
                    except:
                        # Basic fallback if font not available
                        draw.text((220, 220), "Screen Capture Error", fill="white")
                        draw.text((220, 245), "Check logs for details", fill="white")
            
            # Get cursor position
            try:
                cursor_x, cursor_y = pyautogui.position()
                # Adjust cursor position relative to monitor
                cursor_x -= x
                cursor_y -= y
                self._log(f"Cursor position: ({cursor_x}, {cursor_y})", "debug")
            except Exception as e:
                self._log(f"Error getting cursor position: {e}", "warning")
                cursor_x, cursor_y = 0, 0
            
            # Apply scaling if needed
            if self.scale_factor < 1.0:
                try:
                    new_width = max(int(screenshot.width * self.scale_factor), 1)
                    new_height = max(int(screenshot.height * self.scale_factor), 1)
                    
                    self._log(f"Scaling image: {screenshot.width}x{screenshot.height} -> {new_width}x{new_height}", "debug")
                    
                    # Use LANCZOS for better quality or BILINEAR for speed
                    resampling = Image.LANCZOS if self.quality > 50 else Image.BILINEAR
                    screenshot = screenshot.resize((new_width, new_height), resampling)
                    
                    # Scale cursor position too
                    cursor_x = int(cursor_x * self.scale_factor)
                    cursor_y = int(cursor_y * self.scale_factor)
                except Exception as e:
                    self._log(f"Error scaling image: {e}", "warning")
            
            # Convert to JPEG bytes
            buffer = io.BytesIO()
            try:
                # Higher subsampling values = lower quality but smaller file
                subsampling = 0 if self.quality > 90 else 2
                screenshot.save(buffer, format="JPEG", quality=self.quality, subsampling=subsampling)
                buffer_value = buffer.getvalue()
                
                # Log the size of the image
                self._log(f"JPEG size: {len(buffer_value)/1024:.1f} KB", "debug")
                
                # Verify we have valid data
                if not buffer_value or len(buffer_value) < 100:
                    raise ValueError(f"Invalid buffer size: {len(buffer_value) if buffer_value else 0} bytes")
                    
                return buffer_value, (cursor_x, cursor_y)
                
            except Exception as e:
                self._log(f"Error saving image to buffer: {e}", "warning")
                # Try with basic parameters
                try:
                    screenshot.save(buffer, format="JPEG")
                    buffer_value = buffer.getvalue()
                    
                    # Verify we have valid data
                    if not buffer_value or len(buffer_value) < 100:
                        raise ValueError(f"Invalid buffer size: {len(buffer_value) if buffer_value else 0} bytes")
                        
                    return buffer_value, (cursor_x, cursor_y)
                    
                except Exception as e2:
                    self._log(f"Fatal error saving image: {e2}", "error")
                    return None, (0, 0)
            
        except Exception as e:
            self._log(f"Error capturing screen: {e}", "error")
            import traceback
            traceback.print_exc()
            return None, (0, 0) 