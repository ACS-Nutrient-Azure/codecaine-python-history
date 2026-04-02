import logging
from sqlalchemy import select, func, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.history import IntakeSupplement, IntakeItem, PurchaseHistory
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


class RecordService:

    async def get_supplements(
        self, db: AsyncSession, cognito_id: str, is_active: bool | None
    ) -> SupplementListResponse:
        q = select(IntakeSupplement).where(IntakeSupplement.cognito_id == cognito_id)
        if is_active is not None:
            q = q.where(IntakeSupplement.is_active == is_active)
        result = await db.execute(q)
        supplements = result.scalars().all()

        out = []
        for s in supplements:
            low_stock = s.itk_total_quantity is not None and s.itk_total_quantity <= LOW_STOCK_THRESHOLD
            out.append(SupplementOut(
                **{c.key: getattr(s, c.key) for c in s.__table__.columns},
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
        """taken_count에 맞게 intake_item row 수 동기화 + itk_total_quantity 직접 차감 + purchase_history 동기화."""

        current_count_result = await db.execute(
            select(func.count(IntakeItem.item_id)).where(
                IntakeItem.current_id == req.current_id,
                IntakeItem.intake_dt == req.date,
            )
        )
        current_count = current_count_result.scalar() or 0
        diff = req.taken_count - current_count

        if diff == 0:
            return

        if diff > 0:
            new_items = []
            for _ in range(diff):
                item = IntakeItem(current_id=req.current_id, intake_dt=req.date)
                db.add(item)
                new_items.append(item)

            await db.flush()  # item_id 확보

            # purchase_history 동기화 (실패해도 메인 흐름에 영향 없음)
            try:
                ph_result = await db.execute(
                    select(PurchaseHistory)
                    .join(IntakeItem, PurchaseHistory.item_id == IntakeItem.item_id)
                    .where(IntakeItem.current_id == req.current_id)
                    .limit(1)
                )
                ph_row = ph_result.scalar_one_or_none()

                if ph_row:
                    ph_row.remain_day = max(0, (ph_row.remain_day or 0) - diff)
                else:
                    supp_result = await db.execute(
                        select(IntakeSupplement).where(IntakeSupplement.current_id == req.current_id)
                    )
                    supp = supp_result.scalar_one_or_none()

                    initial_remain_day = None
                    if supp and supp.itk_total_quantity is not None and supp.itk_serving_per_day:
                        remaining_after = max(0, supp.itk_total_quantity - diff)
                        initial_remain_day = remaining_after // supp.itk_serving_per_day

                    db.add(PurchaseHistory(
                        item_id=new_items[0].item_id,
                        cognito_id=supp.cognito_id if supp else None,
                        purchased_dt=supp.itk_purchased_dt if supp else None,
                        total_quantity=supp.itk_total_quantity if supp else None,
                        remain_day=initial_remain_day,
                        reminder_sent=False,
                    ))
            except Exception:
                logger.exception("purchase_history 동기화 실패 (current_id=%s)", req.current_id)

        else:
            # 섭취 취소
            protected_item_id = None
            ph_row = None
            try:
                ph_result = await db.execute(
                    select(PurchaseHistory)
                    .join(IntakeItem, PurchaseHistory.item_id == IntakeItem.item_id)
                    .where(IntakeItem.current_id == req.current_id)
                    .limit(1)
                )
                ph_row = ph_result.scalar_one_or_none()
                protected_item_id = ph_row.item_id if ph_row else None
            except Exception:
                logger.exception("purchase_history 조회 실패 (current_id=%s)", req.current_id)

            q = select(IntakeItem.item_id).where(
                IntakeItem.current_id == req.current_id,
                IntakeItem.intake_dt == req.date,
            )
            if protected_item_id is not None:
                q = q.where(IntakeItem.item_id != protected_item_id)
            q = q.order_by(IntakeItem.item_id.desc()).limit(-diff)

            rows_to_delete = await db.execute(q)
            ids = [r[0] for r in rows_to_delete.all()]
            await db.execute(delete(IntakeItem).where(IntakeItem.item_id.in_(ids)))

            if ph_row:
                try:
                    ph_row.remain_day = (ph_row.remain_day or 0) + (-diff)
                except Exception:
                    logger.exception("purchase_history remain_day 복원 실패 (current_id=%s)", req.current_id)

        # itk_total_quantity 직접 차감 (NULL이 아닌 경우만, 0 이하로 내려가지 않도록)
        await db.execute(
            update(IntakeSupplement)
            .where(
                IntakeSupplement.current_id == req.current_id,
                IntakeSupplement.itk_total_quantity.isnot(None),
            )
            .values(itk_total_quantity=func.greatest(0, IntakeSupplement.itk_total_quantity - diff))
        )

        await db.commit()


record_service = RecordService()
