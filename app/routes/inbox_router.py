from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from fastapi import Query
from fastapi.responses import JSONResponse
from fastapi import Depends
from fastapi import status
from fastapi import Body
from sqlalchemy.orm import Session
from app.database import get_db
from uuid import uuid4
from app.models import inbox



inbox_route = APIRouter(
    prefix = '/inbox',
    tags = [ 'Inbox' ]
)

# POST Inbox
@inbox_route.post("/create_inbox")
def create_inbox(
    instance_id: str = Body(...),
    url_evo: str = Body(...),
    api_key: str = Body(...),
    whatsappjID: str = Body(...),
    inbox_name: str = Body(...),
    db: Session = Depends(get_db)
):
    try:
        inbox = inbox(
            inbox_id=str(uuid4()),
            instance_id=instance_id,
            url_evo=url_evo,
            api_key=api_key,
            whatsappjID=whatsappjID,
            inbox_name=inbox_name
        )
        db.add(inbox)
        db.commit()
        db.refresh(inbox)
        return JSONResponse(content={
            "status": "Success",
            "inbox": {
                "inbox_id": inbox.inbox_id,
                "instance_id": inbox.instance_id,
                "url_evo": inbox.url_evo,
                "api_key": inbox.api_key,
                "whatsappjID": inbox.whatsappjID,
                "inbox_name": inbox.inbox_name
            }
        })
    except Exception as e:
        db.rollback()
        return JSONResponse(content={"status": "Error", "details": str(e)})

# GET Inbox
@inbox_route.get("/")
def get_inbox(db: Session = Depends(get_db)):
    try:
        inboxes = db.query(inbox).all()
        result = [
            {
                "inbox_id": inbox.inbox_id,
                "instance_id": inbox.instance_id,
                "url_evo": inbox.url_evo,
                "api_key": inbox.api_key,
                "whatsappjID": inbox.whatsappjID,
                "inbox_name": inbox.inbox_name
            }
            for inbox in inboxes
        ]
        return JSONResponse(content={"status": "Success", "inboxes": result})
    except Exception as e:
        return JSONResponse(content={"status": "Error", "details": str(e)})

# DELETE Inbox
@inbox_route.delete("/{inbox_id}}")
def delete_inbox(inbox_id: str, db: Session = Depends(get_db)):
    try:
        inbox = db.query(inbox).filter(inbox.inbox_id == inbox_id).first()
        if not inbox:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"status": "Error", "details": "Inbox not found"}
            )
        db.delete(inbox)
        db.commit()
        return JSONResponse(content={"status": "Success", "message": f"Inbox {inbox_id} deleted"})
    except Exception as e:
        db.rollback()
        return JSONResponse(content={"status": "Error", "details": str(e)})
