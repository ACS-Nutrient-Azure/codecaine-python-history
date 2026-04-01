from datetime import date
from pydantic import BaseModel

LOW_STOCK_THRESHOLD = 10


# ── Supplement ────────────────────────────────────────────────────────────────

class SupplementOut(BaseModel):
    model_config = {"from_attributes": True}

    current_id: int
    cognito_id: str
    itk_product_name: str | None = None
    itk_serving_amount: int | None = None
    itk_serving_per_day: int | None = None
    itk_daily_total_amount: int | None = None
    itk_total_quantity: int | None = None
    is_active: bool | None = None
    itk_purchased_dt: date | None = None
    itk_estimated_end_dt: date | None = None
    low_stock: bool = False


class SupplementListResponse(BaseModel):
    supplements: list[SupplementOut]


# ── Records ───────────────────────────────────────────────────────────────────

class SupplementRecord(BaseModel):
    current_id: int
    product_name: str | None
    taken_count: int
    daily_limit: int | None


class DayRecord(BaseModel):
    date: str  # YYYY-MM-DD
    supplements: list[SupplementRecord]


class RecordsResponse(BaseModel):
    year: int
    month: int
    records: list[DayRecord]


class RecordUpsertRequest(BaseModel):
    cognito_id: str
    current_id: int
    date: date
    taken_count: int
