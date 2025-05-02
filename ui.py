import sys
import os
import time
import json
import logging
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QLineEdit, QGroupBox, QRadioButton, QDialog, QMessageBox,
    QScrollArea, QFormLayout, QMainWindow, QAction, QStatusBar, QTextEdit,
    QSplitter, QSlider, QSpinBox, QComboBox, QCheckBox, QSizePolicy, QPlainTextEdit,
    QSpacerItem, QFrame, QGridLayout, QListWidget, QListWidgetItem # Import QSpacerItem and QFrame
)
from PyQt5.QtGui import QPixmap, QImage, QPainter, QPen, QCursor, QFont, QPalette, QIcon, QPaintEvent, QMouseEvent, QWheelEvent , QKeyEvent , QPaintEvent 
from PyQt5.QtCore import (
    Qt, QSize, QTimer, QThread, QMutex, pyqtSignal, pyqtSlot, QEvent,
    QPoint, QRect, QPropertyAnimation, QEasingCurve # Added QPropertyAnimation and QEasingCurve
)
# Removed utils import as it's not directly needed here anymore for monitors
import screeninfo # To get monitor info
import time
from constants import (
    DEFAULT_THEME, AVAILABLE_THEMES, STYLES_DIR, ICONS_DIR,
    DEFAULT_STREAM_QUALITY, DEFAULT_STREAM_SCALE, DEFAULT_STREAM_FPS,
    DEFAULT_MONITOR_INDEX, CONNECTION_STATUS
)

# --- Login Window ---
class LoginWindow(QMainWindow):
    """Window for user login."""
    # Signal emits backend_url, username, password
    login_attempt_signal = pyqtSignal(str, str, str)
    toggle_theme_signal = pyqtSignal() # Signal to toggle theme
    # Signal for registration request
    register_signal = pyqtSignal(str) # Emits backend_url for registration

    def __init__(self, default_backend_url="http://127.0.0.1:8000"): # Default to localhost backend
        super().__init__()
        self.default_backend_url = default_backend_url
        self._initUI() # Renamed internal method
        self._load_saved_credentials()

    def _initUI(self):
        """Initializes the Login Window UI elements."""
        self.setWindowTitle("SCU Remote Desktop - Login")
        self.setMinimumWidth(400)
        self.setMinimumHeight(600)  # Set minimum height
        self.setStyleSheet(load_stylesheet(DEFAULT_THEME))

        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)  # Add margins
        main_layout.setSpacing(15)  # Add spacing between elements

        # --- Top Layout (for Title Bar elements) ---
        top_layout = QHBoxLayout()
        top_layout.addStretch(1)  # Push button to the right

        # Theme Toggle Button
        self.theme_button = QPushButton()
        self.theme_button.setObjectName("theme_button")
        self.theme_button.setToolTip("Toggle Light/Dark Mode")
        self.theme_button.setFlat(True)
        self.theme_button.setCursor(Qt.PointingHandCursor)
        self.theme_button.setMinimumSize(35, 35)
        font_theme = self.theme_button.font()
        font_theme.setPointSize(14)  # Larger font for emoji
        self.theme_button.setFont(font_theme)
        self._update_theme_icon("dark")  # Assume starting dark
        self.theme_button.clicked.connect(self.toggle_theme_signal.emit)  # Emit signal
        top_layout.addWidget(self.theme_button)
        main_layout.addLayout(top_layout)

        # Logo Placeholder
        self.logo_label = QLabel("SCU Logo Placeholder")
        self.logo_label.setObjectName("logo_label")
        self.logo_label.setAlignment(Qt.AlignCenter)
        pixmap = QPixmap('Icons/logo.png')  # TODO: Ensure Icons/logo.png is available
        if not pixmap.isNull():
            self.logo_label.setPixmap(pixmap.scaled(150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.logo_label.setText("[Logo Not Found]")  # Fallback text
        main_layout.addWidget(self.logo_label)

        # Title Labels
        self.title_label1 = QLabel("SCU Remote Desktop")
        self.title_label1.setObjectName("title_label1")
        self.title_label1.setAlignment(Qt.AlignCenter)
        font1 = self.title_label1.font()
        font1.setPointSize(14)
        font1.setBold(True)
        self.title_label1.setFont(font1)
        main_layout.addWidget(self.title_label1)

        self.title_label2 = QLabel("Remote Control System")
        self.title_label2.setObjectName("title_label2")
        self.title_label2.setAlignment(Qt.AlignCenter)
        font2 = self.title_label2.font()
        font2.setPointSize(10)
        self.title_label2.setFont(font2)
        main_layout.addWidget(self.title_label2)

        main_layout.addSpacing(20)  # Spacer

        # Form Layout for inputs
        form_layout = QFormLayout()  # Changed from QVBoxLayout to QFormLayout
        form_layout.setSpacing(10)

        # Backend URL
        self.backend_label = QLabel("Backend URL:")
        self.backend_label.setObjectName("backend_label")
        self.backend_input = QLineEdit(self)
        self.backend_input.setText(self.default_backend_url)
        form_layout.addRow(self.backend_label, self.backend_input)

        # Username
        self.username_label = QLabel("Username:")
        self.username_label.setObjectName("username_label")
        self.username_input = QLineEdit(self)
        form_layout.addRow(self.username_label, self.username_input)

        # Password
        self.password_label = QLabel("Password:")
        self.password_label.setObjectName("password_label")
        self.password_input = QLineEdit(self)
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Enter your password")
        form_layout.addRow(self.password_label, self.password_input)

        # Remember Me Checkbox
        self.remember_me_checkbox = QCheckBox("Remember Me")
        self.remember_me_checkbox.setStyleSheet("""
            QCheckBox {
                color: #ffffff;
                font-size: 14px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
            }
            QCheckBox::indicator:unchecked {
                border: 2px solid #666666;
                background-color: #2d2d2d;
            }
            QCheckBox::indicator:checked {
                border: 2px solid #0078d4;
                background-color: #0078d4;
            }
        """)
        form_layout.addRow("", self.remember_me_checkbox)

        main_layout.addLayout(form_layout)
        main_layout.addSpacing(20)  # Spacer before buttons

        # Button Layout
        button_layout = QVBoxLayout()
        button_layout.setSpacing(10)

        # Login Button
        self.login_button = QPushButton("Login", self)
        self.login_button.setObjectName("login_button")
        self.login_button.clicked.connect(self.attempt_login)
        self.login_button.setDefault(True)  # Allow Enter key to trigger login
        button_layout.addWidget(self.login_button)

        # Register Button
        self.register_button = QPushButton("Register", self)
        self.register_button.setObjectName("register_button")
        self.register_button.clicked.connect(self.show_registration_window)
        button_layout.addWidget(self.register_button)

        main_layout.addLayout(button_layout)

        # Error Label (Initially Hidden)
        self.error_label = QLabel("", self)
        self.error_label.setObjectName("error_label")
        self.error_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.error_label)
        self.error_label.hide()

        main_layout.addStretch(1)  # Add stretch at the bottom

        self.username_input.setFocus()  # Set initial focus

    def _load_saved_credentials(self):
        """Loads saved credentials if Remember Me was checked previously."""
        # TODO (Backend): Replace with actual credential storage implementation
        # This should be implemented using secure storage (e.g., keyring, encrypted file)
        # For now, using a simple JSON file as placeholder
        try:
            with open("credentials.json", "r") as f:
                data = json.load(f)
                if data.get("remember_me", False):
                    self.backend_input.setText(data.get("backend_url", ""))
                    self.username_input.setText(data.get("username", ""))
                    self.remember_me_checkbox.setChecked(True)
        except FileNotFoundError:
            pass

    def set_logging_in(self):
        """Updates the UI to show a logging in state."""
        self.login_button.setEnabled(False)
        self.login_button.setText("Logging in...")
        self.register_button.setEnabled(False)
        self.error_label.hide()

    def _save_credentials(self):
        """Saves credentials if Remember Me is checked."""
        # TODO (Backend): Replace with secure credential storage implementation
        if self.remember_me_checkbox.isChecked():
            data = {
                "backend_url": self.backend_input.text(),
                "username": self.username_input.text(),
                "remember_me": True
            }
            with open("credentials.json", "w") as f:
                json.dump(data, f)
        else:
            # Clear saved credentials if Remember Me is unchecked
            try:
                os.remove("credentials.json")
            except FileNotFoundError:
                pass

    def attempt_login(self):
        """Handles login attempt."""
        backend_url = self.backend_input.text().strip()
        username = self.username_input.text().strip()
        password = self.password_input.text()

        # TODO (Backend): Add proper input validation
        # - Validate backend_url format
        # - Validate username format (e.g., length, allowed characters)
        # - Validate password requirements (e.g., minimum length, complexity)
        
        if not backend_url or not username or not password:
            self.show_error("Please fill in all fields")
            return

        # Save credentials if Remember Me is checked
        self._save_credentials()

        # TODO (Backend): Replace with actual authentication
        # 1. Implement proper JWT token handling
        # 2. Add secure password storage/hashing
        # 3. Add proper error handling for different failure cases
        # 4. Add rate limiting protection
        # 5. Add session management
        self.login_attempt_signal.emit(backend_url, username, password)

    def show_registration_window(self):
        """Shows registration window."""
        backend_url = self.backend_input.text().strip()
        if not backend_url:
            self.show_error("Please enter backend URL first")
            return

        # TODO (Backend): Add registration window implementation
        # 1. Create RegistrationWindow class
        # 2. Add proper validation
        # 3. Add proper error handling
        # 4. Add proper success handling
        self.register_signal.emit(backend_url)

    def show_error(self, message):
        """Displays an error message on the login screen."""
        self.error_label.setText(message)
        self.error_label.show()
        # Re-enable button and reset text after error
        self.login_button.setEnabled(True)
        self.login_button.setText("Login")
        self.register_button.setEnabled(True)

    def _update_theme_icon(self, theme_name):
        """Updates the theme toggle button icon and tooltip."""
        if theme_name == "dark":
            emoji = "☀️" # Sun emoji for dark mode (switch to light)
            tooltip = "Switch to Light Mode"
        else:
            emoji = "🌙" # Moon emoji for light mode (switch to dark)
            tooltip = "Switch to Dark Mode"

        self.theme_button.setText(emoji)
        self.theme_button.setIcon(QIcon()) # Clear any potential icon
        self.theme_button.setToolTip(tooltip)
        # Ensure font size remains correct
        font = self.theme_button.font()
        font.setPointSize(14) # Larger font for emoji
        self.theme_button.setFont(font)

# --- Registration Window ---
class RegistrationWindow(QMainWindow):
    """Window for user registration."""
    # Signal emits backend_url, username, password, confirm_password
    register_attempt_signal = pyqtSignal(str, str, str, str)
    toggle_theme_signal = pyqtSignal()

    def __init__(self, backend_url, current_theme="dark"):
        super().__init__()
        self.backend_url = backend_url
        self.current_theme = current_theme
        self._initUI()

    def _initUI(self):
        """Initializes the Registration Window UI elements."""
        self.setWindowTitle("SCU Remote Desktop - Register")
        self.setMinimumWidth(400)
        self.setStyleSheet(load_stylesheet(self.current_theme))

        # --- Top Layout (for Title Bar elements) ---
        top_layout = QHBoxLayout()
        top_layout.addStretch(1)

        # Theme Toggle Button
        self.theme_button = QPushButton()
        self.theme_button.setObjectName("theme_button")
        self.theme_button.setToolTip("Toggle Light/Dark Mode")
        self.theme_button.setFlat(True)
        self.theme_button.setCursor(Qt.PointingHandCursor)
        self.theme_button.setMinimumSize(35, 35)
        font_theme = self.theme_button.font()
        font_theme.setPointSize(14)
        self.theme_button.setFont(font_theme)
        self._update_theme_icon(self.current_theme)
        self.theme_button.clicked.connect(self.toggle_theme_signal.emit)
        top_layout.addWidget(self.theme_button)

        # --- Main Content Layout ---
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(30, 0, 30, 30)
        content_layout.setSpacing(15)

        # Title Labels
        self.title_label1 = QLabel("Create Account")
        self.title_label1.setObjectName("title_label1")
        self.title_label1.setAlignment(Qt.AlignCenter)
        font1 = self.title_label1.font()
        font1.setPointSize(14)
        font1.setBold(True)
        self.title_label1.setFont(font1)
        content_layout.addWidget(self.title_label1)

        content_layout.addSpacing(20)

        # Username
        self.username_label = QLabel("Username:")
        self.username_label.setObjectName("username_label")
        self.username_input = QLineEdit(self)
        content_layout.addWidget(self.username_label)
        content_layout.addWidget(self.username_input)

        # Password
        self.password_label = QLabel("Password:")
        self.password_label.setObjectName("password_label")
        self.password_input = QLineEdit(self)
        self.password_input.setEchoMode(QLineEdit.Password)
        content_layout.addWidget(self.password_label)
        content_layout.addWidget(self.password_input)

        # Confirm Password
        self.confirm_password_label = QLabel("Confirm Password:")
        self.confirm_password_label.setObjectName("confirm_password_label")
        self.confirm_password_input = QLineEdit(self)
        self.confirm_password_input.setEchoMode(QLineEdit.Password)
        content_layout.addWidget(self.confirm_password_label)
        content_layout.addWidget(self.confirm_password_input)

        content_layout.addSpacing(10)

        # Register Button
        self.register_button = QPushButton("Register", self)
        self.register_button.setObjectName("register_button")
        self.register_button.clicked.connect(self.attempt_register)
        self.register_button.setDefault(True)
        content_layout.addWidget(self.register_button)

        # Back to Login Button
        self.back_button = QPushButton("Back to Login", self)
        self.back_button.setObjectName("back_button")
        self.back_button.clicked.connect(self.close)
        content_layout.addWidget(self.back_button)

        # Error Label
        self.error_label = QLabel("", self)
        self.error_label.setObjectName("error_label")
        self.error_label.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(self.error_label)
        self.error_label.hide()

        # --- Combine Layouts ---
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 5, 0, 0)
        main_layout.addLayout(top_layout)
        main_layout.addLayout(content_layout)

        self.username_input.setFocus()

    def attempt_register(self):
        """Validates input and emits register_attempt_signal."""
        username = self.username_input.text().strip()
        password = self.password_input.text()
        confirm_password = self.confirm_password_input.text()

        if not username or not password or not confirm_password:
            self.show_error("All fields are required.")
            return

        if password != confirm_password:
            self.show_error("Passwords do not match.")
            return

        if len(password) < 8:
            self.show_error("Password must be at least 8 characters long.")
            return

        # Clear previous error
        self.error_label.hide()
        self.error_label.setText("")

        self.register_attempt_signal.emit(self.backend_url, username, password, confirm_password)

    def show_error(self, message):
        """Displays an error message on the registration screen."""
        self.error_label.setText(message)
        self.error_label.show()
        self.register_button.setEnabled(True)
        self.register_button.setText("Register")

    def set_registering(self):
        """Updates UI to show registering state."""
        self.register_button.setEnabled(False)
        self.register_button.setText("Registering...")
        self.error_label.hide()

    def _update_theme_icon(self, theme_name):
        """Updates the theme toggle button icon and tooltip."""
        if theme_name == "dark":
            emoji = "☀️"
            tooltip = "Switch to Light Mode"
        else:
            emoji = "🌙"
            tooltip = "Switch to Dark Mode"

        self.theme_button.setText(emoji)
        self.theme_button.setIcon(QIcon())
        self.theme_button.setToolTip(tooltip)
        font = self.theme_button.font()
        font.setPointSize(14)
        self.theme_button.setFont(font)

# --- Screen Display Widget ---
class ScreenDisplayWidget(QWidget):
    """Widget to display the remote screen and capture input."""
    mouse_event_signal = pyqtSignal(dict)
    key_event_signal = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pixmap = QPixmap()
        self.setMinimumSize(800, 600) # Start with a reasonable size
        self.setFocusPolicy(Qt.StrongFocus) # To receive keyboard events
        self.setMouseTracking(True) # Receive mouse move events without clicking
        self.remote_screen_size = QSize(1, 1) # Placeholder, updated on first frame
        self._view_only = True # Start in view-only mode
        self._fit_to_window = False # Start in 1:1 mode
        self.remote_cursor_pos = None # Store position like (x, y)

        self.setCursor(Qt.ArrowCursor) # Show local cursor initially (since view_only is True)
        self.setObjectName("ScreenDisplayWidget") # For styling if needed

    def set_view_only(self, view_only):
        """Enable/disable sending input events."""
        print(f"[UI ScreenDisplay] Setting view_only: {view_only}") # Log state change
        self._view_only = view_only
        if view_only:
            self.setCursor(Qt.ArrowCursor) # Show local cursor if view only
        else:
            self.setCursor(Qt.BlankCursor) # Hide local cursor when controlling

    def update_screen(self, image_data):
        """Loads image data into the pixmap and triggers a repaint."""
        try:
            qimg = QImage.fromData(image_data) # Allow Qt to auto-detect format
            if not qimg.isNull():
                self.pixmap = QPixmap.fromImage(qimg)
                new_size = self.pixmap.size()
                if self.remote_screen_size != new_size:
                     print(f"[UI ScreenDisplay] Received frame, remote size: {new_size.width()}x{new_size.height()}")
                     self.remote_screen_size = new_size
                self.updateGeometry() # Recalculate size hint if needed
                self.update() # Schedule a repaint
            else:
                print("[UI ScreenDisplay WARNING] Failed to load image from data.")
        except Exception as e:
            print(f"[UI ScreenDisplay ERROR] Error updating screen: {e}")

    def update_remote_cursor(self, x, y):
        """Stores the remote cursor position to draw it."""
        self.remote_cursor_pos = (x, y)
        self.update() # Redraw to show new cursor position

    def set_fit_to_window(self, fit):
        """Sets the fit-to-window mode and triggers repaint."""
        print(f"[UI ScreenDisplay] Setting fit_to_window: {fit}")
        if self._fit_to_window != fit:
            self._fit_to_window = fit
            self.updateGeometry() # May need size adjustment
            self.update() # Request repaint

    def paintEvent(self, event: QPaintEvent):
        """Paints the screen pixmap and remote cursor."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform) # Nicer scaling

        if not self.pixmap.isNull():
            target_rect = self.rect() # Area to draw into
            pixmap_size = self.pixmap.size()
            scaled_pixmap = self.pixmap
            draw_pos = QPoint(0, 0) # Top-left corner by default

            if self._fit_to_window:
                # Scale pixmap to fit widget while preserving aspect ratio
                scaled_pixmap = self.pixmap.scaled(target_rect.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                # Center the scaled pixmap
                draw_pos.setX(int((target_rect.width() - scaled_pixmap.width()) / 2))
                draw_pos.setY(int((target_rect.height() - scaled_pixmap.height()) / 2))
            else:
                # Ensure widget minimum size matches pixmap in 1:1 mode
                if self.minimumSize() != pixmap_size:
                    self.setMinimumSize(pixmap_size)

            # Draw the screen pixmap
            painter.drawPixmap(draw_pos, scaled_pixmap)

            # Draw remote cursor (if available and not in view-only)
            if self.remote_cursor_pos and not self._view_only:
                cursor_widget_x, cursor_widget_y = 0, 0
                # Scale cursor position based on how pixmap was drawn
                if self._fit_to_window and pixmap_size.width() > 0 and pixmap_size.height() > 0 and scaled_pixmap.width() > 0:
                    scale_ratio_x = scaled_pixmap.width() / pixmap_size.width()
                    scale_ratio_y = scaled_pixmap.height() / pixmap_size.height()
                    cursor_widget_x = int(self.remote_cursor_pos[0] * scale_ratio_x + draw_pos.x())
                    cursor_widget_y = int(self.remote_cursor_pos[1] * scale_ratio_y + draw_pos.y())
                else: # 1:1 or error case
                    cursor_widget_x = int(self.remote_cursor_pos[0])
                    cursor_widget_y = int(self.remote_cursor_pos[1])

                # Clamp cursor display coords to widget bounds for safety
                cursor_widget_x = max(0, min(cursor_widget_x, target_rect.width() - 1))
                cursor_widget_y = max(0, min(cursor_widget_y, target_rect.height() - 1))

                # Draw cursor (e.g., a red cross)
                painter.setPen(QPen(Qt.red, 2))
                painter.drawLine(cursor_widget_x - 7, cursor_widget_y, cursor_widget_x + 7, cursor_widget_y)
                painter.drawLine(cursor_widget_x, cursor_widget_y - 7, cursor_widget_x, cursor_widget_y + 7)
        else:
            # Draw placeholder if no screen data
            painter.fillRect(self.rect(), QPalette().color(QPalette.Dark)) # Use theme color
            painter.setPen(QPalette().color(QPalette.WindowText)) # Use theme text color
            painter.drawText(self.rect(), Qt.AlignCenter, "Waiting for screen data...")
            # Reset minimum size when no pixmap
            if self.minimumSize() != QSize(800, 600):
                self.setMinimumSize(800, 600)

        painter.end()

    def get_scaled_coords(self, widget_pos: QPoint) -> tuple[int, int]:
        """ Converts widget coordinates (e.g., from mouse event) to original remote screen coordinates. """
        if self.pixmap.isNull() or self.remote_screen_size.width() <= 1 or self.remote_screen_size.height() <= 1:
             # print("[get_scaled_coords] No pixmap or invalid remote size.")
             return 0, 0 # Cannot scale

        widget_rect = self.rect()
        original_x, original_y = 0, 0

        if self._fit_to_window:
            # Calculate the displayed pixmap's rect (centered, aspect-preserved)
            scaled_pixmap = self.pixmap.scaled(widget_rect.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            scaled_width = scaled_pixmap.width()
            scaled_height = scaled_pixmap.height()
            offset_x = (widget_rect.width() - scaled_width) / 2
            offset_y = (widget_rect.height() - scaled_height) / 2

            if scaled_width <= 0 or scaled_height <= 0: return 0,0 # Avoid division by zero

            # Check if click is within the bounds of the *displayed* pixmap
            if offset_x <= widget_pos.x() < offset_x + scaled_width and \
               offset_y <= widget_pos.y() < offset_y + scaled_height:
                # Position relative to the top-left of the scaled pixmap
                x_in_scaled = widget_pos.x() - offset_x
                y_in_scaled = widget_pos.y() - offset_y
                # Convert back to original coordinates
                original_x = (x_in_scaled / scaled_width) * self.remote_screen_size.width()
                original_y = (y_in_scaled / scaled_height) * self.remote_screen_size.height()
            else:
                # Click was outside image (in padding), clamp to nearest edge? Let's just return clamped value based on relative position
                rel_x = widget_pos.x() - offset_x
                rel_y = widget_pos.y() - offset_y
                if rel_x < 0: original_x = 0
                elif rel_x >= scaled_width: original_x = self.remote_screen_size.width()
                else: original_x = (rel_x / scaled_width) * self.remote_screen_size.width()

                if rel_y < 0: original_y = 0
                elif rel_y >= scaled_height: original_y = self.remote_screen_size.height()
                else: original_y = (rel_y / scaled_height) * self.remote_screen_size.height()
        else:
            # 1:1 mode - Coordinates are directly relative to widget origin
            # We assume the scroll area handles the view, so widget_pos IS the coordinate within the full remote screen
            original_x = widget_pos.x()
            original_y = widget_pos.y()

        # Final clamp to ensure coords are within the original image dimensions
        final_x = max(0, min(int(original_x), self.remote_screen_size.width() - 1))
        final_y = max(0, min(int(original_y), self.remote_screen_size.height() - 1))

        # print(f"[get_scaled_coords] Fit:{self._fit_to_window}, Widget:{widget_pos.x()},{widget_pos.y()} -> Original:{final_x},{final_y}")
        return final_x, final_y

    # --- Input Event Handlers ---
    # These emit signals ONLY if view_only is False

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._view_only: return
        x, y = self.get_scaled_coords(event.pos())
        self.mouse_event_signal.emit({'type': 'move', 'x': x, 'y': y})
        # Update local representation of remote cursor immediately for responsiveness
        self.update_remote_cursor(x, y)
        event.accept()

    def mousePressEvent(self, event: QMouseEvent):
        if self._view_only: return
        x, y = self.get_scaled_coords(event.pos())
        button_map = {Qt.LeftButton: 'left', Qt.RightButton: 'right', Qt.MiddleButton: 'middle'}
        button = button_map.get(event.button())
        if button:
            self.mouse_event_signal.emit({'type': 'press', 'x': x, 'y': y, 'button': button})
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._view_only: return
        x, y = self.get_scaled_coords(event.pos())
        button_map = {Qt.LeftButton: 'left', Qt.RightButton: 'right', Qt.MiddleButton: 'middle'}
        button = button_map.get(event.button())
        if button:
            self.mouse_event_signal.emit({'type': 'release', 'x': x, 'y': y, 'button': button})
        event.accept()

    def wheelEvent(self, event: QWheelEvent):
        if self._view_only: return
        # Use position() for wheel events as pos() might not be accurate for pixelDelta
        x, y = self.get_scaled_coords(event.position().toPoint())
        # Prefer pixelDelta for smoother scrolling if available, else use angleDelta
        delta = event.pixelDelta() if event.pixelDelta().y() != 0 else event.angleDelta()
        self.mouse_event_signal.emit({
            'type': 'scroll',
            'x': x, 'y': y,
            'delta_x': delta.x(), 'delta_y': delta.y()
        })
        event.accept()

    def keyPressEvent(self, event: QKeyEvent):
        if self._view_only: return
        key_str = self.get_key_string(event)
        if key_str:
            # print(f"[KeyPress] QtKey: {event.key()}, Text: '{event.text()}', Modifiers: {event.modifiers()}, Mapped: '{key_str}'") # Debug
            self.key_event_signal.emit({'type': 'press', 'key': key_str})
        event.accept()

    def keyReleaseEvent(self, event: QKeyEvent):
        if self._view_only: return
        if event.isAutoRepeat(): # Ignore auto-repeat releases
            event.ignore()
            return
        key_str = self.get_key_string(event)
        if key_str:
            # print(f"[KeyRelease] QtKey: {event.key()}, Text: '{event.text()}', Modifiers: {event.modifiers()}, Mapped: '{key_str}'") # Debug
            self.key_event_signal.emit({'type': 'release', 'key': key_str})
        event.accept()

    def get_key_string(self, event: QKeyEvent) -> str | None:
        """ Converts Qt key event to a string representation potentially usable by pyautogui or backend."""
        key = event.key()
        text = event.text()
        modifiers = event.modifiers()

        # --- Use a dictionary for better mapping ---
        # Based on pyautogui key names where possible
        qt_to_str_map = {
            Qt.Key_Control: 'ctrl', Qt.Key_Shift: 'shift', Qt.Key_Alt: 'alt',
            Qt.Key_Meta: 'cmd', # Command on Mac, Win on Windows
            Qt.Key_Return: 'enter', Qt.Key_Enter: 'enter', # Numpad Enter
            Qt.Key_Escape: 'esc', Qt.Key_Tab: 'tab', Qt.Key_Backspace: 'backspace',
            Qt.Key_Delete: 'delete', Qt.Key_Insert: 'insert',
            Qt.Key_Up: 'up', Qt.Key_Down: 'down', Qt.Key_Left: 'left', Qt.Key_Right: 'right',
            Qt.Key_Home: 'home', Qt.Key_End: 'end',
            Qt.Key_PageUp: 'pageup', Qt.Key_PageDown: 'pagedown',
            Qt.Key_F1: 'f1', Qt.Key_F2: 'f2', Qt.Key_F3: 'f3', Qt.Key_F4: 'f4',
            Qt.Key_F5: 'f5', Qt.Key_F6: 'f6', Qt.Key_F7: 'f7', Qt.Key_F8: 'f8',
            Qt.Key_F9: 'f9', Qt.Key_F10: 'f10', Qt.Key_F11: 'f11', Qt.Key_F12: 'f12',
            Qt.Key_F13: 'f13', Qt.Key_F14: 'f14', Qt.Key_F15: 'f15', Qt.Key_F16: 'f16', # Add more F keys
            Qt.Key_CapsLock: 'capslock', Qt.Key_NumLock: 'numlock', Qt.Key_ScrollLock: 'scrolllock',
            Qt.Key_Print: 'printscreen', Qt.Key_Pause: 'pause',
            # Add other special keys if needed...
            Qt.Key_Space: 'space', # Map space explicitly
        }

        # Check exact key match first (for non-printable/special keys)
        if key in qt_to_str_map:
            return qt_to_str_map[key]

        # Handle printable characters (use event.text() for correct character with modifiers)
        # Check if it's NOT a modifier key itself being pressed
        if text and text.isprintable() and key not in [Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta]:
             # Consider Shift explicitly for symbols? PyAutoGUI's typewrite usually handles this.
             # if modifiers & Qt.ShiftModifier and not text.islower() and not text.isupper():
             #     # It might be a symbol requiring shift, but typewrite should handle it
             #     pass
             return text

        # Fallback for keys not explicitly mapped (e.g., multimedia keys)
        # We could try QKeySequence(key).toString(), but it can be verbose/locale-dependent
        # print(f"[get_key_string] Unhandled key: QtKey={key}, Text='{text}', Modifiers={modifiers}")
        return None

# --- Main Application Window ---
class MainWindow(QMainWindow):
    """Main application window shown after login."""
    # --- Signals emitted to AppController ---
    request_view_signal = pyqtSignal(str) # Emitted when "Connect" button clicked
    disconnect_signal = pyqtSignal() # Emitted on disconnect button click or close
    send_chat_message_signal = pyqtSignal(str) # Emitted when chat message sent
    logout_signal = pyqtSignal() # Emitted on logout button click or window close
    start_sharing_signal = pyqtSignal() # Emitted on "Start Sharing" click
    stop_sharing_signal = pyqtSignal() # Emitted on "Stop Sharing" click
    mouse_permission_signal = pyqtSignal(bool) # Emitted when permission checkbox toggled
    quality_changed_signal = pyqtSignal(int) # Emitted from quality slider
    scale_changed_signal = pyqtSignal(int) # Emitted from scale slider
    fps_changed_signal = pyqtSignal(int) # Emitted from FPS combobox
    monitor_changed_signal = pyqtSignal(int) # Emitted from monitor combobox (1-based index)
    toggle_theme_signal = pyqtSignal() # Emitted from theme toggle button
    # Add new signals for user list management
    refresh_users_signal = pyqtSignal() # Emitted to refresh user list
    user_selected_signal = pyqtSignal(str) # Emitted when user is selected from list
    accept_connection_signal = pyqtSignal(str) # Emitted when connection is accepted
    reject_connection_signal = pyqtSignal(str) # Emitted when connection is rejected

    # Default stream settings constants
    DEFAULT_QUALITY = DEFAULT_STREAM_QUALITY
    DEFAULT_SCALE = DEFAULT_STREAM_SCALE
    DEFAULT_FPS = DEFAULT_STREAM_FPS
    DEFAULT_MONITOR_INDEX = DEFAULT_MONITOR_INDEX
    FPS_OPTIONS = [5, 10, 15, 20, 25, 30]

    # Peer Connection Status Constants (for UI state)
    PEER_STATUS_CONNECTED = "peer_connected"
    PEER_STATUS_CONNECTING = "peer_connecting"
    PEER_STATUS_DISCONNECTED = "peer_disconnected"

    # User role constants (for UI state)
    ROLE_IDLE = "idle"
    ROLE_SHARING = "sharing"
    ROLE_VIEWING = "viewing"

    def __init__(self, username="Unknown User", current_theme="dark"):
        super().__init__()
        self.username = username
        self.current_theme = current_theme
        print(f"[UI MainWindow {self.username}] Initializing...")

        # Internal state tracking
        self._connected_peer_username = ""
        self._peer_connection_status = self.PEER_STATUS_DISCONNECTED
        self._current_role = self.ROLE_IDLE
        self._is_fullscreen = False
        self._sidebar_expanded = True # Sidebar starts expanded

        # Session timer state
        self._session_start_time = None
        self._session_timer = QTimer(self)
        self._session_timer.setInterval(1000) # Update every second
        self._session_timer.timeout.connect(self._update_session_time)
        self._session_duration = 0

        self.setWindowTitle(f"SCU Remote Desktop - {self.username}")
        self.resize(1200, 768)
        self.setMinimumWidth(1000)
        self.setStyleSheet(load_stylesheet(current_theme))

        # Create UI elements
        self._create_toolbar()
        self._create_status_bar()
        self._setup_main_layout() # Merged UI setup logic

        # Connect internal signals/slots
        self.quality_changed_signal.connect(self.update_quality_display)

        # Set initial disconnected state for UI elements
        self.set_disconnected_state()
        print(f"[UI MainWindow {self.username}] Initialization complete.")

    def _create_toolbar(self):
        """Creates the main toolbar."""
        print("[UI MainWindow] Creating Toolbar...")
        toolbar = self.addToolBar("Main Toolbar")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setObjectName("main_toolbar")
        toolbar.setContentsMargins(5, 2, 5, 2)
        toolbar.layout().setSpacing(8) # Spacing between items

        # --- Left Section: Status ---
        self.peer_indicator_label = QLabel()
        self.peer_indicator_label.setObjectName("peer_status_indicator")
        self.peer_indicator_label.setFixedSize(14, 14)
        self.peer_indicator_label.setToolTip("Peer Connection Status")
        toolbar.addWidget(self.peer_indicator_label)

        self.peer_status_text_label = QLabel("Disconnected")
        self.peer_status_text_label.setObjectName("peer_status_text_label")
        toolbar.addWidget(self.peer_status_text_label)

        self.peer_status_label = QLabel("Peer: None")
        self.peer_status_label.setObjectName("peer_username_label")
        toolbar.addWidget(self.peer_status_label)

        self.role_label = QLabel("Role: Idle")
        self.role_label.setObjectName("role_label")
        toolbar.addWidget(self.role_label)

        self.session_timer_label = QLabel("Session: 00:00:00")
        self.session_timer_label.setObjectName("session_timer_label")
        self.session_timer_label.setToolTip("Current session duration")
        toolbar.addWidget(self.session_timer_label)

        toolbar.addSeparator() # Separator

        # --- Center Section: Quick Actions ---
        self.quick_share_button = QPushButton("Share Screen")
        self.quick_share_button.setObjectName("quick_share_button")
        self.quick_share_button.setToolTip("Start sharing your screen")
        self.quick_share_button.clicked.connect(self.start_sharing_signal.emit) # Emit signal
        toolbar.addWidget(self.quick_share_button)

        self.quick_stop_button = QPushButton("Stop Sharing")
        self.quick_stop_button.setObjectName("quick_stop_button")
        self.quick_stop_button.setToolTip("Stop sharing your screen")
        self.quick_stop_button.clicked.connect(self.stop_sharing_signal.emit) # Emit signal
        toolbar.addWidget(self.quick_stop_button)

        self.quick_disconnect_button = QPushButton("Disconnect Peer")
        self.quick_disconnect_button.setObjectName("quick_disconnect_button")
        self.quick_disconnect_button.setToolTip("Disconnect from current peer")
        self.quick_disconnect_button.clicked.connect(self.disconnect_signal.emit) # Emit signal
        toolbar.addWidget(self.quick_disconnect_button)

        toolbar.addSeparator() # Separator

        # --- Right Section: Icon Buttons ---
        # Use a spacer to push icons to the right
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(spacer)

        # Log Button (Placeholder)
        self.log_button = QPushButton("📄") # Document emoji
        self.log_button.setObjectName("log_button")
        self.log_button.setToolTip("Show Logs (Not Implemented)")
        self.log_button.setFlat(True)
        self.log_button.setCursor(Qt.PointingHandCursor)
        self.log_button.setMinimumSize(35, 35)
        self.log_button.clicked.connect(self._show_not_implemented_message) # Connect placeholder
        toolbar.addWidget(self.log_button)

        # Screenshot Button (Placeholder)
        self.screenshot_button = QPushButton()
        self.screenshot_button.setObjectName("screenshot_button")
        self.screenshot_button.setToolTip("Take Screenshot (Not Implemented)")
        self.screenshot_button.setIcon(QIcon("Icons/screenshot.png")) # TODO: Ensure icon exists
        self.screenshot_button.setIconSize(QSize(24, 24))
        self.screenshot_button.setFlat(True)
        self.screenshot_button.setCursor(Qt.PointingHandCursor)
        self.screenshot_button.setMinimumSize(35, 35)
        self.screenshot_button.clicked.connect(self._show_not_implemented_message) # Connect placeholder
        toolbar.addWidget(self.screenshot_button)

        # Screen Recorder Button (Placeholder)
        self.recorder_button = QPushButton()
        self.recorder_button.setObjectName("recorder_button")
        self.recorder_button.setToolTip("Toggle Recording (Not Implemented)")
        self.recorder_button.setIcon(QIcon("Icons/screen recorder.png")) # TODO: Ensure icon exists
        self.recorder_button.setIconSize(QSize(24, 24))
        self.recorder_button.setFlat(True)
        self.recorder_button.setCursor(Qt.PointingHandCursor)
        self.recorder_button.setMinimumSize(35, 35)
        self.recorder_button.clicked.connect(self._show_not_implemented_message) # Connect placeholder
        toolbar.addWidget(self.recorder_button)

        # Fullscreen Toggle Button
        self.fullscreen_button = QPushButton()
        self.fullscreen_button.setObjectName("fullscreen_button")
        self.fullscreen_button.setToolTip("Toggle Fullscreen Mode")
        self.fullscreen_button.setFlat(True)
        self.fullscreen_button.setCursor(Qt.PointingHandCursor)
        self.fullscreen_button.setMinimumSize(35, 35)
        self.fullscreen_button.setText("⛶") # Unicode expand symbol
        self.fullscreen_button.clicked.connect(self._toggle_fullscreen)
        toolbar.addWidget(self.fullscreen_button)

        # Theme Toggle Button
        self.theme_button = QPushButton()
        self.theme_button.setObjectName("theme_button")
        self.theme_button.setToolTip("Toggle Light/Dark Mode")
        self.theme_button.setFlat(True)
        self.theme_button.setCursor(Qt.PointingHandCursor)
        self.theme_button.setMinimumSize(35, 35)
        font_theme = self.theme_button.font()
        font_theme.setPointSize(14)
        self.theme_button.setFont(font_theme)
        self._update_theme_icon(self.current_theme) # Initialize
        self.theme_button.clicked.connect(self.toggle_theme_signal.emit) # Emit signal
        toolbar.addWidget(self.theme_button)

        # Logout Button
        self.toolbar_logout_button = QPushButton()
        self.toolbar_logout_button.setObjectName("toolbar_logout_button")
        self.toolbar_logout_button.setToolTip("Logout")
        self.toolbar_logout_button.setFlat(True)
        self.toolbar_logout_button.setCursor(Qt.PointingHandCursor)
        self.toolbar_logout_button.setMinimumSize(35, 35)
        self.toolbar_logout_button.setIcon(QIcon("Icons/logout.png")) # TODO: Ensure icon exists
        self.toolbar_logout_button.setIconSize(QSize(24, 24))
        self.toolbar_logout_button.clicked.connect(self.logout_signal.emit) # Emit signal
        toolbar.addWidget(self.toolbar_logout_button)

        # Initial UI update for status elements
        self._update_peer_connection_status_ui()
        self._update_role_ui()
        self._update_peer_status_ui()

    def _create_status_bar(self):
        """Creates the status bar with permanent widgets."""
        print("[UI MainWindow] Creating Status Bar...")
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)

        # Create labels for permanent widgets (right side)
        self.control_status_label = QLabel("Control: N/A")
        self.control_status_label.setObjectName("controlStatusLabel")
        self.control_status_label.setToolTip("Indicates control status (Self: Viewing, Peer: Sharing)")

        self.mode_status_label = QLabel("Mode: Idle")
        self.mode_status_label.setObjectName("modeStatusLabel")
        self.mode_status_label.setToolTip("Current interaction mode")

        self.quality_status_label = QLabel(f"Quality: {self.DEFAULT_QUALITY}%")
        self.quality_status_label.setObjectName("qualityStatusLabel")
        self.quality_status_label.setToolTip("Current stream quality setting (when sharing)")

        self.fps_status_label = QLabel("FPS: 0.0")
        self.fps_status_label.setObjectName("fpsStatusLabel")
        self.fps_status_label.setToolTip("Received frames per second (when viewing)")

        # Add labels as permanent widgets (added right-to-left for order)
        self.statusBar.addPermanentWidget(self.control_status_label)
        self.statusBar.addPermanentWidget(self._create_status_bar_separator())
        self.statusBar.addPermanentWidget(self.mode_status_label)
        self.statusBar.addPermanentWidget(self._create_status_bar_separator())
        self.statusBar.addPermanentWidget(self.quality_status_label)
        self.statusBar.addPermanentWidget(self._create_status_bar_separator())
        self.statusBar.addPermanentWidget(self.fps_status_label)

        self.show_status_message("Initializing...", 3000) # Initial message

    def _create_status_bar_separator(self):
        """Helper to create a styled vertical separator for the status bar."""
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet("QFrame { margin-left: 3px; margin-right: 3px; }") # Add spacing
        return separator

    # MODIFIED: Renamed from the second initUI
    def _setup_main_layout(self):
        """Sets up the main central widget layout (screen area and sidebar)."""
        print("[UI MainWindow] Setting up Main Layout...")
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- Left Side: Screen Display ---
        self.screen_container = QWidget()
        screen_layout = QVBoxLayout(self.screen_container)
        screen_layout.setContentsMargins(10, 10, 10, 10) # Padding around screen area

        self.scroll_area = QScrollArea()
        self.scroll_area.setBackgroundRole(QPalette.Dark)
        self.scroll_area.setWidgetResizable(False) # Important: False for 1:1, True for Fit
        self.scroll_area.setAlignment(Qt.AlignCenter) # Center content if smaller than viewport

        self.screen_display_widget = ScreenDisplayWidget(self) # Parent is MainWindow
        self.scroll_area.setWidget(self.screen_display_widget)
        screen_layout.addWidget(self.scroll_area)

        # Fit to Window Checkbox
        self.fit_checkbox = QCheckBox("Fit to Window")
        self.fit_checkbox.stateChanged.connect(self._toggle_fit_to_window)
        screen_layout.addWidget(self.fit_checkbox, alignment=Qt.AlignRight)

        # --- Right Side: Collapsible Sidebar ---
        sidebar_container = QWidget()
        sidebar_container.setObjectName("sidebar_container")
        sidebar_layout = QHBoxLayout(sidebar_container)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        # Toggle Button Container
        toggle_container = QWidget()
        toggle_container.setFixedWidth(24)
        toggle_container.setObjectName("sidebar_toggle_container")
        toggle_layout = QVBoxLayout(toggle_container)
        toggle_layout.setContentsMargins(0, 0, 0, 0)
        toggle_layout.addStretch()
        self.sidebar_toggle_button = QPushButton("❯") # Right arrow initially (expanded)
        self.sidebar_toggle_button.setObjectName("sidebar_toggle_button")
        self.sidebar_toggle_button.setFixedSize(24, 60)
        self.sidebar_toggle_button.setToolTip("Toggle Sidebar")
        self.sidebar_toggle_button.setCursor(Qt.PointingHandCursor)
        self.sidebar_toggle_button.clicked.connect(self._toggle_sidebar)
        toggle_layout.addWidget(self.sidebar_toggle_button)
        toggle_layout.addStretch()

        # Main Sidebar Widget
        self.sidebar = QWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setMinimumWidth(350) # Initial expanded width
        self.sidebar.setMaximumWidth(350) # Initial expanded width

        sidebar_content_layout = QVBoxLayout(self.sidebar)
        sidebar_content_layout.setSpacing(15)
        sidebar_content_layout.setContentsMargins(10, 10, 10, 10)

        # --- Connection GroupBox ---
        connection_groupbox = QGroupBox("Connection")
        connection_groupbox.setObjectName("connection_groupbox")
        connection_layout = QVBoxLayout()
        connection_layout.setSpacing(10)
        
        # Peer UID Input (Moved above users list)
        peer_layout = QHBoxLayout()
        peer_layout.setSpacing(5)
        peer_layout.addWidget(QLabel("Peer UID:"))
        self.peer_input = QLineEdit()
        self.peer_input.setObjectName("peer_input")  # Add object name for styling
        self.peer_input.setPlaceholderText("Enter Peer's Username")
        self.peer_input.setReadOnly(False)
        # Improved styling for the input field
        self.peer_input.setStyleSheet("""
            QLineEdit#peer_input {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #666666;
                border-radius: 4px;
                padding: 5px;
                min-height: 25px;
            }
            QLineEdit#peer_input:focus {
                border: 1px solid #0078d4;
                background-color: #333333;
            }
            QLineEdit#peer_input:disabled {
                background-color: #1a1a1a;
                color: #888888;
                border: 1px solid #444444;
            }
        """)
        peer_layout.addWidget(self.peer_input)
        connection_layout.addLayout(peer_layout)
        
        # Add Online Users List
        users_groupbox = QGroupBox("Online Users")
        users_groupbox.setObjectName("users_groupbox")
        users_layout = QVBoxLayout()
        users_layout.setSpacing(5)
        
        # User list widget
        self.users_list = QListWidget()
        self.users_list.setObjectName("users_list")
        self.users_list.setSelectionMode(QListWidget.SingleSelection)
        self.users_list.setMinimumHeight(150) # Set minimum height
        self.users_list.setAlternatingRowColors(True) # Alternate row colors
        self.users_list.itemClicked.connect(self._on_user_selected)
        users_layout.addWidget(self.users_list)
        
        # Refresh button
        refresh_button = QPushButton("Refresh")
        refresh_button.setObjectName("refresh_users_button")
        refresh_button.setToolTip("Refresh list of online users")
        refresh_button.setIcon(QIcon("Icons/refresh.png")) # TODO: Add refresh icon
        refresh_button.setIconSize(QSize(16, 16))
        refresh_button.clicked.connect(self.refresh_users_signal.emit)
        users_layout.addWidget(refresh_button)
        
        users_groupbox.setLayout(users_layout)
        connection_layout.addWidget(users_groupbox)
        
        # Connection buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(5)
        self.request_view_button = QPushButton("Connect")
        self.request_view_button.setObjectName("connect_button")
        self.request_view_button.setToolTip("Request to view peer's screen")
        self.request_view_button.setIcon(QIcon("Icons/connect.png")) # TODO: Add connect icon
        self.request_view_button.setIconSize(QSize(16, 16))
        self.request_view_button.clicked.connect(self.on_request_view_clicked)
        buttons_layout.addWidget(self.request_view_button)
        
        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.setObjectName("disconnect_button")
        self.disconnect_button.setToolTip("Disconnect from current peer")
        self.disconnect_button.setIcon(QIcon("Icons/disconnect.png")) # TODO: Add disconnect icon
        self.disconnect_button.setIconSize(QSize(16, 16))
        self.disconnect_button.clicked.connect(self.disconnect_signal.emit)
        buttons_layout.addWidget(self.disconnect_button)
        
        connection_layout.addLayout(buttons_layout)
        connection_groupbox.setLayout(connection_layout)
        sidebar_content_layout.addWidget(connection_groupbox)

        # --- Stream Controls Container ---
        stream_controls_container = QWidget()
        stream_controls_container.setObjectName("stream_controls_container")
        stream_controls_layout = QVBoxLayout(stream_controls_container)
        stream_controls_layout.setSpacing(15)
        stream_controls_layout.setContentsMargins(0, 0, 0, 0)

        # Sharer Control GroupBox
        self.sharer_groupbox = QGroupBox("Share Screen Controls")
        self.sharer_groupbox.setObjectName("sharer_groupbox")
        sharer_layout = QVBoxLayout()
        self.sharer_groupbox.setLayout(sharer_layout)
        # MODIFIED: State managed by set_connected/disconnected
        # self.sharer_groupbox.setEnabled(False) # Initially disabled

        sharing_buttons_layout = QHBoxLayout()
        self.start_sharing_button = QPushButton("Start Sharing")
        self.start_sharing_button.setObjectName("start_sharing_button")
        self.start_sharing_button.clicked.connect(self.start_sharing_signal.emit) # Emit signal
        sharing_buttons_layout.addWidget(self.start_sharing_button)
        self.stop_sharing_button = QPushButton("Stop Sharing")
        self.stop_sharing_button.setObjectName("stop_sharing_button")
        self.stop_sharing_button.clicked.connect(self.stop_sharing_signal.emit) # Emit signal
        sharing_buttons_layout.addWidget(self.stop_sharing_button)
        sharer_layout.addLayout(sharing_buttons_layout)
        stream_controls_layout.addWidget(self.sharer_groupbox)

        # Stream Settings GroupBox
        self.settings_groupbox = QGroupBox("Stream Settings")
        self.settings_groupbox.setObjectName("settings_groupbox")
        # MODIFIED: State managed by set_connected/disconnected
        # self.settings_groupbox.setVisible(False) # Initially hidden
        # self.settings_groupbox.setEnabled(False) # Initially disabled
        settings_layout = QFormLayout(self.settings_groupbox)
        # ... (Monitor, Quality, Scale, FPS, Reset - layout unchanged) ...
        # Monitor Selection
        monitor_layout = QHBoxLayout()
        self.monitor_combobox = QComboBox()
        self.monitor_combobox.setObjectName("monitor_combobox")
        self.monitor_combobox.setToolTip("Select which monitor to share")
        self._populate_monitor_combobox() # Populate with available monitors
        self.monitor_combobox.currentIndexChanged.connect(self._emit_monitor_index)
        monitor_layout.addWidget(self.monitor_combobox, 1)
        settings_layout.addRow("Monitor:", monitor_layout)
        # Quality Slider
        quality_layout = QHBoxLayout()
        self.quality_slider = QSlider(Qt.Horizontal)
        self.quality_slider.setObjectName("quality_slider")
        self.quality_slider.setToolTip("Higher quality = better image, more bandwidth")
        self.quality_slider.setRange(10, 100)
        self.quality_slider.setValue(self.DEFAULT_QUALITY)
        self.quality_slider.setTickInterval(10)
        self.quality_slider.setTickPosition(QSlider.TicksBelow)
        self.quality_label = QLabel(f"{self.DEFAULT_QUALITY}%")
        self.quality_label.setObjectName("quality_value_label")
        self.quality_label.setMinimumWidth(40)
        self.quality_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.quality_slider.valueChanged.connect(self._update_quality_label_and_emit)
        quality_layout.addWidget(self.quality_slider, 1)
        quality_layout.addWidget(self.quality_label)
        settings_layout.addRow("Quality:", quality_layout)
        # Scale Slider
        scale_layout = QHBoxLayout()
        self.scale_slider = QSlider(Qt.Horizontal)
        self.scale_slider.setObjectName("scale_slider")
        self.scale_slider.setToolTip("Scale down image to reduce bandwidth")
        self.scale_slider.setRange(25, 100)
        self.scale_slider.setValue(self.DEFAULT_SCALE)
        self.scale_slider.setTickInterval(25)
        self.scale_slider.setTickPosition(QSlider.TicksBelow)
        self.scale_label = QLabel(f"{self.DEFAULT_SCALE}%")
        self.scale_label.setObjectName("scale_value_label")
        self.scale_label.setMinimumWidth(40)
        self.scale_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.scale_slider.valueChanged.connect(self._update_scale_label_and_emit)
        scale_layout.addWidget(self.scale_slider, 1)
        scale_layout.addWidget(self.scale_label)
        settings_layout.addRow("Scale:", scale_layout)
        # FPS ComboBox
        fps_layout = QHBoxLayout()
        self.fps_combobox = QComboBox()
        self.fps_combobox.setObjectName("fps_combobox")
        self.fps_combobox.setToolTip("Higher FPS = smoother video, more bandwidth")
        for fps_option in self.FPS_OPTIONS:
            self.fps_combobox.addItem(str(fps_option), userData=fps_option)
        default_fps_index = self.fps_combobox.findData(self.DEFAULT_FPS)
        if default_fps_index != -1:
            self.fps_combobox.setCurrentIndex(default_fps_index)
        self.fps_combobox.currentIndexChanged.connect(self._emit_fps_value)
        fps_layout.addWidget(self.fps_combobox, 1)
        settings_layout.addRow("Max FPS:", fps_layout)
        # Reset Button
        reset_layout = QHBoxLayout()
        self.reset_settings_button = QPushButton("Reset to Default")
        self.reset_settings_button.setObjectName("reset_settings_button")
        self.reset_settings_button.setToolTip("Reset stream settings to default values")
        self.reset_settings_button.clicked.connect(self._reset_stream_settings)
        reset_layout.addStretch(1)
        reset_layout.addWidget(self.reset_settings_button)
        settings_layout.addRow("", reset_layout)
        # Add settings groupbox to container
        stream_controls_layout.addWidget(self.settings_groupbox)
        # Add container to sidebar
        sidebar_content_layout.addWidget(stream_controls_container)

        # --- Mouse Control Checkbox ---
        self.mouse_permission_checkbox = QCheckBox("Allow Peer Mouse Control")
        self.mouse_permission_checkbox.setObjectName("mouse_permission_checkbox")
        self.mouse_permission_checkbox.setToolTip("Allow connected peer to control your mouse/keyboard when sharing")
        self.mouse_permission_checkbox.toggled.connect(self._toggle_mouse_permission)
        self.mouse_permission_checkbox.toggled.connect(self.update_control_status_display)
        # MODIFIED: State managed by set_sharing_state
        # self.mouse_permission_checkbox.setEnabled(False) # Initially disabled
        sidebar_content_layout.addWidget(self.mouse_permission_checkbox)

        # --- Chat Area ---
        self.chat_groupbox = QGroupBox("Chat")
        self.chat_groupbox.setObjectName("chat_groupbox")
        chat_layout = QVBoxLayout()
        self.chat_display = QPlainTextEdit()
        self.chat_display.setObjectName("chat_display")
        self.chat_display.setReadOnly(True)
        chat_layout.addWidget(self.chat_display)
        chat_input_layout = QHBoxLayout()
        self.chat_input = QLineEdit()
        self.chat_input.setObjectName("chat_input")
        self.chat_input.setPlaceholderText("Enter chat message...")
        self.chat_send_button = QPushButton("Send")
        self.chat_send_button.setObjectName("chat_send_button")
        self.chat_send_button.clicked.connect(self.on_chat_send)
        self.chat_input.returnPressed.connect(self.on_chat_send) # Send on Enter
        chat_input_layout.addWidget(self.chat_input)
        chat_input_layout.addWidget(self.chat_send_button)
        chat_layout.addLayout(chat_input_layout)
        self.chat_groupbox.setLayout(chat_layout)
        sidebar_content_layout.addWidget(self.chat_groupbox)
        sidebar_content_layout.addStretch() # Push controls to the top

        # Add toggle and sidebar to sidebar container
        sidebar_layout.addWidget(toggle_container)
        sidebar_layout.addWidget(self.sidebar)

        # Add screen container and sidebar container to main layout
        main_layout.addWidget(self.screen_container, 1) # Give screen stretch factor
        main_layout.addWidget(sidebar_container, 0) # No stretch for sidebar

        # --- Sidebar Animation Setup ---
        self.sidebar_animation = QPropertyAnimation(self.sidebar, b"minimumWidth")
        self.sidebar_animation.setDuration(300) # Animation duration in ms
        self.sidebar_animation.setEasingCurve(QEasingCurve.InOutQuad)
        self.sidebar_animation_max = QPropertyAnimation(self.sidebar, b"maximumWidth")
        self.sidebar_animation_max.setDuration(300)
        self.sidebar_animation_max.setEasingCurve(QEasingCurve.InOutQuad)

    # --- UI Update Methods (Called by AppController or Internally) ---

    def set_connected_state(self, connected_to_uid):
        """Updates UI elements for the 'connected' state."""
        print(f"[UI MainWindow] Setting connected state for peer: {connected_to_uid}")
        self._connected_peer_username = connected_to_uid
        self.set_peer_connection_status(self.PEER_STATUS_CONNECTED) # Set status state
        self._update_peer_status_ui() # Update toolbar labels

        # Connection Group Controls
        self.request_view_button.setEnabled(False)
        self.disconnect_button.setEnabled(True)
        self.peer_input.setEnabled(False)
        self.peer_input.setText(connected_to_uid) # Show connected peer UID

        # Sharing Group Controls (Enable group, manage buttons based on *sharing* state)
        self.sharer_groupbox.setEnabled(True)
        # Start/Stop buttons are handled by set_sharing_state/set_viewing_state

        # Stream Settings Group (Always visible and enabled when connected)
        self.settings_groupbox.setVisible(True)
        self.settings_groupbox.setEnabled(True)

        # Mouse Permission Checkbox (State depends on sharing status)
        # Enablement handled by set_sharing_state

        # Chat Group
        self.chat_groupbox.setEnabled(True)

        # Toolbar Quick Actions
        self.quick_disconnect_button.setEnabled(True)
        # Share/Stop buttons handled by set_sharing_state/set_viewing_state

        self._start_session_timer()
        self.show_status_message(f"Connected to {connected_to_uid}")
        self.append_chat_message(f"-- Connected to {connected_to_uid} --")

    def set_disconnected_state(self, message="Ready"):
        """Updates UI elements for the 'disconnected' state."""
        print(f"[UI MainWindow] Setting disconnected state. Message: {message}")
        self._connected_peer_username = ""
        self.set_peer_connection_status(self.PEER_STATUS_DISCONNECTED) # Set status state
        self._update_peer_status_ui() # Update toolbar labels
        self.set_role(self.ROLE_IDLE) # Reset role

        # Connection Group Controls
        self.request_view_button.setEnabled(True)
        self.disconnect_button.setEnabled(False)
        self.peer_input.setEnabled(True)
        self.peer_input.clear() # Clear peer input

        # Sharing Group Controls (Disable group, reset buttons)
        self.sharer_groupbox.setEnabled(False)
        self.start_sharing_button.setEnabled(False)
        self.stop_sharing_button.setEnabled(False)

        # Stream Settings Group (Hide and disable)
        self.settings_groupbox.setVisible(False)
        self.settings_groupbox.setEnabled(False)

        # Mouse Permission Checkbox (Disable and uncheck)
        self.mouse_permission_checkbox.setEnabled(False)
        self.mouse_permission_checkbox.setChecked(False)

        # Chat Group
        self.chat_groupbox.setEnabled(False)
        # self.chat_display.clear() # Optional: Clear chat on disconnect

        # Toolbar Quick Actions
        self.quick_disconnect_button.setEnabled(False)
        self.quick_share_button.setEnabled(False)
        self.quick_stop_button.setEnabled(False)

        # Screen Display
        self.screen_display_widget.pixmap = QPixmap() # Clear image
        self.screen_display_widget.set_view_only(True) # Ensure view only
        self.screen_display_widget.update() # Repaint

        self._stop_session_timer()
        self._update_session_time() # Reset timer display
        self.show_status_message(message)
        self.update_fps_display(0.0) # Reset FPS display
        if message != "Ready": # Avoid duplicate messages if just resetting
             self.append_chat_message(f"-- {message} --")

    def set_sharing_state(self, is_sharing):
        """Updates UI elements based on whether *this client* is sharing."""
        print(f"[UI MainWindow] Setting sharing state: {is_sharing}")
        self.set_role(self.ROLE_SHARING if is_sharing else self.ROLE_IDLE)

        # Update buttons in Sharer GroupBox
        self.start_sharing_button.setEnabled(not is_sharing)
        self.stop_sharing_button.setEnabled(is_sharing)

        # Update Toolbar Quick Actions
        # Can only share/stop if connected
        peer_connected = bool(self._connected_peer_username)
        self.quick_share_button.setEnabled(not is_sharing and peer_connected)
        self.quick_stop_button.setEnabled(is_sharing and peer_connected)

        # Enable/Disable Mouse Permission Checkbox
        self.mouse_permission_checkbox.setEnabled(is_sharing)
        if not is_sharing: # Uncheck if stopped sharing
            self.mouse_permission_checkbox.setChecked(False)

        # Update Control Status display
        self.update_control_status_display()

        # Update main status message
        status_msg = "Sharing screen" if is_sharing else "Screen sharing stopped"
        if self._connected_peer_username:
             status_msg += f" with {self._connected_peer_username}"
        self.show_status_message(status_msg)

    def set_viewing_state(self, is_viewing):
        """Updates UI elements based on whether *this client* is viewing."""
        print(f"[UI MainWindow] Setting viewing state: {is_viewing}")
        self.set_role(self.ROLE_VIEWING if is_viewing else self.ROLE_IDLE)

        # When viewing, we cannot share
        self.quick_share_button.setEnabled(False)
        self.quick_stop_button.setEnabled(False)
        self.sharer_groupbox.setEnabled(False) # Disable sharing controls group

        # Ensure settings are visible (if connected) but maybe disable them?
        # Let's keep settings enabled for now, might be useful for reference.
        if self._connected_peer_username:
            self.settings_groupbox.setVisible(True)
            self.settings_groupbox.setEnabled(True)

        # Mouse permission checkbox is irrelevant when viewing
        self.mouse_permission_checkbox.setEnabled(False)
        self.mouse_permission_checkbox.setChecked(False)

        # Update Control Status display (reflects if WE can control THEM)
        self.update_control_status_display()

        # Update main status message
        status_msg = f"Viewing {self._connected_peer_username}'s screen" if is_viewing else "Stopped viewing"
        self.show_status_message(status_msg)

    def set_peer_connection_status(self, status):
        """Sets the internal peer connection status state."""
        if status not in [self.PEER_STATUS_CONNECTED, self.PEER_STATUS_CONNECTING, self.PEER_STATUS_DISCONNECTED]:
            print(f"[UI MainWindow ERROR] Invalid peer connection status: {status}")
            return
        self._peer_connection_status = status
        self._update_peer_connection_status_ui() # Update visual indicator

    def set_role(self, role):
        """Sets the internal user role state."""
        if role not in [self.ROLE_IDLE, self.ROLE_SHARING, self.ROLE_VIEWING]:
            print(f"[UI MainWindow ERROR] Invalid role: {role}")
            return
        self._current_role = role
        self._update_role_ui() # Update visual indicator
        self.update_control_status_display() # Control status depends on role

    # --- Methods to update UI elements ---

    def append_chat_message(self, message):
        """Appends a message to the chat display."""
        # Simple plain text append for now
        self.chat_display.appendPlainText(message)

    def show_status_message(self, status, timeout=0):
        """Shows a temporary message in the status bar's main area."""
        # print(f"[UI Status] {status}") # Optional logging
        self.statusBar.showMessage(status, timeout)

    def update_quality_display(self, quality):
        """Updates the Quality status bar label."""
        self.quality_status_label.setText(f"Quality: {quality}%")

    # ADDED: Method to update FPS display
    def update_fps_display(self, fps):
        """Updates the FPS status bar label."""
        # Format FPS to one decimal place
        self.fps_status_label.setText(f"FPS: {fps:.1f}")

    def update_control_status_display(self):
        """Updates the Control status bar label based on role and permissions."""
        status_text = "Control: N/A"
        if self._current_role == self.ROLE_SHARING:
            # When sharing, status reflects if PEER can control US
            peer_has_control = self.mouse_permission_checkbox.isChecked()
            status_text = f"Control: {'Enabled (Peer)' if peer_has_control else 'Disabled (Peer)'}"
        elif self._current_role == self.ROLE_VIEWING:
            # When viewing, status reflects if WE can control PEER
            we_have_control = not self.screen_display_widget._view_only
            status_text = f"Control: {'Enabled (Self)' if we_have_control else 'View-Only (Self)'}"

        self.control_status_label.setText(status_text)

    # --- Methods to update Toolbar UI ---

    def _update_peer_connection_status_ui(self):
        """Updates the Peer connection status indicator and text in the toolbar."""
        status = self._peer_connection_status
        indicator_style_base = "border-radius: 7px; border: 1px solid grey;" # Base style

        if status == self.PEER_STATUS_CONNECTED:
            self.peer_indicator_label.setStyleSheet(indicator_style_base + " background-color: #4CAF50;") # Green
            self.peer_status_text_label.setText("Connected")
        elif status == self.PEER_STATUS_CONNECTING:
            self.peer_indicator_label.setStyleSheet(indicator_style_base + " background-color: #FFC107;") # Yellow
            self.peer_status_text_label.setText("Connecting...")
        else: # Disconnected
            self.peer_indicator_label.setStyleSheet(indicator_style_base + " background-color: #F44336;") # Red
            self.peer_status_text_label.setText("Disconnected")

    def _update_role_ui(self):
        """Updates the role label in the toolbar."""
        role_map = {
            self.ROLE_IDLE: "Idle",
            self.ROLE_SHARING: "Sharing",
            self.ROLE_VIEWING: "Viewing"
        }
        self.role_label.setText(f"Role: {role_map.get(self._current_role, 'Unknown')}")

    def _update_peer_status_ui(self):
        """Updates the peer username label in the toolbar."""
        if self._connected_peer_username:
            self.peer_status_label.setText(f"Peer: {self._connected_peer_username}")
        else:
            self.peer_status_label.setText("Peer: None")

    # --- Session Timer Methods ---

    def _start_session_timer(self):
        """Starts or restarts the session timer."""
        print("[UI MainWindow] Starting session timer.")
        self._session_start_time = time.time()
        self._session_duration = 0
        if not self._session_timer.isActive():
            self._session_timer.start()
        self._update_session_time() # Update display immediately

    def _stop_session_timer(self):
        """Stops the session timer."""
        if self._session_timer.isActive():
            print("[UI MainWindow] Stopping session timer.")
            self._session_timer.stop()
        self._session_start_time = None

    def _update_session_time(self):
        """Updates the session duration display (HH:MM:SS)."""
        if self._session_start_time is not None:
            self._session_duration = int(time.time() - self._session_start_time)

        hours = self._session_duration // 3600
        minutes = (self._session_duration % 3600) // 60
        seconds = self._session_duration % 60
        time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        self.session_timer_label.setText(f"Session: {time_str}")

    # --- Event Handlers & Slots for UI Actions ---

    def on_chat_send(self):
        """Handles click on chat send button or Enter in input."""
        message = self.chat_input.text().strip()
        if message:
            self.send_chat_message_signal.emit(message) # Emit signal to controller
            self.chat_input.clear()

    def on_request_view_clicked(self):
        """Handles click on the 'Connect' button."""
        peer_uid = self.peer_input.text().strip()
        if not peer_uid:
            QMessageBox.warning(self, "Input Required", "Please enter a peer UID to connect to.")
            return
            
        if peer_uid == self.username:
            QMessageBox.warning(self, "Invalid Selection", "Cannot connect to yourself.")
            return
            
        # Set connecting status
        self.set_peer_connection_status(self.PEER_STATUS_CONNECTING)
        self.request_view_button.setEnabled(False)
        self.disconnect_button.setEnabled(True)
        
        # Emit signal to controller
        self.request_view_signal.emit(peer_uid)
        
        # Show status message
        self.show_status_message(f"Requesting connection to {peer_uid}...")

    def handle_connection_request(self, from_uid):
        """Handles incoming connection request from another user."""
        reply = QMessageBox.question(
            self,
            "Connection Request",
            f"User {from_uid} wants to connect to your screen. Allow connection?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.show_status_message(f"Accepted connection from {from_uid}")
            # Emit signal to accept connection
            self.accept_connection_signal.emit(from_uid)
        else:
            self.show_status_message(f"Rejected connection from {from_uid}")
            # Emit signal to reject connection
            self.reject_connection_signal.emit(from_uid)

    def start_auto_refresh(self):
        """Starts automatic refresh of online users list."""
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_users_signal.emit)
        self.refresh_timer.start(5000)  # Refresh every 5 seconds

    def stop_auto_refresh(self):
        """Stops automatic refresh of online users list."""
        if hasattr(self, 'refresh_timer'):
            self.refresh_timer.stop()

    def _toggle_fit_to_window(self, state):
        """Handles the 'Fit to Window' checkbox state change."""
        fit_enabled = (state == Qt.Checked)
        self.screen_display_widget.set_fit_to_window(fit_enabled)
        self.scroll_area.setWidgetResizable(fit_enabled) # Crucial for scroll area behavior
        if not fit_enabled:
            self.screen_display_widget.adjustSize() # Ensure widget resizes for scrollbars if needed
        else:
             # Ensure widget can shrink when fitting - important!
            self.screen_display_widget.setMinimumSize(1, 1)
            self.screen_display_widget.updateGeometry() # Trigger relayout

    def _toggle_mouse_permission(self, state):
        """Emits signal when mouse permission checkbox is toggled by user."""
        # Only relevant when sharing, enabled state is managed by set_sharing_state
        permission_enabled = (state == Qt.Checked)
        print(f"[UI MainWindow] Mouse permission checkbox toggled by user: {permission_enabled}")
        self.mouse_permission_signal.emit(permission_enabled) # Emit signal to controller

    def _toggle_fullscreen(self):
        """Toggles the main window fullscreen mode."""
        if self.isFullScreen():
            self.showNormal()
            self.fullscreen_button.setText("⛶") # Unicode expand symbol
            self.fullscreen_button.setToolTip("Enter Fullscreen Mode")
            self._is_fullscreen = False
        else:
            self.showFullScreen()
            self.fullscreen_button.setText("⮧") # Unicode exit fullscreen symbol (alternative)
            self.fullscreen_button.setToolTip("Exit Fullscreen Mode")
            self._is_fullscreen = True

    def _toggle_sidebar(self):
        """Animates the sidebar collapse/expand."""
        start_width = self.sidebar.width()
        target_width = 0 if self._sidebar_expanded else 350

        self.sidebar_animation.setStartValue(start_width)
        self.sidebar_animation.setEndValue(target_width)
        self.sidebar_animation_max.setStartValue(start_width)
        self.sidebar_animation_max.setEndValue(target_width)

        self.sidebar_animation.start()
        self.sidebar_animation_max.start()

        self.sidebar_toggle_button.setText("❮" if self._sidebar_expanded else "❯") # Update arrow
        self._sidebar_expanded = not self._sidebar_expanded

    def _populate_monitor_combobox(self):
        """Populates the monitor selection combobox."""
        try:
            monitors = screeninfo.get_monitors()
            self.monitor_combobox.clear()
            if not monitors:
                self.monitor_combobox.addItem("No monitors found", userData=-1)
                self.monitor_combobox.setEnabled(False)
                return

            primary_monitor_index = -1
            for i, monitor in enumerate(monitors):
                monitor_label = f"Monitor {i+1}: {monitor.width}x{monitor.height}"
                if monitor.is_primary:
                    monitor_label += " (Primary)"
                    primary_monitor_index = i
                # Store 1-based index in userData for controller logic
                self.monitor_combobox.addItem(monitor_label, userData=i + 1)

            # Set default selection (Prefer primary, fallback to index or first)
            default_selection_index = 0 # Fallback to first monitor
            if self.DEFAULT_MONITOR_INDEX - 1 < len(monitors):
                 default_selection_index = self.DEFAULT_MONITOR_INDEX - 1
            if primary_monitor_index != -1 : # Prefer primary if found
                 default_selection_index = primary_monitor_index

            self.monitor_combobox.setCurrentIndex(default_selection_index)
            self.monitor_combobox.setEnabled(True)

        except Exception as e: # Catch potential screeninfo errors or others
            print(f"[UI ERROR] Could not get monitor info: {e}")
            self.monitor_combobox.clear()
            self.monitor_combobox.addItem("Error getting monitors", userData=-1)
            self.monitor_combobox.setEnabled(False)

    def _emit_monitor_index(self, index):
        """Emits the 1-based index of the selected monitor."""
        monitor_index_data = self.monitor_combobox.itemData(index)
        if monitor_index_data and monitor_index_data != -1:
            self.monitor_changed_signal.emit(monitor_index_data) # Emit 1-based index

    def _update_quality_label_and_emit(self, value):
        """Updates quality label and emits signal."""
        self.quality_label.setText(f"{value}%")
        self.quality_changed_signal.emit(value)

    def _update_scale_label_and_emit(self, value):
        """Updates scale label and emits signal."""
        self.scale_label.setText(f"{value}%")
        self.scale_changed_signal.emit(value)

    def _emit_fps_value(self, index):
        """Emits the selected FPS value."""
        fps_data = self.fps_combobox.itemData(index)
        if fps_data:
            self.fps_changed_signal.emit(fps_data)

    def _reset_stream_settings(self):
        """Resets stream settings UI controls to default values."""
        print("[UI MainWindow] Resetting stream settings UI.")
        # Reset quality slider (will trigger signal)
        self.quality_slider.setValue(self.DEFAULT_QUALITY)
        # Reset scale slider (will trigger signal)
        self.scale_slider.setValue(self.DEFAULT_SCALE)
        # Reset FPS combobox (will trigger signal)
        default_fps_index = self.fps_combobox.findData(self.DEFAULT_FPS)
        if default_fps_index != -1:
            self.fps_combobox.setCurrentIndex(default_fps_index)
        # Reset monitor combobox (will trigger signal)
        try:
            monitors = screeninfo.get_monitors()
            primary_monitor_index = -1
            default_selection_index = 0
            if monitors:
                 for i, m in enumerate(monitors):
                      if m.is_primary:
                           primary_monitor_index = i
                           break
                 if self.DEFAULT_MONITOR_INDEX - 1 < len(monitors):
                      default_selection_index = self.DEFAULT_MONITOR_INDEX - 1
                 if primary_monitor_index != -1:
                      default_selection_index = primary_monitor_index
            self.monitor_combobox.setCurrentIndex(default_selection_index)
        except Exception:
            pass # Ignore errors resetting monitor combo

        self.show_status_message("Stream settings reset to defaults", 3000)

    def _update_theme_icon(self, theme_name):
        """Updates the theme toggle button icon in the toolbar."""
        if theme_name == "dark":
            emoji = "☀️"
            tooltip = "Switch to Light Mode"
        else:
            emoji = "🌙"
            tooltip = "Switch to Dark Mode"
        self.theme_button.setText(emoji)
        self.theme_button.setToolTip(tooltip)
        font = self.theme_button.font()
        font.setPointSize(14)
        self.theme_button.setFont(font)

    def _show_not_implemented_message(self):
         """Placeholder for unimplemented toolbar actions."""
         QMessageBox.information(self, "Not Implemented", "This feature is not yet implemented.")

    # --- Override closeEvent ---
    def closeEvent(self, event):
        """Ensures logout signal is emitted when window is closed."""
        print("[UI MainWindow] Close event triggered. Emitting logout signal.")
        self.logout_signal.emit() # Signal AppController to handle cleanup
        event.accept() # Allow window to close

    def _on_user_selected(self, item):
        """Handles user selection from the online users list."""
        if item:
            # Extract username from the item text (remove status indicator)
            selected_uid = item.text().split(" ", 1)[1]
            self.peer_input.setText(selected_uid)
            self.user_selected_signal.emit(selected_uid)

    def update_users_list(self, users):
        """Updates the online users list with the provided users."""
        self.users_list.clear()
        for user in users:
            if user != self.username:  # Don't show self in the list
                item = QListWidgetItem(user)
                # Add status indicator
                status = "🟢"  # Green dot for online
                item.setText(f"{status} {user}")
                self.users_list.addItem(item)

    def handle_connection_timeout(self):
        """Handles connection timeout."""
        self.set_peer_connection_status(self.PEER_STATUS_DISCONNECTED)
        self.request_view_button.setEnabled(True)
        self.disconnect_button.setEnabled(False)
        self.show_status_message("Connection attempt timed out")
        QMessageBox.warning(self, "Connection Timeout", "The connection attempt timed out. Please try again.")
        
        # TODO: API Integration
        # 1. Implement proper timeout handling from API
        # 2. Add retry mechanism
        # 3. Add connection status polling

    def handle_connection_error(self, error_message):
        """Handles connection errors."""
        self.set_peer_connection_status(self.PEER_STATUS_DISCONNECTED)
        self.request_view_button.setEnabled(True)
        self.disconnect_button.setEnabled(False)
        self.show_status_message(f"Connection error: {error_message}")
        QMessageBox.critical(self, "Connection Error", f"Failed to connect: {error_message}")
        
        # TODO: API Integration
        # 1. Implement proper error handling from API
        # 2. Add error categorization
        # 3. Add error recovery mechanisms
        # 4. Add error logging

    def handle_connection_refused(self, reason=""):
        """Handles connection refusal."""
        self.set_peer_connection_status(self.PEER_STATUS_DISCONNECTED)
        self.request_view_button.setEnabled(True)
        self.disconnect_button.setEnabled(False)
        message = f"Connection refused{f': {reason}' if reason else ''}"
        self.show_status_message(message)
        QMessageBox.information(self, "Connection Refused", message)
        
        # TODO: API Integration
        # 1. Implement proper refusal handling from API
        # 2. Add refusal reason parsing
        # 3. Add retry options
        # 4. Add user notification preferences

def load_stylesheet(theme):
    """Loads the stylesheet for the specified theme."""
    filename = os.path.join(STYLES_DIR, f"{theme}.qss")
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        logging.warning(f"Stylesheet file '{filename}' not found.")
        return ""
    except Exception as e:
        logging.error(f"Failed to load stylesheet '{filename}': {e}")
        return ""

# --- Main Execution Guard (Optional for UI file, but good practice) ---
# if __name__ == '__main__':
#     app = QApplication(sys.argv)
#
#     # Example Usage (for testing UI components standalone)
#     # login_win = LoginWindow()
#     # login_win.show()
#
#     main_win = MainWindow(username="TestUser")
#     main_win.show()
#
#     sys.exit(app.exec_())