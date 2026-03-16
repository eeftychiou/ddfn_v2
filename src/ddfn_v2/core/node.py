import asyncio
import logging
from typing import Dict, Any, Callable
from ddfn_v2.core.network import NetworkClient

logger = logging.getLogger("DDFN_Node")

class DDFN_Node:
    """
    Base decentralized node. Subscribes to the external SWIM WebSocket broker.
    """
    def __init__(self, node_id: str, network: NetworkClient):
        self.node_id = node_id
        self.network = network
        self.subscription_queue = asyncio.Queue()
        self.handlers: Dict[str, Callable] = {}
        # Make a specific logger for this instance
        self.logger = logging.getLogger(f"Node[{node_id}]")

    async def start(self):
        self.logger.info("Starting DDFN Node instance and listening on SWIM topics...")
        
        # Connect to broker
        await self.network.connect(self.node_id)

        # Core SWIM topics
        await self.network.subscribe("ddfn.capacity.state", self.subscription_queue)
        await self.network.subscribe("ddfn.warning.trigger", self.subscription_queue)
        await self.network.subscribe("ddfn.negotiation.proposal", self.subscription_queue)
        await self.network.subscribe("ddfn.flow.consensus", self.subscription_queue)
        # UI/HITL specific topics
        await self.network.subscribe("ddfn.ui.proposal_action", self.subscription_queue)
        await self.network.subscribe("ddfn.ui.capacity_override", self.subscription_queue)

        self._loop_task = asyncio.create_task(self._message_loop())

    async def stop(self):
        """Stop the node and its message loop."""
        self.logger.info("Stopping DDFN Node...")
        if hasattr(self, '_loop_task'):
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass

    def register_handler(self, message_type: str, handler: Callable):
        self.handlers[message_type] = handler

    async def _message_loop(self):
        while True:
            try:
                msg = await self.subscription_queue.get()
                msg_type = msg.get("message_type")
                self.logger.info(f"DDFN Received: {msg.get('message_type')} on node {self.node_id}")
                if msg_type in self.handlers:
                    await self.handlers[msg_type](msg)
            except Exception as e:
                self.logger.error(f"Error handling message: {e}")

    async def emit(self, topic: str, message_model):
        """Helper to convert dataclass or Pydantic model -> json dict and publish"""
        if hasattr(message_model, "model_dump"):
            msg_dict = message_model.model_dump()
        else:
            import dataclasses
            if dataclasses.is_dataclass(message_model):
                msg_dict = dataclasses.asdict(message_model)
            else:
                msg_dict = message_model # assume it's already a dict or serializable
        
        await self.network.publish(topic, msg_dict)
