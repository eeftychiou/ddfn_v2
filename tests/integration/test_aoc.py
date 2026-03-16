import asyncio
import websockets
import json
import urllib.request
import uuid

async def main():
    max_retries = 5
    for attempt in range(max_retries):
        try:
            print(f"Connecting to broker at ws://127.0.0.1:8001/ws (Attempt {attempt+1}/{max_retries})...")
            ws = await websockets.connect("ws://127.0.0.1:8001/ws", open_timeout=30)
            break
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"Failed to connect after {max_retries} attempts: {e}")
                return
            await asyncio.sleep(2)
            
    async with ws:
        # Subscribe to consensus and inbox topics
        await ws.send(json.dumps({
            "action": "subscribe",
            "topic": "ddfn.flow.consensus"
        }))
        await ws.send(json.dumps({
            "action": "subscribe",
            "topic": "ddfn.ui.inbox"
        }))
        
        print("1. Forcing capacity constraint on EGTT1C to generate CTOT delays...")
        data = json.dumps({
            "target_node": "EGTT1C_DDFN_NODE",
            "sector": "EGTT1C",
            "capacity": 2, # Very low capacity
            "reason": "Test Scavenging"
        }).encode('utf-8')
        req = urllib.request.Request("http://127.0.0.1:8023/api/sectors/override", data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as response:
            print("HTTP response:", json.loads(response.read().decode('utf-8')))
        
        print("2. Connecting to CASA WS and Auto-Approving Inbox Requests...")
        target_flight = None
        target_warn_id = None
        
        while True:
            raw_msg = await ws.recv()
            if not raw_msg: continue
            
            try:
                msg = json.loads(raw_msg)
            except: continue
                
            topic = msg.get("topic")
            payload = msg.get("message", {})
            msg_type = payload.get("message_type")
            
            if topic == "ddfn.ui.inbox" and msg_type == "UI_INBOX_APPROVAL_REQUEST":
                wid = payload.get("warning_id")
                print(f"-> Caught HITL Inbox Request for {wid}. Auto-approving...")
                await ws.send(json.dumps({
                    "action": "publish",
                    "topic": "ddfn.fmp.command",
                    "message": {
                        "message_type": "FMP_PROPOSAL_APPROVAL",
                        "target_node": "EGTT1C_DDFN_NODE",
                        "warning_id": wid,
                        "action": "APPROVE"
                    }
                }))
                
            elif topic == "ddfn.flow.consensus" and msg_type != "CAPACITY_STATE_BROADCAST":
                slots = payload.get("slot_table", [])
                if slots:
                    print(f"-> Received CASA Consensus with {len(slots)} delayed flights.")
                    for s in slots:
                        # Find a delayed EGLL flight (BAW)
                        f_id = s.get("flight_id", "")
                        # skip the first one to ensure there is a BETTER slot (less delay) available
                        if s.get("delay", 0) > 0:
                            if not target_flight:
                                target_flight = f_id # Temporary hold
                                continue 
                            # If we are here, this is at least the second delayed flight
                            target_flight = f_id
                            target_warn_id = payload.get("referencing_warning_id")
                            origin = s.get("origin", "EGLL")
                            print(f"Found target delayed flight for scavenging: {f_id} with delay {s.get('delay')}m (Origin: {origin})")
                            break
                    if target_flight:
                        break
        
        if not target_flight:
            print("No suitable flight found for scavenging.")
            return
            
        print(f"3. Broadcasting AOCC_READY_TO_FLY for {target_flight} (Origin: {origin})...")
        await ws.send(json.dumps({
            "action": "publish",
            "topic": "ddfn.aoc.messages",
            "message": {
                "message_type": "AOCC_READY_TO_FLY",
                "flight_id": target_flight,
                "origin_node": origin
            }
        }))
        
        print("4. Check airport_EGLL and fmp_EGTT running logs to see if scavenging succeeded!")
        await asyncio.sleep(2)
        print("Done.")

if __name__ == "__main__":
    asyncio.run(main())

