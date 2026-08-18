from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, List
from zoneinfo import ZoneInfo

async def calculate_monthly_revenue(property_id: str, tenant_id: str, month: int, year: int, db_session=None) -> Decimal:
    """
    Calculates revenue for a specific month, in the property's local time zone.
    """
    from sqlalchemy import text

    async def _run(session):
        # check_in_date is timestamptz, so the month boundaries have to be
        # timezone-aware too - a naive boundary is read as UTC and shifts
        # bookings into the neighbouring month for non-UTC properties.
        tz_row = (await session.execute(
            text("SELECT timezone FROM properties WHERE id = :property_id AND tenant_id = :tenant_id"),
            {"property_id": property_id, "tenant_id": tenant_id},
        )).fetchone()

        tz = ZoneInfo(tz_row.timezone if tz_row else "UTC")

        start_date = datetime(year, month, 1, tzinfo=tz)
        if month < 12:
            end_date = datetime(year, month + 1, 1, tzinfo=tz)
        else:
            end_date = datetime(year + 1, 1, 1, tzinfo=tz)

        print(f"DEBUG: Querying revenue for {property_id} from {start_date} to {end_date}")

        query = text("""
            SELECT SUM(total_amount) as total
            FROM reservations
            WHERE property_id = :property_id
            AND tenant_id = :tenant_id
            AND check_in_date >= :start_date
            AND check_in_date < :end_date
        """)

        row = (await session.execute(query, {
            "property_id": property_id,
            "tenant_id": tenant_id,
            "start_date": start_date,
            "end_date": end_date,
        })).fetchone()

        return Decimal(str(row.total)) if row and row.total is not None else Decimal('0')

    if db_session is not None:
        return await _run(db_session)

    from app.core.database_pool import DatabasePool

    db_pool = DatabasePool()
    await db_pool.initialize()

    if not db_pool.session_factory:
        raise Exception("Database pool not available")

    async with db_pool.get_session() as session:
        return await _run(session)

async def calculate_total_revenue(property_id: str, tenant_id: str) -> Dict[str, Any]:
    """
    Aggregates revenue from database.
    """
    try:
        # Import database pool
        from app.core.database_pool import DatabasePool
        
        # Initialize pool if needed
        db_pool = DatabasePool()
        await db_pool.initialize()
        
        if db_pool.session_factory:
            async with db_pool.get_session() as session:
                # Use SQLAlchemy text for raw SQL
                from sqlalchemy import text
                
                query = text("""
                    SELECT 
                        property_id,
                        SUM(total_amount) as total_revenue,
                        COUNT(*) as reservation_count
                    FROM reservations 
                    WHERE property_id = :property_id AND tenant_id = :tenant_id
                    GROUP BY property_id
                """)
                
                result = await session.execute(query, {
                    "property_id": property_id, 
                    "tenant_id": tenant_id
                })
                row = result.fetchone()
                
                if row:
                    total_revenue = Decimal(str(row.total_revenue))
                    return {
                        "property_id": property_id,
                        "tenant_id": tenant_id,
                        "total": str(total_revenue),
                        "currency": "USD", 
                        "count": row.reservation_count
                    }
                else:
                    # No reservations found for this property
                    return {
                        "property_id": property_id,
                        "tenant_id": tenant_id,
                        "total": "0.00",
                        "currency": "USD",
                        "count": 0
                    }
        else:
            raise Exception("Database pool not available")
            
    except Exception as e:
        # Never substitute fabricated figures for real revenue: a reporting
        # error is recoverable, a plausible wrong number on a board deck is not.
        print(f"Database error for {property_id} (tenant: {tenant_id}): {e}")
        raise
