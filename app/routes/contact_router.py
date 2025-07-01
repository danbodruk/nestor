from fastapi import APIRouter, Depends, Query, Body, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Contact

contact_route = APIRouter(prefix="/contacts", tags=["Contact"])

@contact_route.get("/")
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

@contact_route.post("/")
def create_contact(
    pushname: str = Body(...),
    WhatsappjId: str = Body(...),
    instanceId: str = Body(...),
    db: Session = Depends(get_db)
):
    try:
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

@contact_route.delete("/")
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
