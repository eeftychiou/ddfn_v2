import asyncio
import json
import logging
import random
import websockets
from typing import Callable, Dict, List, Any, Optional

logger = logging.getLogger("NetworkClient")

class NetworkClient:
    """
    Connects to the central V2 Message Broker over WebSockets.
    Features outbound message buffering and exponential backoff reconnection.
    """
    def __init__(self, broker_url="ws://127.0.0.1:8001/ws"):
        self.broker_url = broker_url
        self.subscribers: Dict[str, List[asyncio.Queue]] = {}
        self.websocket = None
        self.node_id = None
        self._connected_event = asyncio.Event()
        self._outbound_buffer: asyncio.Queue = asyncio.Queue()
        self._reconnect_delay = 5.0
        self._max_reconnect_delay = 60.0
        self._buffer_task: Optional[asyncio.Task] = None
        
    async def connect(self, node_id: str):
        self.node_id = node_id
        self._buffer_task = asyncio.create_task(self._buffer_flush_loop())
        asyncio.create_task(self._maintain_connection())
        await self._connected_event.wait()

    async def _maintain_connection(self):
        while True:
            try:
                logger.info(f"Connecting to broker at {self.broker_url}...")
                async with websockets.connect(self.broker_url) as ws:
                    self.websocket = ws
                    await ws.send(json.dumps({"action": "hello", "node_id": self.node_id}))
                    
                    # Re-subscribe to all topics
                    for topic in self.subscribers.keys():
                        await ws.send(json.dumps({
                            "action": "subscribe",
                            "topic": topic
                        }))
                    
                    # Reset backoff on successful connection
                    self._reconnect_delay = 5.0
                    self._connected_event.set()
                    logger.info(f"Connected to message broker at {self.broker_url}")
                    
                    async for message in ws:
                        data = json.loads(message)
                        topic = data.get("topic")
                        payload = data.get("message")
                        
                        if topic in self.subscribers:
                            for queue in self.subscribers[topic]:
                                await queue.put(payload)
                                
            except Exception as e:
                self._connected_event.clear()
                self.websocket = None
                logger.warning(f"NetworkClient connection lost/failed: {e}. Retrying in {self._reconnect_delay}s...")
                await asyncio.sleep(self._reconnect_delay)
                # Exponential backoff with jitter
                self._reconnect_delay = min(
                    self._reconnect_delay * 1.5 + random.uniform(0, 2),
                    self._max_reconnect_delay
                )

    async def _buffer_flush_loop(self):
        """Background task to flush buffered messages when connection is available."""
        while True:
            try:
                topic, message = await self._outbound_buffer.get()
                # Wait for connection
                if not self.websocket:
                    await self._connected_event.wait()
                
                if self.websocket:
                    try:
                        await self.websocket.send(json.dumps({
                            "action": "publish",
                            "topic": topic,
                            "message": message
                        }))
                        logger.info(f"Published to [{topic}]: {message.get('message_type') if isinstance(message, dict) else type(message)}")
                    except Exception as e:
                        logger.error(f"Failed to publish buffered message to {topic}: {e}")
                        # Re-queue for retry
                        await self._outbound_buffer.put((topic, message))
                        await asyncio.sleep(1)
                else:
                    # Still no connection, re-queue
                    await self._outbound_buffer.put((topic, message))
                    await asyncio.sleep(1)
                    
                self._outbound_buffer.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Buffer flush loop error: {e}")
                await asyncio.sleep(1)

    async def subscribe(self, topic: str, queue: asyncio.Queue):
        if topic not in self.subscribers:
            self.subscribers[topic] = []
            if self.websocket:
                try:
                    await self.websocket.send(json.dumps({
                        "action": "subscribe",
                        "topic": topic
                    }))
                except: pass
        self.subscribers[topic].append(queue)
        logger.debug(f"Subscribed to topic: {topic}")

    async def publish(self, topic: str, message: Any):
        """Publish a message. If disconnected, buffer for later delivery."""
        if self.websocket:
            try:
                await self.websocket.send(json.dumps({
                    "action": "publish",
                    "topic": topic,
                    "message": message
                }))
                logger.info(f"Published to [{topic}]: {message.get('message_type') if isinstance(message, dict) else type(message)}")
            except Exception as e:
                logger.warning(f"Publish failed, buffering: {e}")
                await self._outbound_buffer.put((topic, message))
        else:
            logger.warning(f"Not connected to broker. Buffering message for {topic}.")
            await self._outbound_buffer.put((topic, message))

    async def close(self):
        """Close the network client and cancel background tasks."""
        if self._buffer_task:
            self._buffer_task.cancel()
            try:
                await self._buffer_task
            except asyncio.CancelledError:
                pass
