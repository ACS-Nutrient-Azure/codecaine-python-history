from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user_id
from app.db.database import get_db
from app.schemas.history import SupplementListResponse, RecordsResponse, RecordUpsertRequest
from app.services.record_service import record_service

router = APIRouter(prefix="/history", tags=["기록"])


@router.get("/supplements", response_model=SupplementListResponse)
async def get_supplements(
    cognito_id: str = Query(...),
    is_active: bool | None = Query(None),
    _: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """복용 중인 영양제 목록 (intake_supplements — DMS 동기화 데이터)"""
    return await record_service.get_supplements(db, cognito_id, is_active)


@router.get("/records", response_model=RecordsResponse)
async def get_records(
    cognito_id: str = Query(...),
    year: int = Query(...),
    month: int = Query(...),
    _: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """월별 영양제 복용 기록 조회 (taken_count = intake_item row 수)"""
    return await record_service.get_monthly_records(db, cognito_id, year, month)


@router.post("/records", status_code=204)
async def upsert_record(
    req: RecordUpsertRequest,
    _: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """영양제 복용 기록 추가/수정 (taken_count만큼 intake_item row 동기화)"""
    await record_service.upsert_record(db, req)
