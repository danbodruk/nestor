from fastapi import (
    APIRouter,
    Depends,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime
import json

from app.database import get_db
from app.models import message, contact, image_message
from app.websocket_manager import connection_manager

message_route = APIRouter(tags=["Message"])
manager = connection_manager()


async def _broadcast(payload: dict) -> None:
    """Send a message to all connected websocket clients."""
    await manager.broadcast(json.dumps(payload))


def _update_contact(
    db: Session,
    whatsapp_id: str,
    pushname: str,
    from_me: bool,
    instance_id: str,
    contact_id: str,
) -> None:
    """Create or update a contact based on the incoming message."""
    existing = db.query(contact).filter(contact.WhatsappjId == whatsapp_id).first()
    if existing:
        if not from_me:
            existing.pushname = pushname
            existing.updatedAt = datetime.now()
    else:
        new_contact = contact(
            contactId=contact_id,
            WhatsappjId=whatsapp_id,
            pushname=pushname if not from_me else None,
            instanceId=instance_id,
        )
        db.add(new_contact)


async def _handle_text_message(
    db: Session,
    *,
    instance_id: str,
    message_id: str,
    whatsapp_id: str,
    message_type: str,
    pushname: str,
    datetime_obj: datetime,
    content: str,
) -> None:
    msg = message(
        messageId=message_id,
        datetime=datetime_obj,
        WhatsappjId=whatsapp_id,
        Message_Type=message_type,
        Message_Content=content,
        instanceId=instance_id,
    )
    db.add(msg)
    await _broadcast(
        {
            "messageId": message_id,
            "WhatsappjId": whatsapp_id,
            "Message_Type": message_type,
            "Message_Content": content,
            "contact": pushname,
            "datetime": datetime_obj.isoformat(),
        }
    )


async def _handle_image_message(
    db: Session,
    *,
    instance_id: str,
    message_id: str,
    whatsapp_id: str,
    message_type: str,
    pushname: str,
    datetime_obj: datetime,
    img_data: dict,
) -> None:
    img_msg = image_message(
        id=message_id,
        messageId=message_id,
        WhatsappjId=whatsapp_id,
        instanceId=instance_id,
        datetime=datetime_obj,
        url=img_data.get("url"),
        mimetype=img_data.get("mimetype"),
        caption=img_data.get("caption"),
        fileSha256=img_data.get("fileSha256"),
        fileLength=img_data.get("fileLength"),
        height=img_data.get("height"),
        width=img_data.get("width"),
        mediaKey=img_data.get("mediaKey"),
        fileEncSha256=img_data.get("fileEncSha256"),
        Message_Type=message_type,
    )
    db.add(img_msg)
    await _broadcast(
        {
            "messageId": message_id,
            "WhatsappjId": whatsapp_id,
            "Message_Type": message_type,
            "Image_URL": img_data.get("url"),
            "contact": pushname,
            "datetime": datetime_obj.isoformat(),
        }
    )

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
            db.query(message)
            .filter(
                message.instanceId == instanceId,
                message.WhatsappjId == whatsapp_id
            )
            .order_by(message.datetime.asc())
            .all()
        )
        image_messages = (
            db.query(image_message)
            .filter(
                image_message.instanceId == instanceId,
                image_message.WhatsappjId == whatsapp_id
            )
            .order_by(image_message.datetime.asc())
            .all()
        )
        all_messages = []
        for msg in text_messages:
            contact = db.query(contact).filter(contact.WhatsappjId == msg.WhatsappjId).first()
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
            contact = db.query(contact).filter(contact.WhatsappjId == img.WhatsappjId).first()
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
            content = message_data.get("conversation", "")
            await _handle_text_message(
                db,
                instance_id=instanceId,
                message_id=messageId,
                whatsapp_id=WhatsappjId,
                message_type=Message_Type,
                pushname=pushname,
                datetime_obj=datetime_obj,
                content=content,
            )
        elif "imageMessage" in message_data:
            await _handle_image_message(
                db,
                instance_id=instanceId,
                message_id=messageId,
                whatsapp_id=WhatsappjId,
                message_type=Message_Type,
                pushname=pushname,
                datetime_obj=datetime_obj,
                img_data=message_data.get("imageMessage", {}),
            )

        _update_contact(
            db,
            whatsapp_id=WhatsappjId,
            pushname=pushname,
            from_me=fromMe,
            instance_id=instanceId,
            contact_id=messageId,
        )
        db.commit()
        return {"status": "success"}
    except IntegrityError as e:
        db.rollback()
        return {"status": "error", "details": str(e)}
    except Exception as e:
        db.rollback()
        return {"status": "error", "details": str(e)}
