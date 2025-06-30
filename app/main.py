from fastapi import FastAPI, Request
from fastapi import Query
from fastapi.responses import JSONResponse
from fastapi import Depends
from fastapi import status
from fastapi import Body
from sqlalchemy.orm import Session
from .database import SessionLocal, engine, Base, get_db
from datetime import datetime, timedelta
from .models import Message, Contact
from .models import Inbox
from .models import ImageMessage
from sqlalchemy.exc import IntegrityError
from sqlalchemy import desc
from sqlalchemy import func
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from .websocket_manager import ConnectionManager
from uuid import uuid4
import json
import uvicorn
from app.routes.inbox_router import inbox_route
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from datetime import datetime, timedelta

tags_metadata = [
    {
        "name": "Inbox",
        "description": "Endpoints relacionados à caixa de entrada (Inbox)."
    },
    {
        "name": "Conversation",
        "description": "Endpoints de conversas e agrupamentos."
    },
    {
        "name": "Message",
        "description": "Endpoints de mensagens individuais."
    },
    {
        "name": "Contact",
        "description": "Endpoints de contatos."
    },
    {
        "name": "Dashboard",
        "description": "Endpoints de dashboard."
    },
]


Base.metadata.create_all(bind=engine)

# Manager da API
app = FastAPI(openapi_tags=tags_metadata)

# Cors
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Manager Global do Websocket
manager = ConnectionManager()

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

# Message Websocket
@app.websocket("/ws/mensagens")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # Opcional: Pode ouvir mensagens do frontend, se quiser.
    except WebSocketDisconnect:
        manager.disconnect(websocket)

##############################
# INBOX
app.include_router(inbox_route)

# GET Conversations
@app.get("/conversations", tags=["Conversation"])
def get_conversations(instanceId: str = Query(...), db: Session = Depends(get_db)):
    try:
        contacts = db.query(Contact).filter(Contact.instanceId == instanceId).all()
        conversations = []
        for contact in contacts:
            last_message = (
                db.query(Message)
                .filter(Message.WhatsappjId == contact.WhatsappjId)
                .order_by(desc(Message.datetime))
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

# GET Messages
@app.get("/messages", tags=["Message"])
def get_messages(instanceId: str = Query(...), contact_number: str = Query(...), db: Session = Depends(get_db)):
    try:
        whatsapp_id = f"{contact_number}@s.whatsapp.net"

        # Busca mensagens de texto
        text_messages = (
            db.query(Message)
            .filter(
                Message.instanceId == instanceId,
                Message.WhatsappjId == whatsapp_id
            )
            .order_by(Message.datetime.asc())
            .all()
        )

        # Busca mensagens de imagem
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

        # Adiciona mensagens de texto
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

        # Adiciona mensagens de imagem
        for img in image_messages:
            contact = db.query(Contact).filter(Contact.WhatsappjId == img.WhatsappjId).first()
            all_messages.append({
                "type": "image",
                "messageId": img.messageId,
                "WhatsappjId": img.WhatsappjId,
                "Message_Type": img.message_type,  # snake_case!
                "image_url": img.url,
                "caption": img.caption,
                "contact": contact.pushname if contact else "",
                "datetime": img.datetime.isoformat(),
                "mimetype": img.mimetype,
                "height": img.height,
                "width": img.width
            })

        # Ordena tudo por data/hora
        all_messages.sort(key=lambda x: x["datetime"])

        return JSONResponse(content={"status": "Success", "messages": all_messages})
    except Exception as e:
        return JSONResponse(content={"status": "Error", "details": str(e)})

# POST Messages + Images
@app.post("/webhook/mensagens", tags=["Message"])
async def webhook_mensagens(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    try:
        event_type = data.get('event')
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

        # Caso mensagem de texto
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
        # Caso mensagem de imagem
        elif "imageMessage" in message_data:
            img = message_data.get('imageMessage', {})
            image_msg = ImageMessage(
                id=messageId,  # ou use uuid4()
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
        # Pode adicionar outros tipos (audioMessage, videoMessage etc) aqui

        # Atualização do contato (igual seu código)
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
        print(f"Erro ao processar webhook: {e}")
        return {"status": "error", "details": str(e)}



    db = SessionLocal()
    data = await request.json()

    try:
        # Parse do JSON da Evolution
        event_type = data.get('event')
        data_block = data.get('data', {})
        instanceId = data_block.get('instanceId')

        messageId = data_block.get('key', {}).get('id')
        WhatsappjId = data_block.get('key', {}).get('remoteJid')
        fromMe = data_block.get('key', {}).get('fromMe', False)
        Message_Type = "Outgoing" if fromMe else "Incoming"
        pushname = data_block.get('pushName')
        Message_Content = data_block.get('message', {}).get('conversation', '')
        timestamp_unix = data_block.get('messageTimestamp')
        datetime_obj = datetime.fromtimestamp(timestamp_unix) if timestamp_unix else datetime.now()

        # Broadcast via WebSocket
        await manager.broadcast(json.dumps({
            "messageId": messageId,
            "WhatsappjId": WhatsappjId,
            "Message_Type": Message_Type,
            "Message_Content": Message_Content,
            "contact": pushname,
            "datetime": datetime_obj.isoformat(),
        }))

        # Salvar a mensagem
        message = Message(
            messageId=messageId,
            datetime=datetime_obj,
            WhatsappjId=WhatsappjId,
            Message_Type=Message_Type,
            Message_Content=Message_Content,
            instanceId=instanceId
        )
        db.add(message)

        # Criar ou atualizar o contato
        existing_contact = db.query(Contact).filter(Contact.WhatsappjId == WhatsappjId).first()
        if existing_contact:
            # Se for mensagem recebida (Incoming), atualiza o nome
            if not fromMe:
                existing_contact.pushname = pushname
                existing_contact.updatedAt = datetime.now()
        else:
            # Se for novo contato, cria
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
        print(f"Erro ao processar webhook: {e}")
        return {"status": "error", "details": str(e)}

    finally:
        db.close()

# GET Contact
@app.get("/contacts", tags=["Contact"])
def get_contacts(instanceId: str = Query(...), db: Session = Depends(get_db)):
    try:
        contacts = db.query(Contact).filter(Contact.instanceId == instanceId).all()
        result = [
            {
                "contactId": contact.contactId,
                "WhatsappjId": contact.WhatsappjId,
                "pushname": contact.pushname,
                "instanceId": contact.instanceId,
                "createdAt": contact.createdAt.isoformat() if contact.createdAt else None,
                "updatedAt": contact.updatedAt.isoformat() if contact.updatedAt else None
            }
            for contact in contacts
        ]
        return JSONResponse(content={"status": "Success", "contacts": result})
    except Exception as e:
        return JSONResponse(content={"status": "Error", "details": str(e)})
    
# POST Contact
@app.post("/contacts", tags=["Contact"])
def create_contact(
    pushname: str = Body(...), 
    WhatsappjId: str = Body(...), 
    instanceId: str = Body(...), 
    db: Session = Depends(get_db)
):
    try:
        # Checar se já existe
        exists = db.query(Contact).filter(Contact.WhatsappjId == WhatsappjId, Contact.instanceId == instanceId).first()
        if exists:
            return JSONResponse(content={"status": "Error", "details": "Contact already exists"})
        
        import uuid
        contact = Contact(
            contactId=str(uuid.uuid4()),
            pushname=pushname,
            WhatsappjId=WhatsappjId,
            instanceId=instanceId
        )
        db.add(contact)
        db.commit()
        db.refresh(contact)
        return JSONResponse(content={
            "status": "Success", 
            "contact": {
                "contactId": contact.contactId,
                "pushname": contact.pushname,
                "WhatsappjId": contact.WhatsappjId,
                "instanceId": contact.instanceId,
                "createdAt": contact.createdAt.isoformat() if contact.createdAt else None
            }
        })
    except Exception as e:
        db.rollback()
        return JSONResponse(content={"status": "Error", "details": str(e)})

# DELETE Contact
@app.delete("/contacts", tags=["Contact"])
def delete_contact(contactId: str = Query(...), db: Session = Depends(get_db)):
    try:
        contact = db.query(Contact).filter(Contact.contactId == contactId).first()
        if not contact:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"status": "Error", "details": "Contact not found"}
            )
        db.delete(contact)
        db.commit()
        return JSONResponse(content={"status": "Success", "message": f"Contact {contactId} deleted"})
    except Exception as e:
        db.rollback()
        return JSONResponse(content={"status": "Error", "details": str(e)})

# GET Dashboard
@app.get("/dashboard_info", tags=["Dashboard"])
def get_dashboard_info(db: Session = Depends(get_db)):
    today = datetime.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    # Mensagens enviadas
    sent_today = db.query(func.count()).filter(
        Message.Message_Type == "Outgoing",
        func.date(Message.datetime) == today
    ).scalar()
    sent_week = db.query(func.count()).filter(
        Message.Message_Type == "Outgoing",
        func.date(Message.datetime) >= week_ago
    ).scalar()
    sent_month = db.query(func.count()).filter(
        Message.Message_Type == "Outgoing",
        func.date(Message.datetime) >= month_ago
    ).scalar()

    # Mensagens recebidas
    received_today = db.query(func.count()).filter(
        Message.Message_Type == "Incoming",
        func.date(Message.datetime) == today
    ).scalar()
    received_week = db.query(func.count()).filter(
        Message.Message_Type == "Incoming",
        func.date(Message.datetime) >= week_ago
    ).scalar()
    received_month = db.query(func.count()).filter(
        Message.Message_Type == "Incoming",
        func.date(Message.datetime) >= month_ago
    ).scalar()

    # Contatos ativos (com pelo menos 1 mensagem)
    total_active_contacts = db.query(func.count(Contact.contactId)).scalar()

    # Contatos conversados (enviou ou recebeu mensagem)
    contacts_today = db.query(func.count(func.distinct(Message.WhatsappjId))).filter(
        func.date(Message.datetime) == today
    ).scalar()
    contacts_week = db.query(func.count(func.distinct(Message.WhatsappjId))).filter(
        func.date(Message.datetime) >= week_ago
    ).scalar()
    contacts_month = db.query(func.count(func.distinct(Message.WhatsappjId))).filter(
        func.date(Message.datetime) >= month_ago
    ).scalar()

    # Total de inboxes
    total_inboxes = db.query(func.count(Inbox.inbox_id)).scalar()

    return {
        "messages_sent": {
            "today": sent_today,
            "last_7_days": sent_week,
            "last_30_days": sent_month,
        },
        "messages_received": {
            "today": received_today,
            "last_7_days": received_week,
            "last_30_days": received_month,
        },
        "contacts": {
            "active": total_active_contacts,
            "talked_today": contacts_today,
            "talked_last_7_days": contacts_week,
            "talked_last_30_days": contacts_month
        },
        "total_inboxes": total_inboxes
    }

@app.get("/dashboard_time", tags=["Dashboard"])
def get_dashboard_info(db: Session = Depends(get_db)):
    today = datetime.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    # Mensagens enviadas
    sent_today = db.query(func.count()).filter(
        Message.Message_Type == "Outgoing",
        func.date(Message.datetime) == today
    ).scalar()

    sent_week = db.query(func.count()).filter(
        Message.Message_Type == "Outgoing",
        func.date(Message.datetime) >= week_ago
    ).scalar()

    sent_month = db.query(func.count()).filter(
        Message.Message_Type == "Outgoing",
        func.date(Message.datetime) >= month_ago
    ).scalar()

    # Mensagens recebidas
    received_today = db.query(func.count()).filter(
        Message.Message_Type == "Incoming",
        func.date(Message.datetime) == today
    ).scalar()

    received_week = db.query(func.count()).filter(
        Message.Message_Type == "Incoming",
        func.date(Message.datetime) >= week_ago
    ).scalar()

    received_month = db.query(func.count()).filter(
        Message.Message_Type == "Incoming",
        func.date(Message.datetime) >= month_ago
    ).scalar()

    # Contatos ativos (com pelo menos 1 mensagem)
    total_active_contacts = db.query(func.count(Contact.contactId)).scalar()

    # Contatos conversados
    contacts_today = db.query(func.count(func.distinct(Message.WhatsappjId))).filter(
        func.date(Message.datetime) == today
    ).scalar()

    contacts_week = db.query(func.count(func.distinct(Message.WhatsappjId))).filter(
        func.date(Message.datetime) >= week_ago
    ).scalar()

    contacts_month = db.query(func.count(func.distinct(Message.WhatsappjId))).filter(
        func.date(Message.datetime) >= month_ago
    ).scalar()

    # Total de inboxes
    total_inboxes = db.query(func.count(Inbox.inbox_id)).scalar()

    # Volume de mensagens por hora - enviados
    sent_by_hour_query = db.query(
        extract('hour', Message.datetime).label('hour'),
        func.count().label('count')
    ).filter(
        Message.Message_Type == "Outgoing",
        func.date(Message.datetime) == today
    ).group_by('hour').all()

    sent_by_hour = {f"time_{int(h)}": c for h, c in sent_by_hour_query}

    # Preencher horários faltantes com 0
    sent_by_time = []
    for hour in range(24):
        sent_by_time.append({f"time_{hour}": sent_by_hour.get(f"time_{hour}", 0)})

    # Volume de mensagens por hora - recebidos
    received_by_hour_query = db.query(
        extract('hour', Message.datetime).label('hour'),
        func.count().label('count')
    ).filter(
        Message.Message_Type == "Incoming",
        func.date(Message.datetime) == today
    ).group_by('hour').all()

    received_by_hour = {f"time_{int(h)}": c for h, c in received_by_hour_query}

    received_by_time = []
    for hour in range(24):
        received_by_time.append({f"time_{hour}": received_by_hour.get(f"time_{hour}", 0)})

    # Retorno final
    return {
        "messages_sent": {
            "today": sent_today,
            "last_7_days": sent_week,
            "last_30_days": sent_month,
            "sent_by_time": sent_by_time
        },
        "messages_received": {
            "today": received_today,
            "last_7_days": received_week,
            "last_30_days": received_month,
            "received_by_time": received_by_time
        },
        "contacts": {
            "active": total_active_contacts,
            "talked_today": contacts_today,
            "talked_last_7_days": contacts_week,
            "talked_last_30_days": contacts_month
        },
        "total_inboxes": total_inboxes
    }
