import socket
import struct
import pickle
import mss
import mss.tools
from PIL import Image, ImageOps
import numpy as np
import pyautogui
import io
import time
import traceback

# --- Network Utilities ---

def send_data(sock, data):
    """Prefixes the data with its size and sends it."""
    try:
        serialized_data = pickle.dumps(data)
        sock.sendall(struct.pack('>I', len(serialized_data)) + serialized_data)
    except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError) as e:
        print(f"Connection error during send: {e}")
        raise # Re-raise to signal the connection is broken
    except Exception as e:
        print(f"Error sending data: {e}")
        raise

def recv_data(sock):
    """Receives data prefixed with its size."""
    try:
        # Read message length and unpack it into an integer
        raw_msglen = recvall(sock, 4)
        if not raw_msglen:
            return None
        msglen = struct.unpack('>I', raw_msglen)[0]
        # Read the message data
        return pickle.loads(recvall(sock, msglen))
    except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError) as e:
        print(f"Connection error during receive: {e}")
        return None # Signal connection is broken
    except EOFError: # Handle case where connection is closed mid-pickle stream
        print("Connection closed unexpectedly while receiving data.")
        return None
    except (struct.error, pickle.UnpicklingError) as e:
        print(f"Error receiving/unpacking data: {e}")
        # This might indicate corrupted data or the other side closing improperly
        return None
    except Exception as e:
        print(f"Unexpected error receiving data: {e}")
        return None


def recvall(sock, n):
    """Helper function to receive n bytes or return None if EOF is hit."""
    data = bytearray()
    while len(data) < n:
        try:
            packet = sock.recv(n - len(data))
            if not packet:
                return None
            data.extend(packet)
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            print("Connection closed during recvall.")
            return None
        except Exception as e:
            print(f"Error in recvall: {e}")
            return None
    return bytes(data)

# --- Screen Capture, Scaling, Compression, and Cursor ---

def get_monitor_details():
    """Returns a list of dictionaries with details for each monitor (excluding Monitor 0: All)."""
    monitors = []
    try:
        with mss.mss() as sct:
            # sct.monitors[0] is the full virtual screen, skip it
            for i, monitor in enumerate(sct.monitors[1:], start=1):
                details = {
                    "index": i,
                    "name": f"Monitor {i}",
                    "size": f"{monitor['width']}x{monitor['height']}",
                    "position": f"@{monitor['left']},{monitor['top']}",
                    "full_details": monitor # Store raw details if needed
                }
                monitors.append(details)
    except Exception as e:
        print(f"Error getting monitor details: {e}")
    return monitors

def capture_screen_frame(monitor_number=1, quality=75, scale=1.0):
    """
    Captures a screenshot of the specified monitor, optionally scales it,
    compresses it to JPEG, gets the current cursor position,
    and returns (jpeg_bytes, cursor_position_tuple).
    """
    jpeg_bytes = None
    cursor_pos = (0, 0) # Default cursor position

    try:
        # 1. Get cursor position FIRST (less chance of it changing during capture)
        cursor_pos = pyautogui.position()

        # 2. Capture screen using mss
        with mss.mss() as sct:
            # Ensure monitor_number is valid
            if monitor_number >= len(sct.monitors):
                print(f"[WARN] Monitor {monitor_number} not found. Using primary (monitor 1).")
                monitor_number = 1 # Fallback to primary
            if monitor_number == 0: # Monitor 0 is the full virtual screen
                 print("[WARN] Monitor 0 selected (full virtual screen). Using primary (monitor 1) instead.")
                 monitor_number = 1 # Fallback to primary monitor

            monitor = sct.monitors[monitor_number]
            sct_img = sct.grab(monitor)

            # 3. Convert to PIL Image
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

            # 4. Scale the image if scale factor is not 1.0
            scaled_img = img
            if scale != 1.0 and 0.1 <= scale < 1.0:
                try:
                    new_width = int(img.width * scale)
                    new_height = int(img.height * scale)
                    # --- Revert to LANCZOS --- 
                    try:
                        resample_filter = Image.Resampling.LANCZOS # High quality
                    except AttributeError:
                        resample_filter = Image.LANCZOS # Fallback
                    print(f"[UTILS capture] Resizing to {new_width}x{new_height} using {resample_filter}") # LOG
                    scaled_img = img.resize((new_width, new_height), resample_filter)
                except Exception as resize_err:
                     print(f"[UTILS capture] Error resizing image: {resize_err}. Using original.") # LOG
                     scaled_img = img
            # elif scale != 1.0:
            #      print(f"[WARN] Invalid scale factor {scale} ignored. Using 1.0.")

            # 5. Compress the (potentially scaled) image to JPEG in memory
            img_byte_arr = io.BytesIO()
            # Ensure quality is within valid JPEG range (1-95 approx)
            valid_quality = max(1, min(int(quality), 95))
            scaled_img.save(img_byte_arr, format='JPEG', quality=valid_quality)
            jpeg_bytes = img_byte_arr.getvalue()

    except ImportError:
         print("Error: Pillow, mss or PyAutoGUI not installed properly.")
         # Return None or default image?
    except IndexError:
         print(f"Error: Monitor {monitor_number} does not exist.")
         # Could try falling back to monitor 1
    except Exception as e:
        print(f"Error capturing/processing screen frame: {e}")
        # Optionally capture stack trace:
        traceback.print_exc()
        jpeg_bytes = None # Ensure jpeg_bytes is None on error
        cursor_pos = (0, 0) # Reset cursor pos on error

    # Return both, even if jpeg_bytes is None (signals an error)
    return jpeg_bytes, cursor_pos

# --- Input Simulation ---

def simulate_input(event_data):
    """Determines event type and calls the appropriate simulation function."""
    event_type = event_data.get('type')
    print(f"[UTILS simulate_input] Received: Type={event_type}, Data={event_data}") # LOG: Log entry
    if event_type in ['move', 'press', 'release', 'scroll']:
        simulate_mouse_event(event_data)
    elif event_type in ['keypress', 'keyrelease']: # Keyboard event types
        simulate_keyboard_event(event_data)
    else:
        print(f"[UTILS simulate_input] Unknown input event type received: {event_type}") # LOG: Log unknown type

def simulate_mouse_event(event_data):
    """Simulates mouse events."""
    event_type = event_data['type']
    x = event_data['x']
    y = event_data['y']
    button = event_data.get('button')
    print(f"[UTILS simulate_mouse_event] Simulating: Type={event_type}, x={x}, y={y}, button={button}") # LOG: Log parameters
    
    try:
        # Get screen info for all monitors - useful for debugging
        with mss.mss() as sct:
            for i, monitor in enumerate(sct.monitors):
                print(f"[DEBUG] Monitor {i}: {monitor}")
            
            # Let's trust PyAutoGUI's coordinate system which handles multi-monitor setups
            # This is a fundamental change from the prior approach
            screen_width, screen_height = pyautogui.size()
            
            # Scale received coordinates to match the actual screen size
            # This assumes the sender had correct relative coords (0-100%)
            # Uncomment if your coordinates are being sent as percentages
            # actual_x = int(x * screen_width)
            # actual_y = int(y * screen_height)
            
            # Don't adjust coordinates - use as received
            actual_x = int(x)
            actual_y = int(y)
            
            print(f"[UTILS simulate_mouse_event] Using coordinates: ({actual_x}, {actual_y}) on screen size {screen_width}x{screen_height}") # Better log
    except Exception as size_err:
         print(f"[UTILS simulate_mouse_event] Error getting screen size: {size_err}") # LOG: Log error
         traceback.print_exc()
         return

    try:
        # Use FAILSAFE=False to avoid crashes when mouse reaches screen edges
        pyautogui.FAILSAFE = False
        
        if event_type == 'move':
            pyautogui.moveTo(actual_x, actual_y, duration=0)
            print(f"[UTILS simulate_mouse_event] moveTo({actual_x}, {actual_y}) executed.") # LOG: Log success
        elif event_type == 'press':
            pyautogui.mouseDown(x=actual_x, y=actual_y, button=button)
            print(f"[UTILS simulate_mouse_event] mouseDown({actual_x}, {actual_y}, button={button}) executed.") # LOG: Log success
        elif event_type == 'release':
            pyautogui.mouseUp(x=actual_x, y=actual_y, button=button)
            print(f"[UTILS simulate_mouse_event] mouseUp({actual_x}, {actual_y}, button={button}) executed.") # LOG: Log success
        elif event_type == 'scroll':
            delta_x = event_data.get('delta_x', 0)
            delta_y = event_data.get('delta_y', 0)
            h_scroll_amount = 0
            v_scroll_amount = 0
            scroll_sensitivity = 5
            if delta_x > 0: h_scroll_amount = max(1, delta_x // scroll_sensitivity)
            elif delta_x < 0: h_scroll_amount = min(-1, delta_x // scroll_sensitivity)
            if delta_y > 0: v_scroll_amount = max(1, delta_y // scroll_sensitivity)
            elif delta_y < 0: v_scroll_amount = min(-1, delta_y // scroll_sensitivity)

            if v_scroll_amount != 0:
                pyautogui.scroll(v_scroll_amount, x=actual_x, y=actual_y)
                print(f"[UTILS simulate_mouse_event] scroll({v_scroll_amount}) executed at ({actual_x}, {actual_y}).") # LOG: Log success
            if h_scroll_amount != 0:
                pyautogui.hscroll(h_scroll_amount, x=actual_x, y=actual_y)
                print(f"[UTILS simulate_mouse_event] hscroll({h_scroll_amount}) executed at ({actual_x}, {actual_y}).") # LOG: Log success

    except Exception as e:
        print(f"[UTILS simulate_mouse_event] Error during PyAutoGUI call ({event_type}): {e}") # LOG: Log error
        traceback.print_exc()

def simulate_keyboard_event(event_data):
    """Simulates keyboard events."""
    event_type = event_data['type']
    key = event_data['key']
    print(f"[UTILS simulate_keyboard_event] Simulating: Type={event_type}, Key={key}") # LOG: Log parameters
    try:
        if event_type == 'keypress':
            pyautogui.keyDown(key)
            print(f"[UTILS simulate_keyboard_event] keyDown('{key}') executed.") # LOG: Log success
        elif event_type == 'keyrelease':
            pyautogui.keyUp(key)
            print(f"[UTILS simulate_keyboard_event] keyUp('{key}') executed.") # LOG: Log success
    except Exception as e:
        print(f"[UTILS simulate_keyboard_event] Error during PyAutoGUI call ({event_type} for key '{key}'): {e}") # LOG: Log error
        traceback.print_exc()

def get_local_ip():
    """Gets the local IP address of the machine."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Doesn't have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

# Constants
DEFAULT_PORT = 9999
# DEFAULT_QUALITY = 75 # Moved defaults to MainWindow potentially 