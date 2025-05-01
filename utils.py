import socket
import struct
import pickle
import mss
import mss.tools
from PIL import Image
import numpy as np
import pyautogui
import io

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

# --- Screen Capture and Compression ---

def capture_screenshot(monitor_number=1, quality=75):
    """Captures a screenshot, compresses it (JPEG), and returns bytes."""
    try:
        with mss.mss() as sct:
            # Get information about the monitor
            monitor = sct.monitors[monitor_number]

            # Capture the screen
            sct_img = sct.grab(monitor)

            # Convert to PIL Image
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

            # Compress to JPEG in memory
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='JPEG', quality=quality)
            return img_byte_arr.getvalue()
    except Exception as e:
        print(f"Error capturing or compressing screenshot: {e}")
        return None

# --- Input Simulation ---

def simulate_mouse_event(event_data):
    """Simulates mouse events based on received data using local screen size."""
    event_type = event_data['type']
    # Get coordinates relative to the *remote* screen size sent by the controller
    x = event_data['x'] 
    y = event_data['y'] 
    # We also need the dimensions of the screen *where the event occurred* (controller's view)
    # This information is implicitly handled by get_scaled_coords in ui.py, which sends
    # coordinates already scaled relative to the remote screen size.

    button = event_data.get('button')

    # Get the actual screen size of the machine *running this code* (the host)
    host_width, host_height = pyautogui.size()

    # Since controller sends coords relative to remote screen, no further scaling needed here.
    # We directly use x and y, but clamp them to the host screen bounds.
    actual_x = max(0, min(x, host_width))
    actual_y = max(0, min(y, host_height))

    try:
        if event_type == 'move':
            pyautogui.moveTo(actual_x, actual_y)
        elif event_type == 'click': # Note: PyAutoGUI click needs press/release separated usually
             # Sending press/release is more reliable
             pyautogui.mouseDown(x=actual_x, y=actual_y, button=button)
             pyautogui.mouseUp(x=actual_x, y=actual_y, button=button)
        elif event_type == 'press':
             pyautogui.mouseDown(x=actual_x, y=actual_y, button=button)
        elif event_type == 'release':
             pyautogui.mouseUp(x=actual_x, y=actual_y, button=button)
        elif event_type == 'scroll':
            delta_x = event_data.get('delta_x', 0)
            delta_y = event_data.get('delta_y', 0)
            if delta_y != 0:
                pyautogui.scroll(delta_y // abs(delta_y) * 5 if delta_y else 0)
            if delta_x != 0:
                 pyautogui.hscroll(delta_x // abs(delta_x) * 5 if delta_x else 0)
    except Exception as e:
        print(f"Error simulating mouse event: {e}")


def simulate_keyboard_event(event_data):
    """Simulates keyboard events based on received data."""
    event_type = event_data['type']
    key = event_data['key']

    # Map Qt key names/codes to pyautogui names if necessary
    # This is a simplified example; a more robust solution needs better mapping
    key_map = {
        '<ctrl>': 'ctrl',
        '<alt>': 'alt',
        '<shift>': 'shift',
        '<enter>': 'enter',
        '<tab>': 'tab',
        '<space>': 'space',
        '<backspace>': 'backspace',
        '<delete>': 'delete',
        '<esc>': 'esc',
        '<up>': 'up',
        '<down>': 'down',
        '<left>': 'left',
        '<right>': 'right',
        # Add more mappings as needed
    }
    key_to_press = key_map.get(key.lower(), key) # Use mapping or original key

    try:
        if event_type == 'press':
            pyautogui.keyDown(key_to_press)
        elif event_type == 'release':
            pyautogui.keyUp(key_to_press)
    except Exception as e:
        # pyautogui might fail for some special keys or combinations
        print(f"Error simulating keyboard event for key '{key_to_press}': {e}")

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
DEFAULT_QUALITY = 75 # JPEG quality 