from dataclasses import dataclass
from datetime import time

from app.busy_blocks.schemas import BusyBlockInput


@dataclass(frozen=True)
class EverytimeImportBlock:
    """One weekly class inferred from an Everytime export image."""

    title: str
    weekday: int
    start_time: time
    end_time: time
    geometry_confidence: float
    title_confidence: float = 0.0

    def to_busy_block_input(self) -> BusyBlockInput:
        return BusyBlockInput(
            source="timetable",
            title=self.title,
            is_recurring=True,
            weekday=self.weekday,
            start_time=self.start_time,
            end_time=self.end_time,
        )


@dataclass(frozen=True)
class TimetableImportPreview:
    adapter: str
    blocks: tuple[EverytimeImportBlock, ...]
    warnings: tuple[str, ...]

    def to_busy_block_inputs(self) -> list[BusyBlockInput]:
        return [block.to_busy_block_input() for block in self.blocks]
