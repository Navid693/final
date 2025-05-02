#!/usr/bin/env python3
import asyncio
import json
import websockets
import logging
import signal
import sys
import time
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("server.log")
    ]
)

logger = logging.getLogger('SimpleServer')

class SimpleServer:
    def __init__(self, host='localhost', port=8765):
        self.host = host
        self.port = port
        self.clients = {}  # username -> WebSocket connection
        self.connections = {}  # username -> connected peer username
        self.message_counts = {"text": 0, "binary": 0}
        self.start_time = time.time()
        
        # Register signal handlers for graceful shutdown
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, self.shutdown)
    
    async def handle_client(self, websocket):
        """Handle a client connection."""
        client_username = None
        remote_address = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        
        try:
            logger.info(f"New connection from {remote_address}")
            
            async for message in websocket:
                # Check if it's binary data (screen sharing)
                if isinstance(message, bytes):
                    self.message_counts["binary"] += 1
                    
                    # Find the peer to forward the binary data to
                    if client_username and client_username in self.connections:
                        peer_username = self.connections[client_username]
                        if peer_username in self.clients:
                            peer_ws = self.clients[peer_username]
                            try:
                                await peer_ws.send(message)
                            except Exception as e:
                                logger.error(f"Error forwarding binary data to {peer_username}: {e}")
                    continue
                
                # Process JSON messages
                self.message_counts["text"] += 1
                data = json.loads(message)
                message_type = data.get("type")
                
                if message_type == "register":
                    # Register a new client
                    new_username = data.get("username")
                    
                    # Check if username is already taken
                    if new_username in self.clients:
                        # Append a random suffix to make it unique
                        import random
                        new_username = f"{new_username}_{random.randint(100, 999)}"
                        
                    # Store the client
                    client_username = new_username
                    self.clients[client_username] = websocket
                    
                    # Send success response
                    await websocket.send(json.dumps({
                        "type": "register_response",
                        "success": True,
                        "message": f"Registered as {client_username}"
                    }))
                    
                    logger.info(f"Client {client_username} registered successfully")
                    
                    # Send updated users list to all clients
                    await self.broadcast_users_list()
                    
                elif message_type == "request_connection":
                    # Request a connection to another client
                    if not client_username:
                        continue
                        
                    target_user = data.get("to_user")
                    if target_user in self.clients:
                        # Forward the request to the target user
                        await self.clients[target_user].send(json.dumps({
                            "type": "connection_request",
                            "from_user": client_username
                        }))
                        
                        logger.info(f"{client_username} requesting connection to {target_user}")
                    
                elif message_type == "connection_response":
                    # Handle connection response (accept/reject)
                    if not client_username:
                        continue
                        
                    target_user = data.get("to_user")
                    accepted = data.get("accepted", False)
                    reason = data.get("reason", "")
                    
                    if target_user in self.clients:
                        # Forward the response to the target user
                        response = {
                            "type": "connection_response",
                            "from_user": client_username,
                            "accepted": accepted
                        }
                        if not accepted and reason:
                            response["reason"] = reason
                            
                        await self.clients[target_user].send(json.dumps(response))
                        
                        if accepted:
                            # Store the connection
                            self.connections[client_username] = target_user
                            self.connections[target_user] = client_username
                            logger.info(f"{client_username} accepted connection from {target_user}")
                        else:
                            logger.info(f"{client_username} rejected connection from {target_user}: {reason}")
                    
                elif message_type == "disconnect_peer":
                    # Handle peer disconnection
                    if not client_username or client_username not in self.connections:
                        continue
                        
                    peer_username = self.connections[client_username]
                    
                    # Remove the connection from both sides
                    if peer_username in self.connections:
                        self.connections.pop(peer_username)
                    self.connections.pop(client_username)
                    
                    # Notify the peer
                    if peer_username in self.clients:
                        await self.clients[peer_username].send(json.dumps({
                            "type": "peer_disconnected",
                            "peer": client_username,
                            "reason": "Peer disconnected"
                        }))
                        
                    logger.info(f"{client_username} disconnected from {peer_username}")
                
                elif message_type == "chat_message":
                    # Forward chat message to peer
                    if not client_username or client_username not in self.connections:
                        continue
                        
                    target_user = data.get("to_user")
                    text = data.get("text", "")
                    
                    if target_user in self.clients:
                        await self.clients[target_user].send(json.dumps({
                            "type": "chat_message",
                            "from_user": client_username,
                            "text": text
                        }))
                
                elif message_type == "pong":
                    # Client responded to ping
                    logger.debug(f"Received pong from {client_username}")
                
                elif message_type == "input_event":
                    # Forward input event to peer
                    if not client_username or client_username not in self.connections:
                        continue
                        
                    target_user = data.get("to_user")
                    event_data = data.get("event", {})
                    
                    if target_user in self.clients:
                        await self.clients[target_user].send(json.dumps({
                            "type": "input_event",
                            "from_user": client_username,
                            "event": event_data
                        }))
                
                else:
                    logger.warning(f"Unknown message type: {message_type}")
        
        except websockets.exceptions.ConnectionClosed as e:
            logger.info(f"Client {client_username} disconnected: {e}")
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON received from {remote_address}")
        except Exception as e:
            logger.error(f"Error handling client {client_username}: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Clean up when client disconnects
            if client_username:
                # Remove client
                if client_username in self.clients:
                    self.clients.pop(client_username)
                
                # Notify peer if connected
                if client_username in self.connections:
                    peer_username = self.connections[client_username]
                    
                    # Remove the connection from both sides
                    if peer_username in self.connections:
                        self.connections.pop(peer_username)
                    self.connections.pop(client_username)
                    
                    # Notify the peer
                    if peer_username in self.clients:
                        try:
                            await self.clients[peer_username].send(json.dumps({
                                "type": "peer_disconnected",
                                "peer": client_username,
                                "reason": "Client disconnected"
                            }))
                        except:
                            pass
                
                logger.info(f"Client {client_username} disconnected")
                
                # Broadcast updated users list
                await self.broadcast_users_list()
    
    async def broadcast_users_list(self):
        """Broadcast the list of connected users to all clients."""
        users_list = list(self.clients.keys())
        
        for username, websocket in self.clients.items():
            try:
                await websocket.send(json.dumps({
                    "type": "users_list",
                    "users": users_list
                }))
            except Exception as e:
                logger.error(f"Error sending users list to {username}: {e}")
    
    async def status_monitor(self):
        """Periodically log server status and send pings to clients."""
        while True:
            await asyncio.sleep(60)  # Every 60 seconds
            
            # Calculate uptime
            uptime = time.time() - self.start_time
            uptime_str = self.format_uptime(uptime)
            
            # Log status
            logger.info(f"Server status: Uptime={uptime_str}, Clients={len(self.clients)}, "
                        f"Connections={len(self.connections)//2}, "
                        f"Messages processed: {self.message_counts}")
            
            # Send ping to all clients
            for username, websocket in list(self.clients.items()):
                try:
                    await websocket.send(json.dumps({"type": "ping"}))
                except:
                    # Client may have disconnected, will be cleaned up later
                    pass
    
    def format_uptime(self, seconds):
        """Format uptime in seconds to a readable string."""
        days, remainder = divmod(int(seconds), 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if days > 0:
            return f"{days}d {hours}h {minutes}m {seconds}s"
        elif hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
    
    async def run(self):
        """Run the WebSocket server."""
        server = await websockets.serve(
            self.handle_client, self.host, self.port
        )
        
        logger.info(f"Starting server on {self.host}:{self.port}")
        
        # Start status monitor
        asyncio.create_task(self.status_monitor())
        
        logger.info(f"Server started on ws://{self.host}:{self.port}")
        
        await server.wait_closed()
    
    def shutdown(self, sig, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {sig}, shutting down...")
        # Clean up resources here
        logger.info("Server stopped.")
        sys.exit(0)

if __name__ == "__main__":
    server = SimpleServer()
    
    # Run the server
    asyncio.run(server.run()) 