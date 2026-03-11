"""Router for authentication — login endpoint."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services.auth import verify_credentials, create_token

router = APIRouter()


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    token: str
    email: str


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest) -> LoginResponse:
    if not verify_credentials(body.email, body.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_token(body.email)
    return LoginResponse(token=token, email=body.email)


@router.get("/verify")
async def verify_token_endpoint():
    """Called by frontend to check if token is still valid.
    The auth middleware handles the actual verification — if we
    reach this handler the token is good."""
    return {"valid": True}
