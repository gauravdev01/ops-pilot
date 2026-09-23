from app.domain import ChildService
from fastapi import APIRouter, Depends

from app.models import ItemRequest, ItemResponse

router = APIRouter()


def get_service() -> ChildService:
    return ChildService()


@router.post("/items", response_model=ItemResponse)
def create_item(
    request: ItemRequest,
    service: ChildService = Depends(get_service),  # noqa: B008
) -> ItemResponse:
    return ItemResponse()
