# Screen Sharing and Remote Control Application

This application allows users to share their screen and remotely control each other's computers over a WebSocket connection. It features a simple peer-to-peer architecture with a central WebSocket server for signaling.

## Features

- User registration and presence management
- Peer-to-peer connections
- Screen sharing with configurable quality, scale, and FPS
- Remote mouse and keyboard control
- Chat functionality
- Multi-monitor support
- Simple and intuitive UI

## Setup and Installation

1. Clone the repository
2. Install the dependencies:
   ```
   pip install -r requirements.txt
   ```

## Running the Application

### Starting the Server

Run the WebSocket server:

```
python simple_server.py
```

The server will start on `localhost:8765`.

### Running the Client

Start the client application:

```
python test_client.py
```

## Usage

1. **Connect to Server**:
   - Enter a server URL (default: `ws://localhost:8765`)
   - Enter a username
   - Click "Connect"

2. **Connect to Peers**:
   - Available users will be listed
   - Select a user from the list
   - Click "Connect to Selected User"
   - The other user will receive a connection request

3. **Share Your Screen**:
   - Once connected, click "Start Sharing"
   - You can adjust quality, scale, and FPS settings
   - Click "Stop Sharing" to end sharing

4. **Chat**:
   - Use the chat panel to send messages to your connected peer

## Configuring Screen Sharing

- **Quality**: Controls JPEG compression quality (10-100%)
- **Scale**: Controls the size of the shared screen (25-100%)
- **FPS**: Controls frames per second (5-30)
- **Monitor**: Select which monitor to share for multi-monitor setups

## Architecture

The application uses three main components:

1. **WebSocketHandler**: Manages WebSocket connections and communication
2. **RemoteController**: Handles screen capturing, input events, and remote control
3. **TestClient/UI**: Provides the user interface

## Trouble-shooting

- If you encounter connection issues, ensure the server is running
- Check that no firewall is blocking the WebSocket connection
- For screen capturing issues on Windows, make sure you have proper permissions
- For input control, some systems may require admin privileges

## Security Note

This application does not implement encryption or authentication beyond basic username registration. It is intended for use in trusted networks for demonstration purposes only.

## License

MIT License

## Credits

Built with PyQt5, websocket-client, and pyautogui. 