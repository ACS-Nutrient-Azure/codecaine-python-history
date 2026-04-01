import json
import asyncio
import logging
from datetime import date
from functools import partial

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.history import IntakeSupplement, IntakeItem
from app.schemas.history import (
    LOW_STOCK_THRESHOLD,
    SupplementOut,
    SupplementListResponse,
    SupplementRecord,
    DayRecord,
    RecordsResponse,
    RecordUpsertRequest,
)

logger = logging.getLogger(__name__)


def _put_low_stock_event(cognito_id: str, supplement_name: str, remaining: int) -> None:
    """AWS EventBridge에 재구매 알림 이벤트 발행 (동기, executor에서 호출)"""
    client = boto3.client("events", region_name="ap-northeast-2")
    client.put_events(
        Entries=[
            {
                "Source": "vitamin.history",
                "DetailType": "SupplementLowStock",
                "Detail": json.dumps({
                    "cognito_id": cognito_id,
                    "supplement_name": supplement_name,
                    "remaining": remaining,
                }),
                "EventBusName": "default",
            }
        ]
    )
    logger.info(f"EventBridge 발행: {supplement_name} 잔여 {remaining}회분 (user={cognito_id})")


async def _get_total_taken(db: AsyncSession, current_id: int) -> int:
    result = await db.execute(
        select(func.count(IntakeItem.item_id)).where(
            IntakeItem.current_id == current_id,
        )
    )
    return result.scalar() or 0


class RecordService:

    async def get_supplements(
        self, db: AsyncSession, cognito_id: str, is_active: bool | None
    ) -> SupplementListResponse:
        q = select(IntakeSupplement).where(IntakeSupplement.cognito_id == cognito_id)
        if is_active is not None:
            q = q.where(IntakeSupplement.is_active == is_active)
        result = await db.execute(q)
        supplements = result.scalars().all()

        # current_id 목록으로 복용 횟수 집계
        current_ids = [s.current_id for s in supplements]
        taken_map: dict[int, int] = {}
        if current_ids:
            count_result = await db.execute(
                select(IntakeItem.current_id, func.count(IntakeItem.item_id).label("total"))
                .where(IntakeItem.current_id.in_(current_ids))
                .group_by(IntakeItem.current_id)
            )
            taken_map = {row.current_id: row.total for row in count_result.all()}

        out = []
        for s in supplements:
            total_taken = taken_map.get(s.current_id, 0)
            remaining = (s.itk_total_quantity - total_taken) if s.itk_total_quantity is not None else None
            low_stock = remaining is not None and remaining <= LOW_STOCK_THRESHOLD
            out.append(SupplementOut(
                **{c.key: getattr(s, c.key) for c in s.__table__.columns},
                remaining_count=remaining,
                low_stock=low_stock,
            ))

        return SupplementListResponse(supplements=out)

    async def get_monthly_records(
        self, db: AsyncSession, cognito_id: str, year: int, month: int
    ) -> RecordsResponse:
        supp_result = await db.execute(
            select(IntakeSupplement).where(
                IntakeSupplement.cognito_id == cognito_id,
                IntakeSupplement.is_active == True,
            )
        )
        supplements = {s.current_id: s for s in supp_result.scalars().all()}

        if not supplements:
            return RecordsResponse(year=year, month=month, records=[])

        count_result = await db.execute(
            select(
                IntakeItem.current_id,
                IntakeItem.intake_dt,
                func.count(IntakeItem.item_id).label("taken_count"),
            )
            .where(
                IntakeItem.current_id.in_(list(supplements.keys())),
                func.extract("year", IntakeItem.intake_dt) == year,
                func.extract("month", IntakeItem.intake_dt) == month,
            )
            .group_by(IntakeItem.current_id, IntakeItem.intake_dt)
        )

        day_map: dict[str, list[SupplementRecord]] = {}
        for row in count_result.all():
            date_key = row.intake_dt.strftime("%Y-%m-%d")
            s = supplements.get(row.current_id)
            day_map.setdefault(date_key, []).append(
                SupplementRecord(
                    current_id=row.current_id,
                    product_name=s.itk_product_name if s else None,
                    taken_count=row.taken_count,
                    daily_limit=s.itk_serving_per_day if s else None,
                )
            )

        records = [DayRecord(date=d, supplements=supps) for d, supps in sorted(day_map.items())]
        return RecordsResponse(year=year, month=month, records=records)

    async def upsert_record(self, db: AsyncSession, req: RecordUpsertRequest) -> None:
        """taken_count에 맞게 intake_item row 수 동기화."""
        current_count_result = await db.execute(
            select(func.count(IntakeItem.item_id)).where(
                IntakeItem.current_id == req.current_id,
                IntakeItem.intake_dt == req.date,
            )
        )
        current_count = current_count_result.scalar() or 0
        diff = req.taken_count - current_count

        before_total_taken = None
        if diff > 0:
            before_total_taken = await _get_total_taken(db, req.current_id)

        if diff > 0:
            for _ in range(diff):
                db.add(IntakeItem(
                    current_id=req.current_id,
                    intake_dt=req.date,
                ))
        elif diff < 0:
            rows_to_delete = await db.execute(
                select(IntakeItem.item_id).where(
                    IntakeItem.current_id == req.current_id,
                    IntakeItem.intake_dt == req.date,
                ).order_by(IntakeItem.item_id.asc()).limit(-diff)
            )
            ids = [r[0] for r in rows_to_delete.all()]
            await db.execute(delete(IntakeItem).where(IntakeItem.item_id.in_(ids)))

        await db.commit()

        if diff > 0 and before_total_taken is not None:
            await self._check_low_stock(db, req, before_total_taken, before_total_taken + diff)

    async def _check_low_stock(
        self,
        db: AsyncSession,
        req: RecordUpsertRequest,
        before_taken: int,
        after_taken: int,
    ) -> None:
        supp_result = await db.execute(
            select(IntakeSupplement).where(IntakeSupplement.current_id == req.current_id)
        )
        supp = supp_result.scalar_one_or_none()
        if not supp or supp.itk_total_quantity is None:
            return

        total_qty = supp.itk_total_quantity
        remaining_before = total_qty - before_taken
        remaining_after = total_qty - after_taken

        if remaining_before > LOW_STOCK_THRESHOLD and remaining_after <= LOW_STOCK_THRESHOLD:
            try:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(
                    None,
                    partial(_put_low_stock_event, supp.cognito_id, supp.itk_product_name or "", remaining_after),
                )
            except (BotoCoreError, ClientError) as e:
                logger.warning(f"EventBridge 발행 실패 (무시됨): {e}")


record_service = RecordService()
