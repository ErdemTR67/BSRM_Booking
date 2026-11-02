import argparse
from getpass import getpass
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.platform_role import PlatformRole, PlatformRoleName
from app.models.user import User
from app.schemas.user import validate_bcrypt_password


def create_platform_admin(args: argparse.Namespace) -> None:
    settings = get_settings()
    if settings.database_migration_url is None:
        raise SystemExit(
            "DATABASE_MIGRATION_URL is required for the privileged bootstrap command."
        )

    email = args.email.strip().lower()
    engine = create_engine(settings.database_migration_url, pool_pre_ping=True)
    try:
        with Session(engine) as session:
            user = session.scalar(select(User).where(User.email == email))
            if user is None:
                if not args.first_name or not args.last_name:
                    raise SystemExit(
                        "--first-name and --last-name are required for a new platform admin."
                    )
                password = getpass("Password: ")
                confirmation = getpass("Confirm password: ")
                if password != confirmation:
                    raise SystemExit("Passwords do not match.")
                if len(password) < 12:
                    raise SystemExit("Password must contain at least 12 characters.")
                try:
                    validate_bcrypt_password(password)
                except ValueError as error:
                    raise SystemExit(str(error)) from error
                user = User(
                    id=uuid4(),
                    email=email,
                    password_hash=hash_password(password),
                    first_name=args.first_name.strip(),
                    last_name=args.last_name.strip(),
                    is_active=True,
                )
                session.add(user)
                session.flush()
            elif not user.is_active:
                user.is_active = True

            platform_role = session.scalar(
                select(PlatformRole).where(PlatformRole.user_id == user.id)
            )
            if platform_role is None:
                session.add(
                    PlatformRole(
                        user_id=user.id,
                        role=PlatformRoleName.PLATFORM_ADMIN.value,
                        is_active=True,
                    )
                )
            else:
                platform_role.role = PlatformRoleName.PLATFORM_ADMIN.value
                platform_role.is_active = True
            session.commit()
    finally:
        engine.dispose()

    print(f"Platform admin ready: {email}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BSRM Booking operator commands")
    subparsers = parser.add_subparsers(dest="command", required=True)
    create_admin = subparsers.add_parser(
        "create-platform-admin",
        help="Create or promote a platform administrator using the migration connection.",
    )
    create_admin.add_argument("--email", required=True)
    create_admin.add_argument("--first-name")
    create_admin.add_argument("--last-name")
    create_admin.set_defaults(handler=create_platform_admin)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
