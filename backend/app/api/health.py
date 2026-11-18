from fastapi import APIRouter, Request

from app.core.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness, AI model and worker status")
def health(request: Request) -> dict:
    settings = get_settings()
    worker = getattr(request.app.state, "worker", None)
    return {
        "status": "ok",
        "embedding_model": settings.gemini_embedding_model,
        "chat_model": settings.gemini_chat_model,
        "worker_running": bool(worker and worker.running),
        "queue_depth": worker.queue_depth if worker else 0,
    }
