from fastapi import APIRouter, Query, Response, status

from app.core.db import get_connection
from app.core.errors import NotFoundError
from app.repositories import items_repo
from app.schemas.items import ItemListResponse, ItemOut, ItemResponse

router = APIRouter(prefix="/items", tags=["items"])

# Sync handlers: FastAPI runs them in a threadpool, so blocking SQLite calls don't stall the event loop.


@router.get("", response_model=ItemListResponse, summary="List saved items, newest first")
def list_items(limit: int = Query(default=100, ge=1, le=500)) -> ItemListResponse:
    with get_connection() as conn:
        items = items_repo.list_recent(conn, limit)
    return ItemListResponse(items=[ItemOut.from_domain(item) for item in items])


@router.get("/{item_id}", response_model=ItemResponse, summary="Get one item", responses={404: {"description": "Not found"}})
def get_item(item_id: str) -> ItemResponse:
    with get_connection() as conn:
        item = items_repo.get(conn, item_id)
    if item is None:
        raise NotFoundError(f"No item with id '{item_id}'.", code="ITEM_NOT_FOUND")
    return ItemResponse(item=ItemOut.from_domain(item))


@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an item and its chunks",
    responses={404: {"description": "Not found"}},
)
def delete_item(item_id: str) -> Response:
    with get_connection() as conn:
        deleted = items_repo.delete(conn, item_id)
    if not deleted:
        raise NotFoundError(f"No item with id '{item_id}'.", code="ITEM_NOT_FOUND")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
