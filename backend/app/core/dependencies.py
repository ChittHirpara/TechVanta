"""Reusable FastAPI dependencies for auth and role-gating."""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User, UserRole

# tokenUrl is used only by the OpenAPI /docs UI "Authorize" button
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Decode the Bearer JWT and return the matching User row.

    Raises 401 if the token is missing, invalid, expired, or the user
    no longer exists in the database.
    """
    # Import here to avoid circular imports at module load time
    from app.services.user_service import get_user_by_id

    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(token)
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_exc
    except JWTError:
        raise credentials_exc

    user = await get_user_by_id(db, int(user_id))
    if user is None:
        raise credentials_exc

    return user


def require_role(*roles: UserRole):
    """
    Dependency factory that restricts access to the given roles.

    Usage::

        @router.delete("/users/{id}", dependencies=[Depends(require_role(UserRole.admin))])
        async def delete_user(...): ...

        # Or inject the user at the same time:
        @router.get("/dashboard")
        async def dashboard(user: User = Depends(require_role(UserRole.admin, UserRole.verifier))):
            ...
    """
    async def _check(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Role '{current_user.role.value}' is not permitted. "
                    f"Required one of: {[r.value for r in roles]}"
                ),
            )
        return current_user

    return _check
