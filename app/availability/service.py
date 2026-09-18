from datetime import datetime, timedelta

from app.busy_blocks.models import BusyBlock
from app.shared.time import as_seoul_time


def _overlaps(start: datetime, end: datetime, busy_start: datetime, busy_end: datetime) -> bool:
    return start < busy_end and busy_start < end


def overlaps_busy_block(block: BusyBlock, slot: datetime, slot_minutes: int) -> bool:
    local_slot = as_seoul_time(slot)
    local_slot_end = local_slot + timedelta(minutes=slot_minutes)
    if block.is_recurring:
        if block.weekday != local_slot.weekday() or not block.start_time or not block.end_time:
            return False
        busy_start = local_slot.replace(
            hour=block.start_time.hour,
            minute=block.start_time.minute,
            second=block.start_time.second,
            microsecond=block.start_time.microsecond,
        )
        busy_end = local_slot.replace(
            hour=block.end_time.hour,
            minute=block.end_time.minute,
            second=block.end_time.second,
            microsecond=block.end_time.microsecond,
        )
        return _overlaps(local_slot, local_slot_end, busy_start, busy_end)
    if block.starts_at is None or block.ends_at is None:
        return False
    return _overlaps(slot, slot + timedelta(minutes=slot_minutes), block.starts_at, block.ends_at)


def desired_mask(
    blocks: list[BusyBlock], slots: list[datetime], slot_minutes: int = 15
) -> list[bool]:
    return [
        not any(overlaps_busy_block(block, slot, slot_minutes) for block in blocks)
        for slot in slots
    ]
