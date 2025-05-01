import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QLineEdit, QGroupBox, QRadioButton, QDialog, QMessageBox,
    QScrollArea, QFormLayout, QMainWindow, QAction, QStatusBar, QTextEdit
)
from PyQt5.QtGui import QPixmap, QImage, QPainter, QPen, QCursor, QFont
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize

class LoginWindow(QWidget):
    """Window for user login."""
    # Signal emits backend_url, username, password
    login_attempt_signal = pyqtSignal(str, str, str)

    def __init__(self, default_backend_url="http://127.0.0.1:8000"): # Default to localhost backend
        super().__init__()
        self.default_backend_url = default_backend_url
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Login - Remote Desktop')
        layout = QVBoxLayout()
        layout.setSpacing(15) # Add some spacing

        title_label = QLabel("Remote Desktop Login")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)

        backend_group = QGroupBox("Backend Server")
        backend_layout = QHBoxLayout()
        self.backend_label = QLabel("URL:")
        self.backend_input = QLineEdit(self.default_backend_url)
        self.backend_input.setPlaceholderText("Enter Backend API URL")
        backend_layout.addWidget(self.backend_label)
        backend_layout.addWidget(self.backend_input)
        backend_group.setLayout(backend_layout)

        credentials_group = QGroupBox("Credentials")
        credentials_layout = QFormLayout() # Use QFormLayout for labels and inputs
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Enter your username")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Enter your password")
        self.password_input.setEchoMode(QLineEdit.Password) # Mask password
        credentials_layout.addRow("Username:", self.username_input)
        credentials_layout.addRow("Password:", self.password_input)
        credentials_group.setLayout(credentials_layout)

        self.login_button = QPushButton('Login')
        self.login_button.clicked.connect(self.attempt_login)
        # Allow login by pressing Enter in password field
        self.password_input.returnPressed.connect(self.attempt_login)

        self.status_label = QLabel("") # For showing login errors
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: red;")

        layout.addWidget(title_label)
        layout.addWidget(backend_group)
        layout.addWidget(credentials_group)
        layout.addWidget(self.login_button)
        layout.addWidget(self.status_label)
        layout.addStretch()

        self.setLayout(layout)
        self.resize(400, 300) # Adjust size as needed
        self.show()

    def attempt_login(self):
        backend_url = self.backend_input.text().strip()
        username = self.username_input.text().strip()
        password = self.password_input.text()

        if not backend_url or not username or not password:
            self.status_label.setText("Please fill in all fields.")
            return

        # Clear status and emit signal
        self.status_label.setText("")
        self.login_attempt_signal.emit(backend_url, username, password)

    def show_error(self, message):
        """Displays an error message on the login window."""
        self.status_label.setText(message)
        # Re-enable button if needed (depends on main controller logic)
        self.login_button.setEnabled(True)

    def set_logging_in(self):
         """Disables input fields and button, shows 'Logging in...' status."""
         self.backend_input.setEnabled(False)
         self.username_input.setEnabled(False)
         self.password_input.setEnabled(False)
         self.login_button.setEnabled(False)
         self.status_label.setStyleSheet("color: blue;")
         self.status_label.setText("Logging in...")

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

    def set_view_only(self, view_only):
        self._view_only = view_only
        if view_only:
             self.setCursor(Qt.ArrowCursor) # Show local cursor if view only
        else:
             self.setCursor(Qt.BlankCursor)

    def update_screen(self, image_data):
        """Loads image data into the pixmap and triggers a repaint."""
        try:
            qimg = QImage.fromData(image_data, 'JPEG')
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

    def paintEvent(self, event):
        """Draws the received screen image."""
        painter = QPainter(self)
        if not self.pixmap.isNull():
            # Draw the remote screen scaled to the widget size
            painter.drawPixmap(self.rect(), self.pixmap, self.pixmap.rect())

            # Draw the remote cursor if position is known and not view only
            if self.remote_cursor_pos and not self._view_only:
                # Scale remote cursor position to local widget coordinates
                scaled_x = int(self.remote_cursor_pos[0] * self.width() / self.remote_screen_size.width())
                scaled_y = int(self.remote_cursor_pos[1] * self.height() / self.remote_screen_size.height())

                # Draw a simple crosshair or dot for the cursor
                painter.setPen(QPen(Qt.red, 2))
                painter.drawLine(scaled_x - 5, scaled_y, scaled_x + 5, scaled_y)
                painter.drawLine(scaled_x, scaled_y - 5, scaled_x, scaled_y + 5)
        else:
            painter.fillRect(self.rect(), Qt.black)
            painter.setPen(Qt.white)
            painter.drawText(self.rect(), Qt.AlignCenter, "Waiting for screen data...")
        painter.end()

    def get_scaled_coords(self, pos):
         """Scales local widget coordinates to remote screen coordinates."""
         if not self.remote_screen_size.width() > 1 or not self.remote_screen_size.height() > 1:
             return 0, 0 # Avoid division by zero or using placeholder size
         x = int(pos.x() * self.remote_screen_size.width() / self.width())
         y = int(pos.y() * self.remote_screen_size.height() / self.height())
         return x, y

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
        print(f"Warning: Unhandled key: Qt Key={key}, Text='{text}'")
        return None

# Commenting out the old ClientWindow for now to avoid name clashes
# class ClientWindow(QWidget):
#     # ... (old ClientWindow code) ...
#     pass


# --- New Main Application Window ---
class MainWindow(QMainWindow): # Inherit from QMainWindow for menus, status bar etc.
    """Main application window shown after login."""
    connect_to_peer_signal = pyqtSignal(str) # Emits target UID
    disconnect_signal = pyqtSignal()
    send_chat_message_signal = pyqtSignal(str)
    # Add more signals as needed for settings, screenshot etc.

    def __init__(self, username="Unknown User"): # Pass username for display
        super().__init__()
        self.username = username
        self._create_actions() # Create menu/toolbar actions first
        self._create_menu_bar() # Then create menus
        self._create_status_bar() # Create status bar
        self.initUI()

    def _create_actions(self):
        # Placeholder for actions like Exit, Settings etc.
        self.exit_action = QAction("&Exit", self)
        self.exit_action.triggered.connect(self.close) # Use built-in close

    def _create_menu_bar(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&File")
        file_menu.addAction(self.exit_action)
        # Add other menus (View, Tools, Help) later if needed

    def _create_status_bar(self):
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Ready")

    def initUI(self):
        self.setWindowTitle(f'Remote Desktop - Logged in as {self.username}')

        # --- Central Widget --- 
        central_widget = QWidget()
        self.main_layout = QHBoxLayout(central_widget) # Main layout: Screen on left, controls/chat on right

        # --- Left Side: Screen Display --- 
        screen_container = QGroupBox("Remote Screen")
        screen_layout = QVBoxLayout()
        self.screen_widget = ScreenDisplayWidget() # Re-use the display widget
        # Wrap screen widget in a scroll area just in case
        scroll_area = QScrollArea()
        scroll_area.setWidget(self.screen_widget)
        scroll_area.setWidgetResizable(True)
        screen_layout.addWidget(scroll_area)
        screen_container.setLayout(screen_layout)
        self.main_layout.addWidget(screen_container, 3) # Give screen more space (stretch factor 3)


        # --- Right Side: Controls and Chat --- 
        right_panel_layout = QVBoxLayout()

        # Connection Controls
        connection_group = QGroupBox("Connection")
        connection_layout = QVBoxLayout()
        self.connect_label = QLabel("Connect to User (UID):")
        self.uid_input = QLineEdit()
        self.uid_input.setPlaceholderText("Enter target user's ID")
        self.connect_button = QPushButton("Connect")
        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.setEnabled(False) # Disabled initially
        connection_layout.addWidget(self.connect_label)
        connection_layout.addWidget(self.uid_input)
        connection_layout.addWidget(self.connect_button)
        connection_layout.addWidget(self.disconnect_button)
        connection_group.setLayout(connection_layout)
        right_panel_layout.addWidget(connection_group)

        # Chat Area (Placeholder)
        chat_group = QGroupBox("Chat")
        chat_layout = QVBoxLayout()
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Type message and press Enter...")
        self.chat_send_button = QPushButton("Send") # Optional send button
        chat_input_layout = QHBoxLayout()
        chat_input_layout.addWidget(self.chat_input)
        chat_input_layout.addWidget(self.chat_send_button)
        chat_layout.addWidget(self.chat_display, 1) # Give display more space
        chat_layout.addLayout(chat_input_layout)
        chat_group.setLayout(chat_layout)
        right_panel_layout.addWidget(chat_group)

        right_panel_layout.addStretch() # Push controls up

        self.main_layout.addLayout(right_panel_layout, 1) # Give controls less space (stretch factor 1)

        self.setCentralWidget(central_widget)

        # --- Connect Signals --- 
        self.connect_button.clicked.connect(self.on_connect_clicked)
        self.disconnect_button.clicked.connect(self.disconnect_signal.emit) # Directly emit signal
        self.chat_input.returnPressed.connect(self.on_chat_send)
        self.chat_send_button.clicked.connect(self.on_chat_send)

        # Connect screen widget signals (for sending input later)
        # self.screen_widget.mouse_event_signal.connect(...) # Connect in main controller
        # self.screen_widget.key_event_signal.connect(...)   # Connect in main controller

        self.resize(1200, 700)
        self.show()

    def on_connect_clicked(self):
        target_uid = self.uid_input.text().strip()
        if target_uid:
            self.connect_to_peer_signal.emit(target_uid)
            # Disable connect UI during connection attempt
            self.uid_input.setEnabled(False)
            self.connect_button.setEnabled(False)
            self.update_status(f"Attempting to connect to {target_uid}...")
        else:
            QMessageBox.warning(self, "Input Error", "Please enter the Target User ID.")

    def on_chat_send(self):
        message = self.chat_input.text().strip()
        if message:
            self.send_chat_message_signal.emit(message)
            self.append_chat_message(f"Me: {message}") # Display own message
            self.chat_input.clear()

    def append_chat_message(self, message):
        self.chat_display.append(message)

    def update_status(self, status):
        self.statusBar.showMessage(status)

    def set_connected_state(self, connected_to_uid):
        self.uid_input.setEnabled(False)
        self.connect_button.setEnabled(False)
        self.disconnect_button.setEnabled(True)
        self.update_status(f"Connected to {connected_to_uid}")
        self.screen_widget.setFocus() # Allow screen widget to receive input

    def set_disconnected_state(self, message="Ready"):
        self.uid_input.setEnabled(True)
        self.connect_button.setEnabled(True)
        self.disconnect_button.setEnabled(False)
        self.update_status(message)
        self.screen_widget.pixmap = QPixmap() # Clear screen on disconnect
        self.screen_widget.update()
        self.chat_display.append("<i>--- Disconnected ---</i>")

    # --- Methods to be called by the controller ---
    def update_remote_screen(self, image_data):
        self.screen_widget.update_screen(image_data)

    def update_remote_cursor(self, x, y):
        self.screen_widget.update_remote_cursor(x, y)

    # Override closeEvent to emit disconnect signal if connected?
    # Or handle this in the main controller's cleanup.
    # def closeEvent(self, event):
    #     # self.disconnect_signal.emit() # Maybe?
    #     super().closeEvent(event)

