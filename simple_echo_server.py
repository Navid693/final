# simple_echo_server.py
import asyncio
import websockets
import json
import logging

# Configure logging for websockets library (optional, but helpful for ping/pong debug)
# logging.basicConfig(level=logging.DEBUG)

CONNECTED_CLIENTS = set()

async def broadcast(message, sender, is_binary):
    """Sends a message to all connected clients except the sender."""
    disconnected_clients = set()
    for client in CONNECTED_CLIENTS:
        if client != sender:
            try:
                await client.send(message)
            except websockets.exceptions.ConnectionClosed:
                print(f"[Server] Broadcast failed: Client {client.remote_address} disconnected.")
                disconnected_clients.add(client)
            except Exception as e:
                print(f"[Server] Error broadcasting to {client.remote_address}: {e}")
                disconnected_clients.add(client)
    # Remove clients that failed during broadcast
    for client in disconnected_clients:
        CONNECTED_CLIENTS.remove(client)


async def handler(websocket):
    client_addr = websocket.remote_address
    print(f"[Server] Client connected: {client_addr}")
    # print(f"[Server] Headers: {websocket.request_headers}") # Uncomment to see headers (like Authorization)
    CONNECTED_CLIENTS.add(websocket)

    try:
        async for message in websocket:
            # Check if message is binary or text
            is_binary = isinstance(message, bytes)
            # print(f"[Server] Received message type: {'Binary' if is_binary else 'Text'}")

            if is_binary:
                # Assume binary is screen data for now
                # We check the first byte if needed, but just broadcast
                # print(f"[Server] Broadcasting binary data from {client_addr}")
                await broadcast(message, websocket, is_binary=True)
            else: # It's a text message, try parsing as JSON
                try:
                    data = json.loads(message)
                    message_type = data.get("type")

                    if message_type == "screen_data":
                        # This should not happen if client sends binary for screen
                        print("[Server] Warning: Received screen_data as text, broadcasting anyway.")
                        await broadcast(message, websocket, is_binary=False)
                    elif message_type == "input_event":
                        # Broadcast input events to other clients
                        print(f"[Server] Broadcasting input event from {client_addr}")
                        await broadcast(message, websocket, is_binary=False)
                    elif message_type == "disconnect_notice":
                        # Broadcast disconnect notice to other clients
                        print(f"[Server] Broadcasting disconnect notice from {client_addr}")
                        await broadcast(message, websocket, is_binary=False)
                    elif message_type == "chat":
                        # Echo chat back to sender, maybe prefixing who it's from
                        sender_id = data.get('sender', str(client_addr))
                        response_data = {
                            'type': 'chat',
                            'sender': f'ServerEcho ({sender_id})',
                            'message': data.get('message', '')
                        }
                        await websocket.send(json.dumps(response_data))
                        print(f"[Server] Echoed chat response to {client_addr}")
                        # Optionally, broadcast chat to others too?
                        # broadcast_data = {'type': 'chat', 'sender': sender_id, 'message': data.get('message', '')}
                        # await broadcast(json.dumps(broadcast_data), websocket)
                    elif message_type == "connect_request":
                        # Just echo back confirmation for testing
                        response = {
                            "type": "echo",
                            "status": "received_request",
                            "info": f"Received connection request for {data.get('target_uid')}"
                        }
                        await websocket.send(json.dumps(response))
                        print(f"[Server] Echoed connect_request response to {client_addr}")
                    else:
                        # Echo other JSON messages back to sender
                        response = {"type": "echo", "original_message": data}
                        await websocket.send(json.dumps(response))
                        print(f"[Server] Echoed generic JSON response to {client_addr}")

                except json.JSONDecodeError:
                    # If text is not JSON, echo raw string back to sender
                    print(f"[Server] Received non-JSON text from {client_addr}: {message}")
                    response = f"Echo: {message}"
                    await websocket.send(response)
                    print(f"[Server] Echoed raw text response to {client_addr}")

    except websockets.exceptions.ConnectionClosedOK:
        print(f"[Server] Client {client_addr} disconnected normally.")
    except websockets.exceptions.ConnectionClosedError as e:
        print(f"[Server] Client {client_addr} disconnected with error: {e}")
    except Exception as e:
        print(f"[Server] Error handling client {client_addr}: {e}")
    finally:
        print(f"[Server] Removing client {client_addr}")
        if websocket in CONNECTED_CLIENTS:
             CONNECTED_CLIENTS.remove(websocket)

async def main():
    host = "localhost" # Listen only on local machine
    port = 8000        # Port the client expects (via http://localhost:8000)
    print(f"[Server] Starting WebSocket server on ws://{host}:{port} ...")
    # Note: The server doesn't care about the /ws/connect path here
    # The websockets library handles ping/pong automatically by default with serve()
    # Increase max_size significantly to handle large frames (e.g., 5 MiB)
    async with websockets.serve(handler, host, port,
                              ping_interval=20, ping_timeout=20,
                              max_size=5*1024*1024): # Allow up to 5 MiB messages
        # Increased ping_timeout on server side for robustness
        await asyncio.Future()  # Run forever until stopped

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[Server] Shutting down...") 