from ddfn_v2.services.fmp_service import FMPNode
from ddfn_v2.core.network import NetworkClient
import asyncio

async def test():
    network = NetworkClient()
    node = FMPNode("DIAG_NODE", network, [])
    print(f"INITIAL IS_CONFIGURED: {node.is_configured}")
    print(f"INITIAL _IS_CONFIGURED: {node._is_configured}")

if __name__ == "__main__":
    asyncio.run(test())
