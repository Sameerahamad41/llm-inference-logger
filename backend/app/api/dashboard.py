"""Dashboard analytics endpoints.

Provides aggregated metrics over inference logs: latency percentiles,
throughput, error rates, and breakdowns by provider/model.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.inference_log import InferenceLog
from app.schemas.conversation import DashboardStats, InferenceLogOut

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStats)
async def get_stats(
    hours: int = Query(default=24, ge=1, le=720, description="Lookback window in hours"),
    db: AsyncSession = Depends(get_db),
):
    """Return aggregated dashboard metrics for the given time window."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    base = select(InferenceLog).where(InferenceLog.created_at >= cutoff)

    # ── Scalar aggregates ─────────────────────────────────────────
    agg = await db.execute(
        select(
            func.count(InferenceLog.id).label("total"),
            func.count(
                case((InferenceLog.status == "success", 1))
            ).label("success"),
            func.count(
                case((InferenceLog.status != "success", 1))
            ).label("errors"),
            func.coalesce(func.avg(InferenceLog.latency_ms), 0).label("avg_latency"),
            func.coalesce(
                func.percentile_cont(0.95).within_group(InferenceLog.latency_ms), 0
            ).label("p95_latency"),
            func.coalesce(func.sum(InferenceLog.input_tokens), 0).label("in_tok"),
            func.coalesce(func.sum(InferenceLog.output_tokens), 0).label("out_tok"),
        ).where(InferenceLog.created_at >= cutoff)
    )
    row = agg.one()

    # ── Per-provider counts ───────────────────────────────────────
    prov_rows = await db.execute(
        select(InferenceLog.provider, func.count())
        .where(InferenceLog.created_at >= cutoff)
        .group_by(InferenceLog.provider)
    )
    requests_per_provider = {r[0]: r[1] for r in prov_rows.all()}

    # ── Per-model counts ──────────────────────────────────────────
    model_rows = await db.execute(
        select(InferenceLog.model, func.count())
        .where(InferenceLog.created_at >= cutoff)
        .group_by(InferenceLog.model)
    )
    requests_per_model = {r[0]: r[1] for r in model_rows.all()}

    # ── Errors per provider ───────────────────────────────────────
    err_rows = await db.execute(
        select(InferenceLog.provider, func.count())
        .where(
            InferenceLog.created_at >= cutoff,
            InferenceLog.status != "success",
        )
        .group_by(InferenceLog.provider)
    )
    errors_per_provider = {r[0]: r[1] for r in err_rows.all()}

    # ── Time series: latency ──────────────────────────────────────
    bucket = func.date_trunc("hour", InferenceLog.created_at)
    lat_rows = await db.execute(
        select(
            bucket.label("bucket"),
            func.avg(InferenceLog.latency_ms).label("avg"),
            func.percentile_cont(0.95)
            .within_group(InferenceLog.latency_ms)
            .label("p95"),
        )
        .where(InferenceLog.created_at >= cutoff)
        .group_by(bucket)
        .order_by(bucket)
    )
    latency_over_time = [
        {"time": str(r.bucket), "avg_ms": round(r.avg, 1), "p95_ms": round(r.p95, 1)}
        for r in lat_rows.all()
    ]

    # ── Time series: throughput ───────────────────────────────────
    thr_rows = await db.execute(
        select(bucket.label("bucket"), func.count().label("cnt"))
        .where(InferenceLog.created_at >= cutoff)
        .group_by(bucket)
        .order_by(bucket)
    )
    throughput_over_time = [
        {"time": str(r.bucket), "requests": r.cnt}
        for r in thr_rows.all()
    ]

    return DashboardStats(
        total_requests=row.total,
        success_count=row.success,
        error_count=row.errors,
        avg_latency_ms=round(float(row.avg_latency), 2),
        p95_latency_ms=round(float(row.p95_latency), 2),
        total_input_tokens=int(row.in_tok),
        total_output_tokens=int(row.out_tok),
        requests_per_provider=requests_per_provider,
        requests_per_model=requests_per_model,
        errors_per_provider=errors_per_provider,
        latency_over_time=latency_over_time,
        throughput_over_time=throughput_over_time,
    )


@router.get("/logs", response_model=list[InferenceLogOut])
async def list_logs(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    provider: str | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Return recent inference logs with optional filters."""
    query = select(InferenceLog).order_by(InferenceLog.created_at.desc())

    if provider:
        query = query.where(InferenceLog.provider == provider)
    if status:
        query = query.where(InferenceLog.status == status)

    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()
