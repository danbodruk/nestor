from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from datetime import datetime, timedelta

from app.database import get_db
from app.models import message, contact, inbox


dashboard_route = APIRouter(tags=["Dashboard"])


def _base_dashboard_data(db: Session, today: datetime.date):
    """Return basic dashboard metrics used by multiple endpoints."""
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    sent_today = (
        db.query(func.count())
        .filter(message.Message_Type == "Outgoing", func.date(message.datetime) == today)
        .scalar()
    )
    sent_week = (
        db.query(func.count())
        .filter(message.Message_Type == "Outgoing", func.date(message.datetime) >= week_ago)
        .scalar()
    )
    sent_month = (
        db.query(func.count())
        .filter(message.Message_Type == "Outgoing", func.date(message.datetime) >= month_ago)
        .scalar()
    )

    received_today = (
        db.query(func.count())
        .filter(message.Message_Type == "Incoming", func.date(message.datetime) == today)
        .scalar()
    )
    received_week = (
        db.query(func.count())
        .filter(message.Message_Type == "Incoming", func.date(message.datetime) >= week_ago)
        .scalar()
    )
    received_month = (
        db.query(func.count())
        .filter(message.Message_Type == "Incoming", func.date(message.datetime) >= month_ago)
        .scalar()
    )

    total_active_contacts = db.query(func.count(contact.contactId)).scalar()
    contacts_today = (
        db.query(func.count(func.distinct(message.WhatsappjId)))
        .filter(func.date(message.datetime) == today)
        .scalar()
    )
    contacts_week = (
        db.query(func.count(func.distinct(message.WhatsappjId)))
        .filter(func.date(message.datetime) >= week_ago)
        .scalar()
    )
    contacts_month = (
        db.query(func.count(func.distinct(message.WhatsappjId)))
        .filter(func.date(message.datetime) >= month_ago)
        .scalar()
    )

    total_inboxes = db.query(func.count(inbox.inbox_id)).scalar()

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
            "talked_last_30_days": contacts_month,
        },
        "total_inboxes": total_inboxes,
    }

@dashboard_route.get("/dashboard_info")
def get_dashboard_info(db: Session = Depends(get_db)):
    today = datetime.now().date()
    return _base_dashboard_data(db, today)

@dashboard_route.get("/dashboard_time")
def get_dashboard_time(db: Session = Depends(get_db)):
    today = datetime.now().date()
    base_data = _base_dashboard_data(db, today)

    sent_by_hour_query = db.query(
        extract('hour', message.datetime).label('hour'),
        func.count().label('count')
    ).filter(
        message.Message_Type == "Outgoing",
        func.date(message.datetime) == today
    ).group_by('hour').all()
    sent_by_hour = {f"time_{int(h)}": c for h, c in sent_by_hour_query}
    sent_by_time = [{f"time_{h}": sent_by_hour.get(f"time_{h}", 0)} for h in range(24)]

    received_by_hour_query = db.query(
        extract('hour', message.datetime).label('hour'),
        func.count().label('count')
    ).filter(
        message.Message_Type == "Incoming",
        func.date(message.datetime) == today
    ).group_by('hour').all()
    received_by_hour = {f"time_{int(h)}": c for h, c in received_by_hour_query}
    received_by_time = [{f"time_{h}": received_by_hour.get(f"time_{h}", 0)} for h in range(24)]

    base_data["messages_sent"]["sent_by_time"] = sent_by_time
    base_data["messages_received"]["received_by_time"] = received_by_time
    return base_data
