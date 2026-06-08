from datetime import datetime
from sqlalchemy import DateTime, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class PushLog(Base):
    __tablename__ = "push_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slot: Mapped[str] = mapped_column(String(16), nullable=False)
    category_slug: Mapped[str] = mapped_column(String(64), nullable=False)
    pushed_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    item_ids: Mapped[list] = mapped_column(JSON, nullable=False)
