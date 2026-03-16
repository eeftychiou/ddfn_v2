import asyncio
import json
import logging
import websockets
from typing import Callable, Dict, List, Any

# Configure brief logging
logger = logging.getLogger("NetworkClient")

class NetworkClient:
    """
    Connects to the central V2 Message Broker over WebSockets.
    Replaces the pure in-memory EventBus from the PoC.
    """
    def __init__(self, broker_url="ws://127.0.0.1:8001/ws"):
        self.broker_url = broker_url
        self.subscribers: Dict[str, List[asyncio.Queue]] = {}
        self.websocket = None
        self.node_id = None
        self._connected_event = asyncio.Event()
        
    async def connect(self, node_id: str):
        self.node_id = node_id
        asyncio.create_task(self._maintain_connection())
        # Wait until first connection is established
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
                logger.warning(f"NetworkClient connection lost/failed: {e}. Retrying in 5s...")
                await asyncio.sleep(5)

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
        if self.websocket:
            try:
                logger.info(f"Publishing to [{topic}]: {message.get('message_type') if isinstance(message, dict) else type(message)}")
                await self.websocket.send(json.dumps({
                    "action": "publish",
                    "topic": topic,
                    "message": message
                }))
            except Exception as e:
                logger.error(f"Failed to publish to {topic}: {e}")
        else:
            logger.warning(f"Cannot publish to {topic}: Not connected to broker.")
