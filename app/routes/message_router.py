from fastapi import APIRouter, Depends, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime
import json

from app.database import get_db
from app.models import Message, Contact, ImageMessage
from app.websocket_manager import ConnectionManager

message_route = APIRouter(tags=["Message"])
manager = ConnectionManager()

@message_route.websocket("/ws/mensagens")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@message_route.get("/messages")
def get_messages(instanceId: str = Query(...), contact_number: str = Query(...), db: Session = Depends(get_db)):
    try:
        whatsapp_id = f"{contact_number}@s.whatsapp.net"
        text_messages = (
            db.query(Message)
            .filter(
                Message.instanceId == instanceId,
                Message.WhatsappjId == whatsapp_id
            )
            .order_by(Message.datetime.asc())
            .all()
        )
        image_messages = (
            db.query(ImageMessage)
            .filter(
                ImageMessage.instanceId == instanceId,
                ImageMessage.WhatsappjId == whatsapp_id
            )
            .order_by(ImageMessage.datetime.asc())
            .all()
        )
        all_messages = []
        for msg in text_messages:
            contact = db.query(Contact).filter(Contact.WhatsappjId == msg.WhatsappjId).first()
            all_messages.append({
                "type": "text",
                "messageId": msg.messageId,
                "WhatsappjId": msg.WhatsappjId,
                "Message_Type": msg.Message_Type,
                "Message_Content": msg.Message_Content,
                "contact": contact.pushname if contact else "",
                "datetime": msg.datetime.isoformat()
            })
        for img in image_messages:
            contact = db.query(Contact).filter(Contact.WhatsappjId == img.WhatsappjId).first()
            all_messages.append({
                "type": "image",
                "messageId": img.messageId,
                "WhatsappjId": img.WhatsappjId,
                "Message_Type": img.message_type,
                "image_url": img.url,
                "caption": img.caption,
                "contact": contact.pushname if contact else "",
                "datetime": img.datetime.isoformat(),
                "mimetype": img.mimetype,
                "height": img.height,
                "width": img.width
            })
        all_messages.sort(key=lambda x: x["datetime"])
        return JSONResponse(content={"status": "Success", "messages": all_messages})
    except Exception as e:
        return JSONResponse(content={"status": "Error", "details": str(e)})

@message_route.post("/webhook/mensagens")
async def webhook_mensagens(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    try:
        data_block = data.get('data', {})
        instanceId = data_block.get('instanceId')
        messageId = data_block.get('key', {}).get('id')
        WhatsappjId = data_block.get('key', {}).get('remoteJid')
        fromMe = data_block.get('key', {}).get('fromMe', False)
        Message_Type = "Outgoing" if fromMe else "Incoming"
        pushname = data_block.get('pushName')
        message_data = data_block.get('message', {})
        timestamp_unix = data_block.get('messageTimestamp')
        datetime_obj = datetime.fromtimestamp(timestamp_unix) if timestamp_unix else datetime.now()
        if "conversation" in message_data:
            Message_Content = message_data.get('conversation', '')
            await manager.broadcast(json.dumps({
                "messageId": messageId,
                "WhatsappjId": WhatsappjId,
                "Message_Type": Message_Type,
                "Message_Content": Message_Content,
                "contact": pushname,
                "datetime": datetime_obj.isoformat(),
            }))
            message = Message(
                messageId=messageId,
                datetime=datetime_obj,
                WhatsappjId=WhatsappjId,
                Message_Type=Message_Type,
                Message_Content=Message_Content,
                instanceId=instanceId
            )
            db.add(message)
        elif "imageMessage" in message_data:
            img = message_data.get('imageMessage', {})
            image_msg = ImageMessage(
                id=messageId,
                messageId=messageId,
                WhatsappjId=WhatsappjId,
                instanceId=instanceId,
                datetime=datetime_obj,
                url=img.get("url"),
                mimetype=img.get("mimetype"),
                caption=img.get("caption"),
                fileSha256=img.get("fileSha256"),
                fileLength=img.get("fileLength"),
                height=img.get("height"),
                width=img.get("width"),
                mediaKey=img.get("mediaKey"),
                fileEncSha256=img.get("fileEncSha256"),
                Message_Type=Message_Type
            )
            db.add(image_msg)
            await manager.broadcast(json.dumps({
                "messageId": messageId,
                "WhatsappjId": WhatsappjId,
                "Message_Type": Message_Type,
                "Image_URL": img.get("url"),
                "contact": pushname,
                "datetime": datetime_obj.isoformat(),
            }))
        existing_contact = db.query(Contact).filter(Contact.WhatsappjId == WhatsappjId).first()
        if existing_contact:
            if not fromMe:
                existing_contact.pushname = pushname
                existing_contact.updatedAt = datetime.now()
        else:
            contact = Contact(
                contactId=messageId,
                WhatsappjId=WhatsappjId,
                pushname=pushname if not fromMe else None,
                instanceId=instanceId
            )
            db.add(contact)
        db.commit()
        return {"status": "success"}
    except IntegrityError as e:
        db.rollback()
        return {"status": "error", "details": str(e)}
    except Exception as e:
        db.rollback()
        return {"status": "error", "details": str(e)}
