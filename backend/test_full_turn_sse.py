import asyncio
import json
import sys

sys.path.insert(0, ".")
from app.routes.turn import process_turn
from app.db.models import TurnRequest
from fastapi import BackgroundTasks

async def run_live_test():
    print("=================================================================")
    print("[TEST] RUNNING LIVE FULL-TURN SSE & DVS TEST")
    print("=================================================================")

    # Create dummy user and request
    user = {"user_id": "test-student-123", "email": "test@example.com"}
    req = TurnRequest(
        session_id="test-session-dvs-live",
        student_message="Can you show me a visual diagram of how a PN junction works in forward bias?",
        chronometric_load_score=0.35
    )
    bg_tasks = BackgroundTasks()

    print(f"\n[1] Sending Prompt: '{req.student_message}'")
    streaming_response = await process_turn(req, bg_tasks, user)

    events_received = []
    streamed_tokens = ""
    dvs_svg = None
    done_payload = None

    print("\n[2] Listening to SSE Stream Events...")
    async for chunk in streaming_response.body_iterator:
        text = chunk if isinstance(chunk, str) else chunk.decode("utf-8")
        for block in text.split("\n\n"):
            if not block.strip():
                continue
            lines = block.strip().split("\n")
            event_type = ""
            data_str = ""
            for line in lines:
                if line.startswith("event: "):
                    event_type = line[7:].strip()
                elif line.startswith("data: "):
                    data_str = line[6:].strip()
            
            if event_type:
                events_received.append(event_type)
                if event_type == "status":
                    data = json.loads(data_str)
                    print(f"  * [STATUS]: {data.get('msg')}")
                elif event_type == "token":
                    data = json.loads(data_str)
                    streamed_tokens += data.get("token", "")
                elif event_type == "dvs":
                    data = json.loads(data_str)
                    dvs_svg = data.get("svg")
                    print(f"  * [DVS EVENT RECEIVED]: SVG size = {len(dvs_svg)} chars")
                elif event_type == "done":
                    done_payload = json.loads(data_str)
                    print(f"  * [DONE EVENT]: {done_payload}")

    print("\n=================================================================")
    print("[REPORT] TEST SUMMARY")
    print("=================================================================")
    print(f"1. Events Captured: {set(events_received)}")
    print(f"2. Streamed Tutor Text:\n   \"{streamed_tokens.strip()}\"")
    print(f"3. DVS Diagram Generated: {dvs_svg is not None}")
    if dvs_svg:
        print(f"   - SVG Length: {len(dvs_svg)} characters")
        print(f"   - SVG Opening: {dvs_svg[:75]}...")
        print(f"   - SVG Closing: ...{dvs_svg[-25:]}")
    print(f"4. Done Signal: {done_payload}")
    print("=================================================================")

if __name__ == "__main__":
    asyncio.run(run_live_test())
