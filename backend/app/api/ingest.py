import structlog
from fastapi import APIRouter, Depends, Response, status
from starlette.concurrency import run_in_threadpool

from app.api.deps import get_worker
from app.schemas.items import IngestRequest, ItemOut, ItemResponse
from app.services.ingestion import create_item
from app.workers.ingest_worker import IngestWorker

router = APIRouter(tags=["ingestion"])
log = structlog.get_logger("api.ingest")


@router.post(
    "/ingest",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ItemResponse,
    summary="Save a note or URL; indexing happens in the background",
    responses={422: {"description": "Invalid body"}, 503: {"description": "Ingestion worker unavailable"}},
)
async def ingest(body: IngestRequest, response: Response, worker: IngestWorker = Depends(get_worker)) -> ItemResponse:
    """Returns 202 with the item in `pending` status. Poll `GET /items/{id}` until it is `ready` or `failed`."""
    item = await run_in_threadpool(create_item, body)
    worker.enqueue(item.id)
    response.headers["Location"] = f"/items/{item.id}"
    log.info("item_accepted", item_id=item.id, source_type=item.source_type)
    return ItemResponse(item=ItemOut.from_domain(item))
