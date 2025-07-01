from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models import message, contact

conversation_route = APIRouter(tags=["Conversation"])

@conversation_route.get("/conversations")
def get_conversations(instanceId: str = Query(...), db: Session = Depends(get_db)):
    try:
        contacts = db.query(contact).filter(contact.instanceId == instanceId).all()
        conversations = []
        for contact in contacts:
            last_message = (
                db.query(message)
                .filter(message.WhatsappjId == contact.WhatsappjId)
                .order_by(desc(message.datetime))
                .first()
            )
            if last_message:
                conversations.append({
                    "contact_name": contact.pushname,
                    "contact_number": contact.WhatsappjId.replace("@s.whatsapp.net", ""),
                    "last_message": last_message.Message_Content,
                    "last_update": last_message.datetime.strftime("%Y-%m-%d %H:%M:%S")
                })
        return JSONResponse(content={"status": "Success", "conversations": conversations})
    except Exception as e:
        return JSONResponse(content={"status": "Error", "details": str(e)})
