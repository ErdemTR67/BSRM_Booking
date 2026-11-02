from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.dependencies.auth import CurrentUser
from app.core.database import get_database_session
from app.schemas.auth import RefreshTokenRequest, TokenResponse
from app.schemas.membership import MembershipResponse
from app.schemas.platform import InvitationAcceptRequest, InvitationTokenRequest
from app.schemas.user import UserResponse
from app.services.invitation import InvitationService
from app.services.auth import AuthService


router = APIRouter(prefix="/auth", tags=["Authentication"])


def get_auth_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> AuthService:
    return AuthService(session)


def get_invitation_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> InvitationService:
    return InvitationService(session)


@router.post(
    "/invitations/accept",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def accept_invitation(
    payload: InvitationAcceptRequest,
    service: Annotated[InvitationService, Depends(get_invitation_service)],
) -> UserResponse:
    return UserResponse.model_validate(service.accept_new_user(payload))


@router.post(
    "/invitations/accept-existing",
    response_model=MembershipResponse,
)
def accept_invitation_for_existing_user(
    payload: InvitationTokenRequest,
    current_user: CurrentUser,
    service: Annotated[InvitationService, Depends(get_invitation_service)],
) -> MembershipResponse:
    membership = service.accept_existing_user(payload.token, current_user)
    return MembershipResponse.model_validate(membership)


@router.post("/login", response_model=TokenResponse)
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    tokens = service.login(email=form.username, password=form.password)
    return TokenResponse.model_validate(tokens, from_attributes=True)


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    payload: RefreshTokenRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    tokens = service.refresh(payload.refresh_token)
    return TokenResponse.model_validate(tokens, from_attributes=True)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    payload: RefreshTokenRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> Response:
    service.logout(payload.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(current_user)
