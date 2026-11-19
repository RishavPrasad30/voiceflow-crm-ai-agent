import json
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

app = FastAPI(title="VoiceFlow CRM - AI Voice & Lead Qualification Agent", version="1.0.0")
CRM_LEADS = {}

class CallWebhookPayload(BaseModel):
    call_sid: str
    caller_number: str
    transcript_chunk: str
    turn_id: int = 1

def evaluate_lead_turn(transcript: str) -> dict:
    text = transcript.lower()
    if any(k in text for k in ["demo", "pricing", "enterprise", "buy", "interested"]):
        return {"intent": "high_intent_purchase", "qualification_score": 88, "sentiment": "positive", "next_action": "book_ae_calendar_slot", "agent_reply": "I can schedule a walkthrough for your team. Does tomorrow at 11 AM IST work?"}
    if any(k in text for k in ["not interested", "stop", "unsubscribe", "busy"]):
        return {"intent": "opt_out_or_busy", "qualification_score": 15, "sentiment": "negative", "next_action": "mark_do_not_disturb", "agent_reply": "Understood, I will update your preferences right away. Thank you!"}
    return {"intent": "discovery_inquiry", "qualification_score": 55, "sentiment": "neutral", "next_action": "qualify_company_size", "agent_reply": "Thanks for reaching out! Roughly how many team members will use this?"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@app.post("/webhooks/telephony/turn")
async def handle_telephony_turn(payload: CallWebhookPayload):
    decision = evaluate_lead_turn(payload.transcript_chunk)
    CRM_LEADS[payload.call_sid] = {"caller_number": payload.caller_number, "turn_id": payload.turn_id, **decision}
    return {"call_sid": payload.call_sid, **decision}

@app.websocket("/ws/voice-stream/{call_sid}")
async def voice_stream_socket(websocket: WebSocket, call_sid: str):
    await websocket.accept()
    await websocket.send_json({"event": "connected", "call_sid": call_sid})
    try:
        while True:
            data = json.loads(await websocket.receive_text())
            decision = evaluate_lead_turn(data.get("transcript", ""))
            CRM_LEADS[call_sid] = {"call_sid": call_sid, **decision}
            await websocket.send_json({"event": "tts_dispatch", "call_sid": call_sid, "reply_text": decision["agent_reply"], "crm_sync": decision})
    except WebSocketDisconnect:
        pass

@app.get("/api/v1/crm/leads")
async def list_qualified_leads():
    return {"total": len(CRM_LEADS), "leads": CRM_LEADS}
