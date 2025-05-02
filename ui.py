import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QLineEdit, QGroupBox, QRadioButton, QDialog, QMessageBox,
    QScrollArea, QFormLayout, QMainWindow, QAction, QStatusBar, QTextEdit,
    QSplitter, QSlider, QSpinBox, QComboBox, QCheckBox, QSizePolicy, QPlainTextEdit,
    QSpacerItem # Import QSpacerItem
)
from PyQt5.QtGui import QPixmap, QImage, QPainter, QPen, QCursor, QFont, QPalette, QIcon
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize
import utils # Import utils to get monitor list
import screeninfo # To get monitor info

class LoginWindow(QWidget):
    """Window for user login."""
    # Signal emits backend_url, username, password
    login_attempt_signal = pyqtSignal(str, str, str)
    toggle_theme_signal = pyqtSignal() # Signal to toggle theme
    # Add signals for new buttons if needed later
    # register_signal = pyqtSignal()
    # guest_login_signal = pyqtSignal()

    def __init__(self, default_backend_url="http://127.0.0.1:8000"): # Default to localhost backend
        super().__init__()
        self.default_backend_url = default_backend_url
        self.initUI()

    def initUI(self):
        self.setWindowTitle("SCU Remote Desktop - Login") # Changed title
        self.setMinimumWidth(400) # Give it a bit more width

        # --- Top Layout (for Title Bar elements) --- 
        top_layout = QHBoxLayout()
        top_layout.addStretch(1) # Push button to the right

        # Theme Toggle Button
        self.theme_button = QPushButton()
        self.theme_button.setObjectName("theme_button")
        self.theme_button.setToolTip("Toggle Light/Dark Mode")
        self.theme_button.setFlat(True) # Make background transparent initially
        self.theme_button.setCursor(Qt.PointingHandCursor)
        
        # Set initial size and styling for emoji
        self.theme_button.setMinimumSize(35, 35)
        font = self.theme_button.font()
        font.setPointSize(14)  # Larger font for emoji
        self.theme_button.setFont(font)
        
        # Initialize with the dark theme icon (sun emoji)
        self._update_theme_icon("dark") # Assume starting dark
        self.theme_button.clicked.connect(self.toggle_theme_signal.emit) # Emit signal
        top_layout.addWidget(self.theme_button)

        # --- Main Content Layout --- 
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(30, 0, 30, 30) # Adjust margins
        content_layout.setSpacing(15) # Add spacing between elements

        # Logo Placeholder
        self.logo_label = QLabel("SCU Logo Placeholder") # Placeholder
        self.logo_label.setObjectName("logo_label") # Set object name
        self.logo_label.setAlignment(Qt.AlignCenter)
        # --- Load actual logo --- 
        pixmap = QPixmap('logo.png') 
        if not pixmap.isNull():
             # Scale the logo while keeping aspect ratio
             self.logo_label.setPixmap(pixmap.scaled(150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
             self.logo_label.setText("[Logo Not Found]") # Fallback text
        # --- End Load actual logo --- 
        content_layout.addWidget(self.logo_label)

        # Title Labels
        self.title_label1 = QLabel("SCU Remote Desktop")
        self.title_label1.setObjectName("title_label1") # Set object name
        self.title_label1.setAlignment(Qt.AlignCenter)
        font1 = self.title_label1.font()
        font1.setPointSize(14)
        font1.setBold(True)
        self.title_label1.setFont(font1)
        content_layout.addWidget(self.title_label1)

        self.title_label2 = QLabel("Remote Control System")
        self.title_label2.setObjectName("title_label2") # Set object name
        self.title_label2.setAlignment(Qt.AlignCenter)
        font2 = self.title_label2.font()
        font2.setPointSize(10)
        self.title_label2.setFont(font2)
        content_layout.addWidget(self.title_label2)

        # Spacer
        content_layout.addSpacing(20)

        # Backend URL (Kept for now)
        self.backend_label = QLabel("Backend URL:")
        self.backend_label.setObjectName("backend_label")
        self.backend_input = QLineEdit(self)
        self.backend_input.setText(self.default_backend_url)
        content_layout.addWidget(self.backend_label)
        content_layout.addWidget(self.backend_input)

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
        self.password_input.setPlaceholderText("Enter your password") # Added placeholder
        content_layout.addWidget(self.password_label)
        content_layout.addWidget(self.password_input)

        # Remember Me Checkbox
        self.remember_checkbox = QCheckBox("Remember Me")
        self.remember_checkbox.setObjectName("remember_checkbox")  # Set object name for styling
        self.remember_checkbox.setChecked(False)  # Initially unchecked
        self.remember_checkbox.stateChanged.connect(self.on_remember_me_changed)
        content_layout.addWidget(self.remember_checkbox)
        content_layout.addSpacing(10) # Spacer before buttons

        # Login Button
        self.login_button = QPushButton("Login", self)
        self.login_button.setObjectName("login_button") # Set object name for styling
        self.login_button.clicked.connect(self.attempt_login)
        self.login_button.setDefault(True) # Allow Enter key to trigger login
        content_layout.addWidget(self.login_button)

        # Register Button
        self.register_button = QPushButton("Register", self)
        self.register_button.setObjectName("register_button") # Set object name
        self.register_button.clicked.connect(self.register_clicked)  # Connected to new handler
        content_layout.addWidget(self.register_button)
        
        # Guest Login Button removed as requested

        # Error Label (Initially Hidden)
        self.error_label = QLabel("", self)
        self.error_label.setObjectName("error_label")
        self.error_label.setAlignment(Qt.AlignCenter)
        # self.error_label.setStyleSheet("color: #FF6B6B;") # Style using QSS file
        content_layout.addWidget(self.error_label)
        self.error_label.hide()

        # --- Combine Layouts --- 
        main_layout = QVBoxLayout(self) # Overall layout for the window
        main_layout.setContentsMargins(0, 5, 0, 0) # Only top margin for top_layout
        main_layout.addLayout(top_layout) # Add theme button layout at the top
        main_layout.addLayout(content_layout) # Add main content below

        # Set focus initially
        self.username_input.setFocus()

    # --- Method to update theme button icon --- 
    def _update_theme_icon(self, theme_name):
        if theme_name == "dark":
            emoji = "☀️"  # Sun emoji for dark mode (switch to light)
            tooltip = "Switch to Light Mode"
        else:
            emoji = "🌙"  # Moon emoji for dark mode (switch to dark) 
            tooltip = "Switch to Dark Mode"
            
        # Set the text directly to the emoji
        self.theme_button.setText(emoji)
        self.theme_button.setIcon(QIcon())  # Clear any icon
        self.theme_button.setToolTip(tooltip)
        
        # The font size is already set in CSS, but we'll ensure it's set here as well
        # for systems that might override it
        font = self.theme_button.font()
        font.setPointSize(14)  # Larger font for emoji
        self.theme_button.setFont(font)

    def attempt_login(self):
        backend_url = self.backend_input.text().strip()
        username = self.username_input.text().strip()
        password = self.password_input.text()

        if not backend_url or not username:
            self.show_error("Backend URL and Username are required.")
            return

        # Clear previous error
        self.error_label.hide()
        self.error_label.setText("")

        self.login_attempt_signal.emit(backend_url, username, password)

    def show_error(self, message):
        # Display error in the label instead of message box
        self.error_label.setText(message)
        self.error_label.show()
        # Re-enable button
        self.login_button.setEnabled(True)
        self.login_button.setText("Login")

    def set_logging_in(self):
        # Disable button and show progress indication
        self.login_button.setEnabled(False)
        self.login_button.setText("Logging In...")
        self.error_label.hide()

    def on_remember_me_changed(self, state):
        # This method is called when the state of the "Remember Me" checkbox changes
        # You can implement the logic to save the checkbox state to a file or a database
        # For example, you can use a configuration file to store the state
        print(f"[UI LoginWindow] Remember Me checkbox toggled: {state}")
        # Here, we'll just print the state

    def register_clicked(self):
        # Display a dialog or navigate to the registration page
        # For now, just display a message that registration functionality is coming soon
        QMessageBox.information(self, "Registration", "Registration functionality is coming soon!")
        # In the future, this could emit a signal to open a registration form or dialog
        # self.register_signal.emit()

class InitialWindow(QWidget):
    """Window to choose between Host and Client mode."""
    start_host_signal = pyqtSignal()
    connect_client_signal = pyqtSignal(str, int) # Emits host IP (str) and port (int)

    def __init__(self, local_ip, default_port):
        super().__init__()
        self.local_ip = local_ip
        self.default_port = default_port # Store default port
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Remote Desktop Control')

        layout = QVBoxLayout()

        # --- Host Section ---
        host_group = QGroupBox("Start as Host")
        host_layout = QVBoxLayout()
        self.ip_label = QLabel(f"Your IP Address: {self.local_ip}:{self.default_port}")
        self.start_host_button = QPushButton('Start Hosting')
        self.start_host_button.clicked.connect(self.start_host)
        host_layout.addWidget(self.ip_label)
        host_layout.addWidget(self.start_host_button)
        host_group.setLayout(host_layout)

        # --- Client Section ---
        client_group = QGroupBox("Connect to Host")
        client_layout = QVBoxLayout()
        # IP Input
        ip_layout = QHBoxLayout() # Use horizontal layout for IP label and input
        self.ip_input_label = QLabel("Host IP:")
        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("e.g., 192.168.1.10")
        ip_layout.addWidget(self.ip_input_label)
        ip_layout.addWidget(self.ip_input)
        client_layout.addLayout(ip_layout) # Add the horizontal layout

        # Port Input
        port_layout = QHBoxLayout() # Use horizontal layout for Port label and input
        self.port_input_label = QLabel("Port:")
        self.port_input = QLineEdit()
        self.port_input.setPlaceholderText(f"Default: {self.default_port}") # Show default in placeholder
        # Optional: Set fixed width for port input
        self.port_input.setMaximumWidth(80)
        port_layout.addWidget(self.port_input_label)
        port_layout.addWidget(self.port_input)
        port_layout.addStretch() # Push port input to the left
        client_layout.addLayout(port_layout) # Add the horizontal layout

        self.connect_button = QPushButton('Connect')
        self.connect_button.clicked.connect(self.connect_client)
        client_layout.addWidget(self.connect_button)
        client_group.setLayout(client_layout)

        layout.addWidget(host_group)
        layout.addWidget(client_group)

        self.setLayout(layout)
        self.show()

    def start_host(self):
        self.start_host_signal.emit()
        self.close()

    def connect_client(self):
        host_ip = self.ip_input.text().strip()
        port_str = self.port_input.text().strip()
        port = self.default_port # Use default initially

        if not host_ip:
            QMessageBox.warning(self, "Input Error", "Please enter the Host IP address.")
            return

        if port_str: # If user entered a port
            try:
                port = int(port_str)
                if not (0 < port < 65536):
                    raise ValueError("Port must be between 1 and 65535")
            except ValueError as e:
                 QMessageBox.warning(self, "Input Error", f"Invalid Port Number: {e}")
                 return

        # Emit both IP and Port
        self.connect_client_signal.emit(host_ip, port)
        self.close()

class HostWindow(QWidget):
    """Window displayed on the host machine."""
    stop_host_signal = pyqtSignal()

    def __init__(self, ip_address, port):
        super().__init__()
        self.ip_address = ip_address
        self.port = port
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Hosting - Remote Desktop')
        layout = QVBoxLayout()
        self.status_label = QLabel(f"Hosting on {self.ip_address}:{self.port}\nWaiting for connection...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.stop_button = QPushButton("Stop Hosting")
        self.stop_button.clicked.connect(self.stop_hosting)

        layout.addWidget(self.status_label)
        layout.addWidget(self.stop_button)
        self.setLayout(layout)
        self.show()

    def update_status(self, status):
        self.status_label.setText(status)

    def stop_hosting(self):
        self.stop_host_signal.emit()
        self.close()

    def closeEvent(self, event):
        # Ensure the signal is emitted even if the window is closed manually
        self.stop_host_signal.emit()
        event.accept()


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
        self.remote_screen_size = QSize(1, 1) # Placeholder
        self._view_only = False
        self.setCursor(Qt.BlankCursor) # Hide local cursor
        self.remote_cursor_pos = None
        self._fit_to_window = False # Add state for fit-to-window

    def set_view_only(self, view_only):
        self._view_only = view_only
        if view_only:
             self.setCursor(Qt.ArrowCursor) # Show local cursor if view only
        else:
             self.setCursor(Qt.BlankCursor)

    def update_screen(self, image_data):
        """Loads image data into the pixmap and triggers a repaint."""
        try:
            # Allow Qt to auto-detect format (PNG or JPEG)
            qimg = QImage.fromData(image_data) # Removed format='JPEG'
            if not qimg.isNull():
                self.pixmap = QPixmap.fromImage(qimg)
                # Store the size of the remote screen for scaling
                self.remote_screen_size = self.pixmap.size()
                self.updateGeometry()
                self.update() # Schedule a repaint
            else:
                 print("Failed to load image from data")
        except Exception as e:
            print(f"Error updating screen: {e}")

    def update_remote_cursor(self, x, y):
        """Stores the remote cursor position to draw it."""
        self.remote_cursor_pos = (x, y)
        self.update() # Redraw to show cursor

    def set_fit_to_window(self, fit):
        """Sets the fit-to-window mode and triggers repaint."""
        print(f"[UI ScreenDisplayWidget] Setting fit_to_window: {fit}") # LOG
        if self._fit_to_window != fit:
            self._fit_to_window = fit
            self.updateGeometry() # May need size adjustment
            self.update() # Request repaint

    def paintEvent(self, event):
        painter = QPainter(self)
        if not self.pixmap.isNull():
            target_rect = self.rect()
            pixmap_size = self.pixmap.size()
            # LOG: Log paint event mode
            # print(f"[UI ScreenDisplayWidget] paintEvent - Fit: {self._fit_to_window}, Widget Rect: {target_rect}, Pixmap Size: {pixmap_size}") 

            scaled_pixmap = self.pixmap # Assign default
            x, y = 0, 0 # Default offsets

            if self._fit_to_window:
                # Scale pixmap to fit widget while preserving aspect ratio
                scaled_pixmap = self.pixmap.scaled(target_rect.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                x = (target_rect.width() - scaled_pixmap.width()) / 2
                y = (target_rect.height() - scaled_pixmap.height()) / 2
                painter.drawPixmap(int(x), int(y), scaled_pixmap)
                # Ensure widget can shrink if needed when fitting
                # self.setMinimumSize(1, 1) # Or something small?
            else:
                painter.drawPixmap(int(x), int(y), scaled_pixmap) # Draw at 0,0
                if self.minimumSize() != pixmap_size:
                    self.setMinimumSize(pixmap_size)

            # Draw remote cursor
            if self.remote_cursor_pos and not self._view_only:
                cursor_display_x, cursor_display_y = 0, 0
                if self._fit_to_window and pixmap_size.width() > 0 and pixmap_size.height() > 0 and scaled_pixmap.width() > 0 and scaled_pixmap.height() > 0:
                    scale_ratio_x = scaled_pixmap.width() / pixmap_size.width()
                    scale_ratio_y = scaled_pixmap.height() / pixmap_size.height()
                    cursor_display_x = int(self.remote_cursor_pos[0] * scale_ratio_x + x)
                    cursor_display_y = int(self.remote_cursor_pos[1] * scale_ratio_y + y)
                else:
                    # 1:1 calculation or if scaling failed
                    cursor_display_x = int(self.remote_cursor_pos[0])
                    cursor_display_y = int(self.remote_cursor_pos[1])

                # Clamp cursor display coords to widget bounds for safety
                cursor_display_x = max(0, min(cursor_display_x, target_rect.width() -1))
                cursor_display_y = max(0, min(cursor_display_y, target_rect.height() -1))
                
                # Draw cursor
                painter.setPen(QPen(Qt.red, 2))
                painter.drawLine(cursor_display_x - 5, cursor_display_y, cursor_display_x + 5, cursor_display_y)
                painter.drawLine(cursor_display_x, cursor_display_y - 5, cursor_display_x, cursor_display_y + 5)
        else:
            painter.fillRect(self.rect(), Qt.black)
            painter.setPen(Qt.white)
            painter.drawText(self.rect(), Qt.AlignCenter, "Waiting for screen data...")
            # Reset minimum size when no pixmap
            if self.minimumSize() != QSize(800, 600):
                self.setMinimumSize(800, 600) 
        painter.end()

    def get_scaled_coords(self, widget_pos):
         """ Converts widget coordinates to original remote screen coordinates. """
         if self.pixmap.isNull() or self.pixmap.width() == 0 or self.pixmap.height() == 0:
              # print("[get_scaled_coords] No pixmap or zero size.")
              return 0, 0
         
         pixmap_size = self.pixmap.size()
         widget_rect = self.rect()
         widget_x = widget_pos.x()
         widget_y = widget_pos.y()
         
         original_x = 0
         original_y = 0

         if self._fit_to_window:
              # Calculate the size and position of the displayed pixmap (keeping aspect ratio)
              scaled_pixmap = self.pixmap.scaled(widget_rect.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
              scaled_width = scaled_pixmap.width()
              scaled_height = scaled_pixmap.height()
              offset_x = (widget_rect.width() - scaled_width) / 2
              offset_y = (widget_rect.height() - scaled_height) / 2

              # Check if click is within the bounds of the *displayed* pixmap
              if scaled_width > 0 and scaled_height > 0 and \
                 offset_x <= widget_x < offset_x + scaled_width and \
                 offset_y <= widget_y < offset_y + scaled_height:
                  
                  # Calculate position relative to the top-left of the scaled pixmap
                  x_in_scaled = widget_x - offset_x
                  y_in_scaled = widget_y - offset_y
                  
                  # Convert back to original coordinates using the scaling ratio
                  original_x = (x_in_scaled / scaled_width) * pixmap_size.width()
                  original_y = (y_in_scaled / scaled_height) * pixmap_size.height()
              else:
                   # Click was outside the image area (in padding) - treat as edge case
                   print("[get_scaled_coords Fit] Click outside image area.")
                   # Return coords clamped to the original edge? Or (0,0)? Clamp for now.
                   # Determine which edge is closest based on relative position
                   rel_x = widget_x - offset_x
                   rel_y = widget_y - offset_y
                   if rel_x < 0: original_x = 0
                   elif rel_x >= scaled_width: original_x = pixmap_size.width()
                   else: original_x = (rel_x / scaled_width) * pixmap_size.width() # Should not happen based on outer check

                   if rel_y < 0: original_y = 0
                   elif rel_y >= scaled_height: original_y = pixmap_size.height()
                   else: original_y = (rel_y / scaled_height) * pixmap_size.height()
         else:
              # 1:1 mode - Coordinates are relative to the widget origin
              # Ensure click is within the pixmap bounds displayed at (0,0)
              original_x = widget_x
              original_y = widget_y

         # Final clamp to ensure coords are within the original image dimensions
         final_x = max(0, min(int(original_x), pixmap_size.width() - 1))
         final_y = max(0, min(int(original_y), pixmap_size.height() - 1))
         
         # print(f"[get_scaled_coords] Fit:{self._fit_to_window}, Widget:{widget_x},{widget_y} -> Original:{final_x},{final_y}")
         return final_x, final_y

    # --- Input Event Handlers ---
    def mouseMoveEvent(self, event):
        if self._view_only:
            return
        x, y = self.get_scaled_coords(event.pos())
        # Also update the locally drawn remote cursor immediately
        self.remote_cursor_pos = (x,y)
        self.update()
        # Send move event
        self.mouse_event_signal.emit({'type': 'move', 'x': x, 'y': y})
        event.accept()

    def mousePressEvent(self, event):
        if self._view_only:
            return
        x, y = self.get_scaled_coords(event.pos())
        button = 'left' if event.button() == Qt.LeftButton else \
                 'right' if event.button() == Qt.RightButton else \
                 'middle' if event.button() == Qt.MiddleButton else None
        if button:
            self.mouse_event_signal.emit({'type': 'press', 'x': x, 'y': y, 'button': button})
        event.accept()

    def mouseReleaseEvent(self, event):
        if self._view_only:
            return
        x, y = self.get_scaled_coords(event.pos())
        button = 'left' if event.button() == Qt.LeftButton else \
                 'right' if event.button() == Qt.RightButton else \
                 'middle' if event.button() == Qt.MiddleButton else None
        if button:
            self.mouse_event_signal.emit({'type': 'release', 'x': x, 'y': y, 'button': button})
        event.accept()

    # Note: Qt doesn't directly map to pyautogui click, we send press/release
    # def mouseDoubleClickEvent(self, event):
    #     # PyAutoGUI handles double click with click(clicks=2)
    #     # We might need to detect double clicks manually based on timing
    #     # or just rely on the host interpreting two rapid clicks.
    #     pass

    def wheelEvent(self, event):
        if self._view_only:
            return
        x, y = self.get_scaled_coords(event.position().toPoint())
        delta = event.angleDelta()
        # Send scroll event (vertical is usually delta.y())
        self.mouse_event_signal.emit({
            'type': 'scroll',
            'x': x,
            'y': y,
            'delta_x': delta.x(),
            'delta_y': delta.y()
        })
        event.accept()


    def keyPressEvent(self, event):
        if self._view_only:
            return
        key = self.get_key_string(event)
        if key:
            self.key_event_signal.emit({'type': 'press', 'key': key})
        event.accept()

    def keyReleaseEvent(self, event):
        if self._view_only:
            return
        # Ignore auto-repeat release events
        if event.isAutoRepeat():
            event.ignore()
            return
        key = self.get_key_string(event)
        if key:
            self.key_event_signal.emit({'type': 'release', 'key': key})
        event.accept()

    def get_key_string(self, event):
        """ Converts Qt key event to a string representation for pyautogui."""
        key = event.key()
        text = event.text()

        # Handle modifiers first
        if key == Qt.Key_Control:
            return '<ctrl>'
        if key == Qt.Key_Shift:
            return '<shift>'
        if key == Qt.Key_Alt:
            return '<alt>'
        if key == Qt.Key_Meta: # Command key on Mac, Windows key on Win
            return '<cmd>' # Or map to 'win' if needed

        # Handle special keys (non-printable)
        special_keys = {
            Qt.Key_Return: '<enter>',
            Qt.Key_Enter: '<enter>', # Numpad Enter
            Qt.Key_Escape: '<esc>',
            Qt.Key_Tab: '<tab>',
            Qt.Key_Backspace: '<backspace>',
            Qt.Key_Delete: '<delete>',
            Qt.Key_Up: '<up>',
            Qt.Key_Down: '<down>',
            Qt.Key_Left: '<left>',
            Qt.Key_Right: '<right>',
            Qt.Key_Home: '<home>',
            Qt.Key_End: '<end>',
            Qt.Key_PageUp: '<pageup>',
            Qt.Key_PageDown: '<pagedown>',
            Qt.Key_F1: '<f1>', Qt.Key_F2: '<f2>', Qt.Key_F3: '<f3>',
            Qt.Key_F4: '<f4>', Qt.Key_F5: '<f5>', Qt.Key_F6: '<f6>',
            Qt.Key_F7: '<f7>', Qt.Key_F8: '<f8>', Qt.Key_F9: '<f9>',
            Qt.Key_F10: '<f10>', Qt.Key_F11: '<f11>', Qt.Key_F12: '<f12>',
            # Add more function keys or special keys as needed
        }
        if key in special_keys:
            return special_keys[key]

        # Handle printable characters
        if text and text.isprintable():
            return text

        # Fallback for other keys (might need more mapping)
        print(f"Unhandled key: {key}, text: {text}")
        return None


# --- New Main Application Window ---
class MainWindow(QMainWindow): # Inherit from QMainWindow for menus, status bar etc.
    """Main application window shown after login."""
    request_view_signal = pyqtSignal(str) # Renamed from connect_to_peer_signal
    disconnect_signal = pyqtSignal()
    send_chat_message_signal = pyqtSignal(str)
    logout_signal = pyqtSignal() # Signal for logout request
    start_sharing_signal = pyqtSignal() # Signal to request start sharing
    stop_sharing_signal = pyqtSignal()  # Signal to request stop sharing
    # Add signal for mouse permission
    mouse_permission_signal = pyqtSignal(bool) # Emits boolean for allow/deny
    # Add signals for stream settings
    quality_changed_signal = pyqtSignal(int)
    scale_changed_signal = pyqtSignal(int) # Emit percentage (25-100)
    fps_changed_signal = pyqtSignal(int)
    monitor_changed_signal = pyqtSignal(int) # Emit monitor index (1-based)
    # Add theme toggle signal
    toggle_theme_signal = pyqtSignal() # Signal to toggle theme

    # Default stream settings
    DEFAULT_QUALITY = 75
    DEFAULT_SCALE = 100 # Percentage
    DEFAULT_FPS = 15
    DEFAULT_MONITOR_INDEX = 1 # Default to primary monitor
    # Preset FPS values for ComboBox
    FPS_OPTIONS = [5, 10, 15, 20, 25, 30]

    def __init__(self, username="Unknown User", current_theme="dark"): # Pass username and theme
        super().__init__()
        self.username = username
        self.current_theme = current_theme  # Store current theme
        # Store internal state for settings
        self._current_quality = self.DEFAULT_QUALITY
        self._current_scale = self.DEFAULT_SCALE
        self._current_fps = self.DEFAULT_FPS
        self._current_monitor_index = self.DEFAULT_MONITOR_INDEX
        # Store the last base status message for FPS updates
        self._last_base_status = "Ready"
        self._last_displayed_fps = 0.0

        print("[DEBUG] Creating MainWindow with toolbar buttons only on the right side")
        
        # Setup UI
        self.setWindowTitle(f"SCU Remote Desktop - {self.username}")
        self.setMinimumSize(800, 600)
        
        # Create toolbar for theme toggle and logout (RIGHT SIDE ONLY)
        toolbar = self.addToolBar("Theme")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        
        # Add spacer to push buttons to the right
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(spacer)
        
        # Theme Toggle Button (right side)
        self.theme_button = QPushButton()
        self.theme_button.setObjectName("theme_button")
        self.theme_button.setToolTip("Toggle Light/Dark Mode")
        self.theme_button.setFlat(True)
        self.theme_button.setCursor(Qt.PointingHandCursor)
        self.theme_button.setMinimumSize(35, 35)
        
        font = self.theme_button.font()
        font.setPointSize(14)
        self.theme_button.setFont(font)
        
        # Initialize with the current theme icon
        self._update_theme_icon(self.current_theme)
        self.theme_button.clicked.connect(self.toggle_theme_signal.emit)
        toolbar.addWidget(self.theme_button)
        
        # Logout Button (right side)
        self.toolbar_logout_button = QPushButton()
        self.toolbar_logout_button.setObjectName("toolbar_logout_button")
        self.toolbar_logout_button.setToolTip("Logout")
        self.toolbar_logout_button.setFlat(True)
        self.toolbar_logout_button.setCursor(Qt.PointingHandCursor)
        self.toolbar_logout_button.setMinimumSize(35, 35)
        
        # Set icon from logout.png
        self.toolbar_logout_button.setIcon(QIcon("logout.png"))
        self.toolbar_logout_button.setIconSize(QSize(24, 24))
        self.toolbar_logout_button.clicked.connect(self.logout_signal.emit)
        toolbar.addWidget(self.toolbar_logout_button)
        
        # Create status bar
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.update_status("Initializing...")
        
        # Setup main UI components
        self.initUI()
        self.set_disconnected_state() # Initial state

    def initUI(self):
        # Main central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # --- Left Side: Screen Display --- 
        screen_layout = QVBoxLayout()

        # --- Screen Display Widget --- 
        self.scroll_area = QScrollArea()
        self.scroll_area.setBackgroundRole(QPalette.Dark) # Match dark theme potentially
        self.scroll_area.setWidgetResizable(True)
        
        self.screen_display_widget = ScreenDisplayWidget(self) # Parent needed?
        self.screen_display_widget.setObjectName("ScreenDisplayWidget") # Set object name
        self.scroll_area.setWidget(self.screen_display_widget)

        screen_layout.addWidget(self.scroll_area)

        # --- Fit to Window Checkbox --- 
        self.fit_checkbox = QCheckBox("Fit to Window")
        self.fit_checkbox.stateChanged.connect(self._toggle_fit_to_window)
        screen_layout.addWidget(self.fit_checkbox, alignment=Qt.AlignRight)

        # --- Right Side: Controls --- 
        controls_layout = QVBoxLayout()
        controls_layout.setSpacing(15)

        # --- Connection GroupBox --- 
        connection_groupbox = QGroupBox("Connection")
        connection_layout = QVBoxLayout()

        peer_layout = QHBoxLayout()
        peer_layout.addWidget(QLabel("Peer UID:"))
        self.peer_input = QLineEdit()
        self.peer_input.setPlaceholderText("Enter Peer's Username")
        peer_layout.addWidget(self.peer_input)
        
        self.request_view_button = QPushButton("Request View") # Renamed from Connect
        self.request_view_button.setObjectName("request_view_button")
        self.request_view_button.clicked.connect(self.on_request_view_clicked)
        peer_layout.addWidget(self.request_view_button)

        connection_layout.addLayout(peer_layout)

        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.setObjectName("disconnect_button")
        self.disconnect_button.clicked.connect(self.disconnect_signal.emit) # Directly emit
        self.disconnect_button.setEnabled(False) # Initially disabled
        connection_layout.addWidget(self.disconnect_button)
        
        connection_groupbox.setLayout(connection_layout)
        controls_layout.addWidget(connection_groupbox)

        # --- Sharer Control GroupBox --- 
        # Make the groupbox itself checkable
        self.sharer_groupbox = QGroupBox("Share Your Screen")
        self.sharer_groupbox.setCheckable(True)
        self.sharer_groupbox.setChecked(False)
        self.sharer_groupbox.toggled.connect(self.on_sharer_toggled) # Handle check changes
        sharer_layout = QVBoxLayout()
        self.sharer_groupbox.setLayout(sharer_layout)
        self.sharer_groupbox.setEnabled(False) # Disabled until connected

        # Start/Stop Buttons
        sharing_buttons_layout = QHBoxLayout()
        self.start_sharing_button = QPushButton("Start Sharing")
        self.start_sharing_button.setObjectName("start_sharing_button")
        self.start_sharing_button.clicked.connect(self.on_start_sharing_clicked)
        self.start_sharing_button.setEnabled(False)
        sharing_buttons_layout.addWidget(self.start_sharing_button)

        self.stop_sharing_button = QPushButton("Stop Sharing")
        self.stop_sharing_button.setObjectName("stop_sharing_button")
        self.stop_sharing_button.clicked.connect(self.on_stop_sharing_clicked)
        self.stop_sharing_button.setEnabled(False)
        sharing_buttons_layout.addWidget(self.stop_sharing_button)
        sharer_layout.addLayout(sharing_buttons_layout)
        
        # --- Settings inside Sharer GroupBox (Initially Hidden/Disabled) --- 
        self.settings_groupbox = QGroupBox("Stream Settings")
        self.settings_groupbox.setVisible(False) # Start hidden
        self.settings_groupbox.setEnabled(False) # Start disabled
        settings_layout = QFormLayout(self.settings_groupbox)
        settings_layout.setRowWrapPolicy(QFormLayout.DontWrapRows)
        settings_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        settings_layout.setLabelAlignment(Qt.AlignLeft)
        settings_layout.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)

        # Monitor Selection
        self.monitor_combobox = QComboBox()
        self._populate_monitor_combobox() # Populate with available monitors
        self.monitor_combobox.currentIndexChanged.connect(self._emit_monitor_index)
        settings_layout.addRow("Monitor:", self.monitor_combobox)

        # Quality Slider
        quality_layout = QHBoxLayout()
        self.quality_slider = QSlider(Qt.Horizontal)
        self.quality_slider.setRange(10, 100)
        self.quality_slider.setValue(self.DEFAULT_QUALITY)
        self.quality_slider.setTickInterval(10)
        self.quality_slider.setTickPosition(QSlider.TicksBelow)
        self.quality_label = QLabel(f"{self.DEFAULT_QUALITY}%")
        self.quality_slider.valueChanged.connect(self._update_quality_label_and_emit)
        quality_layout.addWidget(self.quality_slider)
        quality_layout.addWidget(self.quality_label)
        settings_layout.addRow("Quality:", quality_layout)

        # Scale Slider
        scale_layout = QHBoxLayout()
        self.scale_slider = QSlider(Qt.Horizontal)
        self.scale_slider.setRange(25, 100)
        self.scale_slider.setValue(self.DEFAULT_SCALE)
        self.scale_slider.setTickInterval(25)
        self.scale_slider.setTickPosition(QSlider.TicksBelow)
        self.scale_label = QLabel(f"{self.DEFAULT_SCALE}%")
        self.scale_slider.valueChanged.connect(self._update_scale_label_and_emit)
        scale_layout.addWidget(self.scale_slider)
        scale_layout.addWidget(self.scale_label)
        settings_layout.addRow("Scale:", scale_layout)

        # FPS ComboBox
        self.fps_combobox = QComboBox()
        for fps_option in self.FPS_OPTIONS:
            self.fps_combobox.addItem(str(fps_option), userData=fps_option)
        # Find and set the default FPS index
        default_fps_index = self.fps_combobox.findData(self.DEFAULT_FPS)
        if default_fps_index != -1:
             self.fps_combobox.setCurrentIndex(default_fps_index)
        self.fps_combobox.currentIndexChanged.connect(self._emit_fps_value)
        settings_layout.addRow("Max FPS:", self.fps_combobox)

        sharer_layout.addWidget(self.settings_groupbox)
        controls_layout.addWidget(self.sharer_groupbox)

        # --- Mouse Control Checkbox --- 
        self.mouse_permission_checkbox = QCheckBox("Allow Peer Mouse Control")
        self.mouse_permission_checkbox.setObjectName("mouse_permission_checkbox")
        self.mouse_permission_checkbox.toggled.connect(self._toggle_mouse_permission)
        self.mouse_permission_checkbox.setEnabled(False) # Disabled until connected
        controls_layout.addWidget(self.mouse_permission_checkbox)

        # --- Chat Area (Placeholder) --- 
        chat_groupbox = QGroupBox("Chat")
        chat_layout = QVBoxLayout()
        self.chat_display = QPlainTextEdit()
        self.chat_display.setReadOnly(True)
        chat_layout.addWidget(self.chat_display)
        
        chat_input_layout = QHBoxLayout()
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Enter chat message...")
        self.chat_send_button = QPushButton("Send")
        self.chat_send_button.clicked.connect(self.on_chat_send)
        self.chat_input.returnPressed.connect(self.on_chat_send) # Send on Enter
        chat_input_layout.addWidget(self.chat_input)
        chat_input_layout.addWidget(self.chat_send_button)
        chat_layout.addLayout(chat_input_layout)
        
        chat_groupbox.setLayout(chat_layout)
        controls_layout.addWidget(chat_groupbox) # Re-enabled chat section
        controls_layout.addStretch() # Push controls to the top

        # Add layouts to main layout
        main_layout.addLayout(screen_layout, 75) # Screen takes 75% width
        main_layout.addLayout(controls_layout, 25) # Controls take 25% width

    # --- Helper methods for UI --- 
    def _populate_monitor_combobox(self):
        try:
            monitors = screeninfo.get_monitors()
            self.monitor_combobox.clear()
            if not monitors:
                self.monitor_combobox.addItem("No monitors found", userData=-1)
                self.monitor_combobox.setEnabled(False)
                return

            for i, monitor in enumerate(monitors):
                monitor_label = f"Monitor {i+1}: {monitor.width}x{monitor.height}"
                if monitor.is_primary:
                    monitor_label += " (Primary)"
                self.monitor_combobox.addItem(monitor_label, userData=i + 1) # Use 1-based index for user data
                
            # Set default selection
            if len(monitors) >= self.DEFAULT_MONITOR_INDEX:
                 self.monitor_combobox.setCurrentIndex(self.DEFAULT_MONITOR_INDEX - 1) # 0-based index for setCurrentIndex
            elif len(monitors) > 0:
                 self.monitor_combobox.setCurrentIndex(0) # Fallback to first monitor

        except screeninfo.ScreenInfoError as e:
            print(f"Could not get monitor info: {e}")
            self.monitor_combobox.addItem("Error getting monitors", userData=-1)
            self.monitor_combobox.setEnabled(False)

    def _emit_monitor_index(self, index):
        monitor_index_data = self.monitor_combobox.itemData(index)
        if monitor_index_data and monitor_index_data != -1:
             print(f"[UI MainWindow] Monitor selection changed: Index {index}, UserData (1-based): {monitor_index_data}") # LOG
             self.monitor_changed_signal.emit(monitor_index_data) # Emit 1-based index

    def _update_quality_label_and_emit(self, value):
        self.quality_label.setText(f"{value}%")
        self.quality_changed_signal.emit(value)

    def _update_scale_label_and_emit(self, value):
        self.scale_label.setText(f"{value}%")
        self.scale_changed_signal.emit(value)

    def _emit_fps_value(self, index):
        fps_data = self.fps_combobox.itemData(index)
        if fps_data:
            self.fps_changed_signal.emit(fps_data)

    # --- Event Handlers --- 
    def on_sharer_toggled(self, checked):
        # This is triggered by USER clicking the checkbox OR programmatically
        # We only want to trigger START/STOP if the USER clicked it.
        # The actual start/stop is handled by start/stop button clicks now.
        # This toggle can enable/disable the inner settings box.
        print(f"[UI MainWindow] Sharer GroupBox toggled: {checked}") # LOG
        # self.settings_groupbox.setVisible(checked)
        # self.settings_groupbox.setEnabled(checked)
        # If user UNCHECKS the box, signal stop sharing
        # if not checked and self.stop_sharing_button.isEnabled():
             # self.stop_sharing_signal.emit()
        # If user CHECKS the box, signal start sharing
        # elif checked and self.start_sharing_button.isEnabled():
             # self.start_sharing_signal.emit()
        pass # Let buttons handle start/stop

    def on_request_view_clicked(self): # Renamed from on_connect_clicked
        peer_uid = self.peer_input.text().strip()
        if peer_uid:
            self.request_view_signal.emit(peer_uid) # Emit renamed signal
            # Disable button temporarily while request is in progress?
            # self.request_view_button.setEnabled(False)
        else:
            QMessageBox.warning(self, "Input Required", "Please enter a Peer UID to connect to.")

    def on_chat_send(self):
        message = self.chat_input.text().strip()
        if message:
            # self.append_chat_message(f"Me: {message}") # Show own message immediately
            self.send_chat_message_signal.emit(message)
            self.chat_input.clear()

    # --- Methods called by AppController --- 
    def append_chat_message(self, message):
        self.chat_display.appendPlainText(message)

    def update_status(self, status, is_base_message=True):
        """Updates the status bar message, preserving FPS if available."""
        if is_base_message:
            self._last_base_status = status # Store the new base status
            
        current_status = self._last_base_status
        if self._last_displayed_fps > 0:
            current_status += f" (Recv FPS: {self._last_displayed_fps:.1f})"

        self.statusBar.showMessage(current_status)

    # --- New Slot for FPS updates ---
    def update_fps_display(self, fps):
        """Updates the FPS part of the status bar message."""
        self._last_displayed_fps = fps
        # Update the full status bar text using the last base message
        self.update_status(self._last_base_status, is_base_message=False)

    # --- State Management Methods (called by AppController) ---

    def set_connected_state(self, connected_to_uid):
        """Update UI state when connected to a peer."""
        if not connected_to_uid:
            # No UID means effectively disconnected
            self.set_disconnected_state("Not connected to any peer.")
            return
            
        # Update button states
        self.request_view_button.setEnabled(False)
        self.peer_input.setEnabled(False)
        self.disconnect_button.setEnabled(True)
        
        # Enable appropriate controls
        self.sharer_groupbox.setEnabled(True)
        self.sharer_groupbox.setChecked(False)
        self.start_sharing_button.setEnabled(True)
        self.stop_sharing_button.setEnabled(False)
        self.settings_groupbox.setVisible(False)
        self.settings_groupbox.setEnabled(False)
        
        # Enable mouse permission control
        self.mouse_permission_checkbox.setEnabled(True)
        
        # Update status
        self._last_base_status = f"Connected to {connected_to_uid}. Ready."
        self.update_status(self._last_base_status)
        self._last_displayed_fps = 0

    def set_disconnected_state(self, message="Ready"):
        """Reset UI state when disconnected from peer."""
        # Reset connection controls
        self.request_view_button.setEnabled(True)
        self.peer_input.setEnabled(True)
        self.disconnect_button.setEnabled(False)
        
        # Reset sharer controls
        self.sharer_groupbox.setEnabled(False)
        self.sharer_groupbox.setChecked(False)  # Uncheck
        self.start_sharing_button.setEnabled(False)
        self.stop_sharing_button.setEnabled(False)
        self.settings_groupbox.setVisible(False)
        self.settings_groupbox.setEnabled(False)
        
        # Reset mouse permission control
        self.mouse_permission_checkbox.setEnabled(False)
        self.mouse_permission_checkbox.setChecked(False)  # Uncheck
        
        # Set screen display to view-only
        if hasattr(self, 'screen_display_widget') and self.screen_display_widget:
            self.screen_display_widget.set_view_only(True)
            print("[DEBUG UI] Set screen display to view-only mode on disconnect")
        
        # Update status bar
        self._last_base_status = message # Remember status message for possible FPS overlay
        # Use the provided message, or default to "Disconnected"
        status_msg = message if message != "Ready" else "Disconnected. Ready."
        self.update_status(status_msg)
        self.screen_display_widget.update_screen(b'')
        self._last_displayed_fps = 0


    def set_sharing_state(self, is_sharing):
        """Updates UI elements based on active sharing state."""
        # Update check state of the main group box
        self.sharer_groupbox.setChecked(is_sharing)

        # Enable/Disable Start/Stop buttons
        self.start_sharing_button.setEnabled(not is_sharing)
        self.stop_sharing_button.setEnabled(is_sharing)

        # Show/Hide and Enable/Disable the settings group box
        self.settings_groupbox.setVisible(is_sharing)
        self.settings_groupbox.setEnabled(is_sharing)

        # Update status bar message
        if is_sharing:
             monitor_text = self.monitor_combobox.currentText()
             self.update_status(f"Sharing {monitor_text}...")
        else:
             # Revert status
             if self.disconnect_button.isEnabled():
                  peer_uid = self.peer_input.text().strip()
                  status_msg = f"Connected to {peer_uid}. Ready."
                  if peer_uid == "": status_msg = "Connected. Ready."
                  self.update_status(status_msg)
             else:
                  self.update_status("WebSocket Connected. Ready.")
        self.update_fps_display(0)


    def update_remote_screen(self, image_data):
        """Pass image data to the display widget."""
        self.screen_display_widget.update_screen(image_data)

    def update_remote_cursor(self, x, y):
        """Pass cursor data to the display widget."""
        self.screen_display_widget.update_remote_cursor(x, y)


    # --- Button Click Handlers ---
    # These now primarily emit signals. AppController handles the logic & state updates.

    def on_start_sharing_clicked(self):
        # Emit signal regardless of checkbox state; controller verifies if allowed
        self.start_sharing_signal.emit()
        # Controller will call set_sharing_state(True) upon success


    def on_stop_sharing_clicked(self):
        # Emit signal regardless of checkbox state; controller verifies if allowed
        self.stop_sharing_signal.emit()
        # Controller will call set_sharing_state(False) upon success

    def closeEvent(self, event):
        """Handle window close event."""
        self.logout_signal.emit() # Signal AppController to handle logout/cleanup
        event.accept() # Close the window

    # --- Slot for Fit Checkbox --- 
    def _toggle_fit_to_window(self, state):
        fit_enabled = (state == Qt.Checked)
        print(f"[UI MainWindow] Fit to window toggled: {fit_enabled}") # LOG
        self.screen_display_widget.set_fit_to_window(fit_enabled)
        self.scroll_area.setWidgetResizable(fit_enabled) # Important for scrollarea behavior
        if not fit_enabled:
            self.screen_display_widget.adjustSize() # Ensure widget resizes for scrollbars
            print("[UI MainWindow] Disabled fit, adjusted widget size.") # LOG
        else:
             # When fitting, ensure widget fills scroll area
             self.screen_display_widget.setMinimumSize(1, 1) 
             self.screen_display_widget.updateGeometry() # Trigger relayout

    def _toggle_mouse_permission(self, state):
        permission_enabled = (state == Qt.Checked)
        print(f"[UI MainWindow] Mouse permission toggled: {permission_enabled}") # LOG
        self.mouse_permission_signal.emit(permission_enabled)

    # --- Method to update theme button icon --- 
    def _update_theme_icon(self, theme_name):
        if theme_name == "dark":
            emoji = "☀️"  # Sun emoji for dark mode (switch to light)
            tooltip = "Switch to Light Mode"
        else:
            emoji = "🌙"  # Moon emoji for dark mode (switch to dark) 
            tooltip = "Switch to Dark Mode"
            
        # Set the text directly to the emoji
        self.theme_button.setText(emoji)
        self.theme_button.setIcon(QIcon())  # Clear any icon
        self.theme_button.setToolTip(tooltip)
        
        # The font size is already set in CSS, but we'll ensure it's set here as well
        # for systems that might override it
        font = self.theme_button.font()
        font.setPointSize(14)  # Larger font for emoji
        self.theme_button.setFont(font)

