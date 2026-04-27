from fastapi import APIRouter, Depends, Request

from app.core.errors import ErrorCatalog, http_error

router = APIRouter(prefix="/protected", tags=["protected"])


@router.get("/me")
def me(request: Request):
    user = getattr(request.state, "user", None)
    if not user:
        raise http_error(401, ErrorCatalog.MISSING_TOKEN)
    return {
        "user_id": user.get("sub"),
        "email": user.get("email"),
        "user_type": user.get("user_type"),
    }