"""Auth routes — Turnstile verification for magic link bot protection."""

import logging

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class TurnstileRequest(BaseModel):
    token: str


@router.post("/verify-turnstile")
async def verify_turnstile(body: TurnstileRequest, request: Request):
    """Verify a Cloudflare Turnstile token before sending a magic link."""
    settings = get_settings()
    if not settings.turnstile_secret_key:
        logger.warning("TURNSTILE_SECRET_KEY not set — Turnstile verification skipped")
        return {"success": True}

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data={
                "secret": settings.turnstile_secret_key,
                "response": body.token,
                "remoteip": request.client.host if request.client else None,
            },
        )
        result = resp.json()

    if not result.get("success"):
        raise HTTPException(status_code=403, detail="Verification failed")
    return {"success": True}
