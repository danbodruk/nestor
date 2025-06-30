from sqlalchemy import Column, String, Integer, DateTime
from sqlalchemy.sql import func
from .database import Base

class Inbox(Base):
    __tablename__ = "inbox"

    inbox_id = Column(String, primary_key=True, index=True)
    instance_id = Column(String, index=True)
    url_evo = Column(String, nullable=False)
    api_key = Column(String, nullable=False)
    whatsappjID = Column(String, nullable=False)
    inbox_name = Column(String, nullable=False)

class Message(Base):
    __tablename__ = "message"

    messageId = Column(String, primary_key=True, index=True)
    datetime = Column(DateTime, nullable=False)
    WhatsappjId = Column(String, index=True, nullable=False)
    Message_Type = Column(String, nullable=False)
    Message_Content = Column(String, nullable=True)
    instanceId = Column(String, nullable=False)

class ImageMessage(Base):
    __tablename__ = "image_message"
    id = Column(String, primary_key=True, index=True)
    messageId = Column(String, index=True)
    WhatsappjId = Column(String, index=True)
    instanceId = Column(String, index=True)
    datetime = Column(DateTime, nullable=False)
    url = Column(String, nullable=False)
    mimetype = Column(String)
    caption = Column(String)
    fileSha256 = Column(String)
    fileLength = Column(String)
    height = Column(Integer)
    width = Column(Integer)
    mediaKey = Column(String)
    fileEncSha256 = Column(String)
    Message_Type = Column(String, nullable=False)




class Contact(Base):
    __tablename__ = "contact"

    contactId = Column(String, primary_key=True, index=True)
    WhatsappjId = Column(String, unique=True, index=True, nullable=False)
    pushname = Column(String, nullable=True)
    instanceId = Column(String, nullable=False)
    createdAt = Column(DateTime(timezone=True), server_default=func.now())
    updatedAt = Column(DateTime(timezone=True), onupdate=func.now())