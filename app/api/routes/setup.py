from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies.tenant import HeaderTenantContext
from app.core.database import get_database_session
from app.schemas.setup import SetupStatusResponse
from app.services.setup import SetupService


router = APIRouter(prefix="/setup", tags=["Setup"])


def get_setup_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> SetupService:
    return SetupService(session)


@router.get("/status", response_model=SetupStatusResponse)
def get_setup_status(
    context: HeaderTenantContext,
    service: Annotated[SetupService, Depends(get_setup_service)],
) -> SetupStatusResponse:
    return service.get_status(context)
