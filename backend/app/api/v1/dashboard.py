from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from decimal import Decimal
from app.services.cache import get_revenue_summary
from app.core.auth import authenticate_request as get_current_user

router = APIRouter()

@router.get("/dashboard/summary")
async def get_dashboard_summary(
    property_id: str,
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    
    # Fail closed: a missing tenant must never fall back to a shared bucket.
    tenant_id = getattr(current_user, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=403, detail="No tenant associated with this user")

    revenue_data = await get_revenue_summary(property_id, tenant_id)
    
    # Money must not pass through binary float: NUMERIC(10,3) amounts are exact
    # decimals and are serialised as a string to survive the JSON round-trip.
    total_revenue = Decimal(revenue_data['total'])

    return {
        "property_id": revenue_data['property_id'],
        "total_revenue": str(total_revenue),
        "currency": revenue_data['currency'],
        "reservations_count": revenue_data['count']
    }
