from datetime import datetime, date
from sqlalchemy import String, DateTime, Boolean, Integer, BigInteger, Date, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.database import Base


class IntakeSupplement(Base):
    """intake_supplements 테이블 — DMS로 mypage current_supplements에서 동기화됨 (읽기 전용)"""
    __tablename__ = "intake_supplements"

    current_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    cognito_id: Mapped[str] = mapped_column(String(36), nullable=False)
    itk_product_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    itk_serving_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    itk_serving_per_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    itk_daily_total_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    itk_total_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    itk_purchased_dt: Mapped[date | None] = mapped_column(Date, nullable=True)
    itk_estimated_end_dt: Mapped[date | None] = mapped_column(Date, nullable=True)
    remaining_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class IntakeItem(Base):
    """intake_item 테이블 — 영양제 1회 복용 이벤트"""
    __tablename__ = "intake_item"

    item_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    current_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("intake_supplements.current_id"), nullable=False)
    intake_dt: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PurchaseHistory(Base):
    """purchase_history 테이블"""
    __tablename__ = "purchase_history"

    purchase_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("intake_item.item_id"), nullable=False)
    cognito_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    purchased_dt: Mapped[date | None] = mapped_column(Date, nullable=True)
    total_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    remain_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reminder_sent: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
