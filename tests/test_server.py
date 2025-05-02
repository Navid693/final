import unittest
import sys
import os
import asyncio
import websockets
import json
import threading
import time
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simple_server import SimpleServer
from concurrent.futures import ThreadPoolExecutor

class TestServer(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        self.server = SimpleServer(host='localhost', port=8766)
        # Start server in a separate thread
        self.server_thread = threading.Thread(target=self.run_server)
        self.server_thread.daemon = True
        self.server_thread.start()
        time.sleep(1)  # Give server time to start

    def run_server(self):
        """Run the server in the current thread"""
        asyncio.set_event_loop(asyncio.new_event_loop())
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.server.run())

    async def create_client(self, username):
        """Create a test client"""
        uri = "ws://localhost:8766/ws"
        async with websockets.connect(uri) as websocket:
            # Register user
            await websocket.send(json.dumps({
                "type": "register",
                "username": username
            }))
            response = await websocket.recv()
            return json.loads(response)

    async def test_client_registration(self):
        """Test client registration process"""
        # Test successful registration
        response = await self.create_client("test_user1")
        self.assertEqual(response["type"], "register_response")
        self.assertTrue(response["success"])

        # Test duplicate username
        response = await self.create_client("test_user1")
        self.assertEqual(response["type"], "register_response")
        self.assertFalse(response["success"])

    async def test_multiple_clients(self):
        """Test handling multiple client connections"""
        # Create multiple clients
        clients = []
        usernames = ["user1", "user2", "user3"]
        
        for username in usernames:
            response = await self.create_client(username)
            self.assertTrue(response["success"])
            clients.append(username)

        # Verify server state
        self.assertEqual(len(self.server.clients), len(clients))

    async def test_client_disconnect(self):
        """Test client disconnection handling"""
        # Connect a client
        response = await self.create_client("test_user")
        self.assertTrue(response["success"])
        
        # Force disconnect (will be handled by server cleanup)
        initial_client_count = len(self.server.clients)
        # Client websocket will auto-close after context
        
        # Give server time to clean up
        await asyncio.sleep(1)
        self.assertLess(len(self.server.clients), initial_client_count)

    async def test_message_broadcasting(self):
        """Test message broadcasting to clients"""
        async def client_handler(uri, username):
            async with websockets.connect(uri) as websocket:
                # Register
                await websocket.send(json.dumps({
                    "type": "register",
                    "username": username
                }))
                await websocket.recv()  # Registration response
                
                # Send and receive messages
                if username == "sender":
                    await websocket.send(json.dumps({
                        "type": "chat_message",
                        "text": "Test broadcast"
                    }))
                else:
                    response = await websocket.recv()
                    return json.loads(response)
                
                return None

        # Create multiple clients
        uri = "ws://localhost:8766/ws"
        tasks = [
            client_handler(uri, "sender"),
            client_handler(uri, "receiver1"),
            client_handler(uri, "receiver2")
        ]
        
        # Run clients concurrently
        results = await asyncio.gather(*tasks)
        
        # Check that receivers got the message
        for result in results[1:]:  # Skip sender's result
            if result and result["type"] == "chat_message":
                self.assertEqual(result["text"], "Test broadcast")

    async def test_server_ping(self):
        """Test server ping mechanism"""
        uri = "ws://localhost:8766/ws"
        async with websockets.connect(uri) as websocket:
            # Register
            await websocket.send(json.dumps({
                "type": "register",
                "username": "ping_test_user"
            }))
            await websocket.recv()  # Registration response
            
            # Wait for ping
            await asyncio.sleep(30)  # Adjust based on ping interval
            
            # Server should still be running and client connected
            self.assertTrue(self.server.is_running)
            self.assertIn("ping_test_user", self.server.clients)

    def test_server_shutdown(self):
        """Test server shutdown"""
        self.assertTrue(self.server.is_running)
        self.server.shutdown(None, None)  # Simulate shutdown signal
        self.assertFalse(self.server.is_running)

    def tearDown(self):
        """Clean up after each test"""
        self.server.shutdown(None, None)
        self.server_thread.join(timeout=1)

def run_async_test(coro):
    """Helper to run async tests"""
    with ThreadPoolExecutor() as executor:
        future = executor.submit(asyncio.run, coro)
        return future.result()

if __name__ == '__main__':
    # Modify test methods to run async tests
    async_methods = [
        'test_client_registration',
        'test_multiple_clients',
        'test_client_disconnect',
        'test_message_broadcasting',
        'test_server_ping'
    ]
    
    for method in async_methods:
        original = getattr(TestServer, method)
        setattr(TestServer, method, 
                lambda self, orig=original: run_async_test(orig(self)))
    
    unittest.main()