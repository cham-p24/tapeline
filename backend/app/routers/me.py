"""GET /api/me — current user + subscription state."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.models import User
from app.services.auth import current_user_optional
from app.services.tier import FEATURES, Tier, has_feature, limit

router = APIRouter()


@router.get("")
async def me(user: User | None = Depends(current_user_optional)) -> dict:
    if user is None:
        return {
            "authenticated": False,
            "tier": "free",
            "features": {f: has_feature(Tier.FREE, f) for f in FEATURES},
            "limits": {
                "scanner_rows": limit(Tier.FREE, "scanner_rows"),
                "email_alerts_per_day": limit(Tier.FREE, "email_alerts_per_day"),
            },
        }
    tier = Tier(user.tier)
    return {
        "authenticated": True,
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "tier": user.tier,
        "features": {f: has_feature(tier, f) for f in FEATURES},
        "limits": {
            "scanner_rows": limit(tier, "scanner_rows"),
            "email_alerts_per_day": limit(tier, "email_alerts_per_day"),
            "api_requests_per_day": limit(tier, "api_requests_per_day"),
        },
    }
