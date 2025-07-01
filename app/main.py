from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routes import (
    inbox_route,
    conversation_route,
    message_route,
    contact_route,
    dashboard_route,
)

Base.metadata.create_all(bind=engine)

tags_metadata = [
    {
        "name": "Inbox",
        "description": "Endpoints relacionados à caixa de entrada (Inbox).",
    },
    {
        "name": "Conversation",
        "description": "Endpoints de conversas e agrupamentos.",
    },
    {
        "name": "Message",
        "description": "Endpoints de mensagens individuais.",
    },
    {
        "name": "Contact",
        "description": "Endpoints de contatos.",
    },
    {
        "name": "Dashboard",
        "description": "Endpoints de dashboard.",
    },
]

app = FastAPI(openapi_tags=tags_metadata)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(inbox_route)
app.include_router(conversation_route)
app.include_router(message_route)
app.include_router(contact_route)
app.include_router(dashboard_route)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
