from fastapi import APIRouter

from app.api.v1 import (
    activities,
    agent,
    auth,
    avatar,
    chat,
    chunks,
    conversations,
    documents,
    figures,
    kb,
    models,
    photo,
    qa,
    training,
    users,
    voice,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(models.router)
api_router.include_router(photo.router)
api_router.include_router(conversations.router)
api_router.include_router(chat.router)
api_router.include_router(kb.router)
api_router.include_router(documents.router)
api_router.include_router(chunks.router)
api_router.include_router(qa.router)
api_router.include_router(training.router)
api_router.include_router(agent.router)
api_router.include_router(figures.router)
api_router.include_router(activities.router)
api_router.include_router(voice.router)
api_router.include_router(avatar.router)
