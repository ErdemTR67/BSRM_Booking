from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.refresh_token import RefreshToken


class RefreshTokenRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_hash(
        self,
        token_hash: str,
        *,
        for_update: bool = False,
    ) -> RefreshToken | None:
        statement = select(RefreshToken).where(
            RefreshToken.token_hash == token_hash
        )

        if for_update:
            statement = statement.with_for_update()

        result = self.session.execute(statement)
        return result.scalar_one_or_none()

    def add(self, refresh_token: RefreshToken) -> RefreshToken:
        self.session.add(refresh_token)
        self.session.flush()
        return refresh_token
