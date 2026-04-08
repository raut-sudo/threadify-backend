"""
Repository layer for User and Role database operations.

Pure data-access — no business logic, no HTTP concerns. Every method
receives an AsyncSession and returns ORM model instances or None.
The service layer is responsible for orchestrating calls here.
"""

import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.role import Role
from app.models.user import User
from app.utils.constants import (
    DEFAULT_PAGE_LIMIT,
    DEFAULT_PAGE_SKIP,
    DEFAULT_ROLES,
    ROLE_ADMIN,
)

logger = logging.getLogger(__name__)


# ── Role Queries ────────────────────────────────────


async def get_role_by_name(db: AsyncSession, name: str) -> Role | None:
    """Fetch a single role by its unique name (e.g. 'MEMBER').

    Returns the Role ORM object or None if not found.
    """
    stmt = select(Role).where(Role.name == name)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def seed_default_roles(db: AsyncSession) -> list[Role]:
    """Insert the three default roles if they don't already exist.

    Intended for first-run or test setup. Skips any role whose
    name already appears in the table and returns all roles.
    """
    for name, description in DEFAULT_ROLES:
        existing = await get_role_by_name(db, name)
        if not existing:
            db.add(Role(name=name, description=description))
            logger.info("Seeded role: %s", name)

    await db.flush()
    result = await db.execute(select(Role))
    return list(result.scalars().all())


async def seed_admin_user(
    db: AsyncSession,
    *,
    username: str,
    email: str,
    password: str,
) -> User | None:
    """Create the single bootstrap admin user if they don't already exist.

    This is fully idempotent — if a user with the given username already
    exists, this function does nothing and returns None.  Should be called
    after seed_default_roles so the ADMIN role FK is resolvable.
    """
    from app.core.security import hash_password  # local import to avoid circular

    existing = await get_user_by_username(db, username)
    if existing:
        logger.info("Admin user '%s' already exists — skipping seed", username)
        return None

    admin_role = await get_role_by_name(db, ROLE_ADMIN)
    if admin_role is None:
        logger.error("ADMIN role not found — cannot seed admin user")
        return None

    user = User(
        username=username,
        email=email,
        hashed_password=hash_password(password),
        role_id=admin_role.id,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user, attribute_names=["role"])
    logger.info("Admin user '%s' seeded (id=%s)", username, user.id)
    return user


# ── User Queries ────────────────────────────────────


async def create_user(
    db: AsyncSession,
    *,
    username: str,
    email: str,
    hashed_password: str,
    role_id: uuid.UUID,
    bio: str | None = None,
    avatar_url: str | None = None,
) -> User:
    """Insert a new user row and return the persisted instance.

    Caller is responsible for hashing the password and resolving
    the role_id before calling this function.
    """
    user = User(
        username=username,
        email=email,
        hashed_password=hashed_password,
        role_id=role_id,
        bio=bio,
        avatar_url=avatar_url,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user, attribute_names=["role"])
    logger.info("User created: %s (id=%s)", username, user.id)
    return user


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    """Fetch a user by primary key with the role relationship loaded.

    Returns None if no user matches the given UUID.
    """
    stmt = select(User).options(joinedload(User.role)).where(User.id == user_id)
    result = await db.execute(stmt)
    return result.unique().scalar_one_or_none()


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    """Fetch a user by username (case-sensitive) with role loaded.

    Used during login to verify credentials.
    """
    stmt = select(User).options(joinedload(User.role)).where(User.username == username)
    result = await db.execute(stmt)
    return result.unique().scalar_one_or_none()


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Fetch a user by email address with role loaded.

    Used during registration to check for duplicates.
    """
    stmt = select(User).options(joinedload(User.role)).where(User.email == email)
    result = await db.execute(stmt)
    return result.unique().scalar_one_or_none()


async def list_users(
    db: AsyncSession,
    *,
    skip: int = DEFAULT_PAGE_SKIP,
    limit: int = DEFAULT_PAGE_LIMIT,
    role: str | None = None,
    search: str | None = None,
    deleted: bool | None = False,
) -> tuple[list[User], int]:
    """Return a paginated, filterable list of users and the total count.

    Filters:
        role:    Exact match on role name (e.g. 'MEMBER', 'MOD', 'ADMIN').
        search:  Case-insensitive substring match on username OR email.
        deleted: True = only banned, False = only active (default),
                 None = all users.
    """
    from sqlalchemy import or_

    # ── Build WHERE clauses ──────────────────────────
    conditions = []

    if deleted is not None:
        conditions.append(User.deleted == deleted)

    if role is not None:
        conditions.append(User.role.has(Role.name == role.upper()))

    if search is not None:
        pattern = f"%{search}%"
        conditions.append(
            or_(
                User.username.ilike(pattern),
                User.email.ilike(pattern),
            )
        )

    # ── Count query ──────────────────────────────────
    count_stmt = select(func.count()).select_from(User)
    for cond in conditions:
        count_stmt = count_stmt.where(cond)
    total = (await db.execute(count_stmt)).scalar() or 0

    # ── Data query ───────────────────────────────────
    stmt = (
        select(User)
        .options(joinedload(User.role))
        .order_by(User.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    for cond in conditions:
        stmt = stmt.where(cond)

    result = await db.execute(stmt)
    users = list(result.unique().scalars().all())
    return users, total


async def update_user(db: AsyncSession, user: User, **fields: object) -> User:
    """Apply a dict of field updates to an existing User instance.

    All values in `fields` are written — including None (used to
    clear nullable fields like bio and avatar_url).  The caller must
    have already validated / hashed any sensitive values.
    """
    for key, value in fields.items():
        setattr(user, key, value)

    await db.flush()
    await db.refresh(user, attribute_names=["role"])
    logger.debug("User updated: %s (fields=%s)", user.username, list(fields.keys()))
    return user


async def soft_delete_user(db: AsyncSession, user: User) -> User:
    """Soft-delete a user by setting deleted=True.

    The row stays for audit purposes; the user can no
    longer log in or refresh tokens.
    """
    user.deleted = True
    await db.flush()
    logger.info("User soft-deleted: %s", user.username)
    return user
