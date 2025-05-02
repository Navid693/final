"""
Constants and configuration settings for the Remote Desktop Application.
"""

# Network and Connection Settings
DEFAULT_BACKEND_URL = "http://127.0.0.1:8000"  # Can be overridden by user input
DEFAULT_WS_URL = "ws://127.0.0.1:8000/ws"  # Can be overridden by user input
MAX_RECONNECT_ATTEMPTS = 5  # Can be configured in settings
RECONNECT_DELAY_MS = 5000  # Can be configured in settings

# Stream Settings
DEFAULT_STREAM_QUALITY = 80  # Can be configured in UI
DEFAULT_STREAM_SCALE = 50  # Can be configured in UI
DEFAULT_STREAM_FPS = 30  # Can be configured in UI
DEFAULT_MONITOR_INDEX = 0  # Can be configured in UI
MIN_FRAME_SIZE = 100  # Minimum size for valid frame data

# UI and Theme Settings
DEFAULT_THEME = "dark"
AVAILABLE_THEMES = ["dark", "light"]
STATUS_MESSAGE_TIMEOUT_MS = 3000  # Can be configured in settings

# Security Settings
JWT_TOKEN_HEADER = "Authorization"
TOKEN_PREFIX = "Bearer "
MAX_PASSWORD_LENGTH = 128
MIN_PASSWORD_LENGTH = 8

# System Messages
INITIAL_STATUS = "Initializing..."
CONNECTION_STATUS = {
    "connecting": "Connecting to server...",
    "connected": "Connected to server",
    "disconnected": "Disconnected from server",
    "error": "Connection error"
}

# WebSocket Message Types
WS_MESSAGE_TYPES = {
    "REGISTER": "register",
    "USERS_LIST": "users_list",
    "CONNECT_REQUEST": "connect_request",
    "CONNECT_RESPONSE": "connect_response",
    "DISCONNECT": "disconnect",
    "CHAT": "chat",
    "CONTROL_REQUEST": "control_request",
    "CONTROL_RESPONSE": "control_response",
    "FRAME": "frame"
}

# File Paths
STYLES_DIR = "styles"
ICONS_DIR = "Icons"
LOG_FILE = "app.log"

# Logging Settings
LOG_FORMAT = '%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
LOG_LEVEL = "DEBUG"  # Can be configured in settings 