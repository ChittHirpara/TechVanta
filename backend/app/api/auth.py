"""Auth router – register, login, and /me endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.core.limiter import limiter
from app.core.security import create_access_token, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserRead
from app.services.user_service import create_user, get_user_by_username

router = APIRouter(prefix="/auth", tags=["Auth"])


# ── Local schemas ─────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def register(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    """
    Create a new user account.

    - **username**: 3–100 characters, must be unique.
    - **password**: minimum 8 characters (stored as bcrypt hash, never returned).
    - **role**: `admin` | `verifier` | `field_officer` (default: `field_officer`).
    """
    if await get_user_by_username(db, payload.username):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{payload.username}' is already taken.",
        )
    return await create_user(db, payload)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Exchange credentials for a JWT access token",
)
@limiter.limit("10/minute")
async def login(
    request: Request,                   # required by slowapi for IP key extraction
    response: Response,                 # required by slowapi for X-RateLimit-* headers
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Authenticate and receive a Bearer token.

    The token payload contains: `sub` (user id), `role`, `username`, `exp`.
    Pass it as `Authorization: Bearer <token>` on protected endpoints.
    """
    user = await get_user_by_username(db, payload.username)
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(
        subject=user.id,
        extra_claims={"role": user.role.value, "username": user.username},
    )
    return TokenResponse(access_token=token)


@router.get(
    "/me",
    response_model=UserRead,
    summary="Return the currently authenticated user",
)
async def me(current_user: User = Depends(get_current_user)) -> UserRead:
    """Requires a valid Bearer token. Returns the caller's profile."""
    return current_user
