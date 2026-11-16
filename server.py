import os
import logging
import json
import sys
from typing import Dict, Any, List
from fastapi import FastAPI, HTTPException, Request, Query, Header
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voicebot-server")

app = FastAPI(title="Voicebot Token & Webhook Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

LIVEKIT_API_KEY: str = os.getenv("LIVEKIT_API_KEY", "devkey")
LIVEKIT_API_SECRET: str = os.getenv("LIVEKIT_API_SECRET", "secret")
LIVEKIT_URL: str = os.getenv("LIVEKIT_URL", "ws://127.0.0.1:7880")

webhook_events_log: List[Dict[str, Any]] = []

from livekit.api import AccessToken, VideoGrants, WebhookReceiver, TokenVerifier, LiveKitAPI
from livekit.protocol.agent_dispatch import CreateAgentDispatchRequest

token_verifier = TokenVerifier(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
receiver = WebhookReceiver(token_verifier)


@app.get("/api/token")
async def get_token(
    room_name: str = Query(None),
    participant_name: str = Query(None),
) -> Dict[str, Any]:
    if not LIVEKIT_API_KEY or not LIVEKIT_API_SECRET:
        raise HTTPException(
            status_code=500,
            detail="LiveKit credentials not configured in backend/.env",
        )

    import time
    actual_room = room_name if room_name else f"ecommerce-support-room-{int(time.time() * 1000)}"
    actual_participant = participant_name if participant_name else f"Customer-{int(time.time() % 10000)}"

    token = (
        AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        .with_identity(actual_participant)
        .with_name(actual_participant)
        .with_grants(
            VideoGrants(
                room_join=True,
                room=actual_room,
                can_publish=True,
                can_subscribe=True,
            )
        )
    )

    try:
        api = LiveKitAPI(LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        dispatch_req = CreateAgentDispatchRequest(agent_name="aria", room=actual_room)
        dispatch_res = await api.agent_dispatch.create_dispatch(dispatch_req)
        await api.aclose()
        logger.info(f"Successfully dispatched Agent worker to room '{actual_room}' (Dispatch ID: {getattr(dispatch_res, 'id', 'OK')})")
    except Exception as dispatch_err:
        logger.warning(f"Agent dispatch notice for room '{actual_room}': {dispatch_err}")

    logger.info(f"Generated LiveKit token for room '{actual_room}', participant '{actual_participant}'")

    return {
        "server_url": LIVEKIT_URL,
        "room_name": actual_room,
        "participant_name": actual_participant,
        "token": token.to_jwt(),
    }


@app.post("/api/webhook")
async def handle_webhook(request: Request, authorization: str = Header(None)) -> Dict[str, Any]:
    """
    LiveKit Server-Side Webhook Receiver.
    Receives notifications when room and participant events occur.
    """
    body_bytes = await request.body()
    body_str = body_bytes.decode("utf-8")

    event_data = {}
    try:
        if authorization and LIVEKIT_API_KEY and LIVEKIT_API_SECRET:
            event_obj = receiver.receive(body_str, authorization)
            event_data = {
                "event": getattr(event_obj, "event", "unknown"),
                "room": getattr(getattr(event_obj, "room", None), "name", None),
                "participant": getattr(getattr(event_obj, "participant", None), "identity", None),
                "raw": json.loads(body_str),
            }
        else:
            parsed = json.loads(body_str) if body_str else {}
            event_data = {
                "event": parsed.get("event", "unknown_event"),
                "room": parsed.get("room", {}).get("name"),
                "participant": parsed.get("participant", {}).get("identity"),
                "raw": parsed,
            }
    except Exception as e:
        logger.warning(f"Webhook signature or parsing warning: {e}")
        try:
            parsed = json.loads(body_str) if body_str else {}
            event_data = {
                "event": parsed.get("event", "unverified_event"),
                "room": parsed.get("room", {}).get("name"),
                "participant": parsed.get("participant", {}).get("identity"),
                "raw": parsed,
                "warning": str(e),
            }
        except Exception:
            event_data = {"event": "parse_error", "raw_body": body_str}

    logger.info(f"🔔 LiveKit Webhook Event Received: {event_data.get('event')} | Room: {event_data.get('room')} | Participant: {event_data.get('participant')}")

    webhook_events_log.append(event_data)
    if len(webhook_events_log) > 50:
        webhook_events_log.pop(0)

    return {"status": "success", "event_received": event_data.get("event")}


@app.get("/api/webhook/events")
async def get_webhook_events() -> Dict[str, Any]:
    """Retrieve recent server-side room & participant webhook events."""
    return {"total": len(webhook_events_log), "events": webhook_events_log}


@app.get("/api/health")
async def health_check() -> Dict[str, str]:
    return {"status": "ok", "livekit_url": LIVEKIT_URL}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True)
