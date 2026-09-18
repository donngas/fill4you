from datetime import datetime, timedelta

from app.busy_blocks.models import BusyBlock
from app.shared.time import as_seoul_time


def _overlaps(start: datetime, end: datetime, busy_start: datetime, busy_end: datetime) -> bool:
    return start < busy_end and busy_start < end


def overlaps_busy_block(block: BusyBlock, slot: datetime, slot_minutes: int) -> bool:
    local_slot = as_seoul_time(slot)
    local_slot_end = local_slot + timedelta(minutes=slot_minutes)
    before = timedelta(
        minutes=block.before_buffer_minutes if block.before_buffer_minutes is not None else 15
    )
    after = timedelta(
        minutes=block.after_buffer_minutes if block.after_buffer_minutes is not None else 15
    )
    if block.is_recurring:
        if not block.start_time or not block.end_time:
            return False
        for day_offset in (-1, 0, 1):
            block_day = local_slot + timedelta(days=day_offset)
            if block.weekday != block_day.weekday():
                continue
            busy_start = (
                block_day.replace(
                    hour=block.start_time.hour,
                    minute=block.start_time.minute,
                    second=0,
                    microsecond=0,
                )
                - before
            )
            busy_end = (
                block_day.replace(
                    hour=block.end_time.hour, minute=block.end_time.minute, second=0, microsecond=0
                )
                + after
            )
            if _overlaps(local_slot, local_slot_end, busy_start, busy_end):
                return True
        return False
    if block.starts_at is None or block.ends_at is None:
        return False
    return _overlaps(
        slot,
        slot + timedelta(minutes=slot_minutes),
        block.starts_at - before,
        block.ends_at + after,
    )


def desired_mask(
    blocks: list[BusyBlock], slots: list[datetime], slot_minutes: int = 15
) -> list[bool]:
    return [
        not any(overlaps_busy_block(block, slot, slot_minutes) for block in blocks)
        for slot in slots
    ]


def busy_preview_blocks(
    blocks: list[BusyBlock],
    slots: list[datetime],
    slot_minutes: int,
    *,
    include_titles: bool,
) -> list[dict[str, int | str | list[int] | None]]:
    preview_blocks = []
    for block in blocks:
        slot_indexes = [
            index
            for index, slot in enumerate(slots)
            if overlaps_busy_block(block, slot, slot_minutes)
        ]
        if slot_indexes:
            preview_blocks.append(
                {
                    "id": block.id,
                    "title": block.title if include_titles else None,
                    "slot_indexes": slot_indexes,
                }
            )
    return preview_blocks
