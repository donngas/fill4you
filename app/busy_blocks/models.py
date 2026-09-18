from datetime import datetime, time

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Time, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class BusyBlock(Base):
    """A local busy interval from a timetable, manual entry, or future calendar sync."""

    __tablename__ = "busy_blocks"
    __table_args__ = (
        CheckConstraint(
            "source IN ('timetable', 'manual', 'google_calendar')", name="busy_blocks_source"
        ),
        CheckConstraint("weekday IS NULL OR weekday BETWEEN 0 AND 6", name="busy_blocks_weekday"),
        CheckConstraint(
            "(is_recurring = true AND weekday IS NOT NULL AND start_time IS NOT NULL "
            "AND end_time IS NOT NULL AND starts_at IS NULL AND ends_at IS NULL) OR "
            "(is_recurring = false AND weekday IS NULL AND start_time IS NULL "
            "AND end_time IS NULL AND starts_at IS NOT NULL AND ends_at IS NOT NULL)",
            name="busy_blocks_schedule_shape",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    source: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(255))
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    weekday: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    external_event_id: Mapped[str | None] = mapped_column(String(1024), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
