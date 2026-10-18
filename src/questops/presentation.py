"""How a run is presented: the one place that decides what to show and how wide to draw it."""

from __future__ import annotations

from dataclasses import dataclass

from .art import color_enabled, visible_len
from .engine import Result
from .events import Art, Event, Retreat
from .pixels import Backend, backend_for

MIN_WIDTH = 62


@dataclass(frozen=True)
class Presentation:
    """`ephemeral` is the one-off mode (--dry-run): nothing is saved, so the story leaves out
    the bookkeeping and the card shows no XP, 'kens, streak or gear, but is narrated instead."""

    ephemeral: bool = False
    color: bool = False
    pixels: Backend | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "pixels", backend_for(self.pixels or self.color))

    @classmethod
    def detect(cls, ephemeral: bool = False, color: bool | None = None) -> Presentation:
        return cls(ephemeral=ephemeral, color=color_enabled() if color is None else color)

    @property
    def narrated(self) -> bool:
        """Open and close the story with the wake-up and fade-out lines."""
        return self.ephemeral

    @property
    def show_stats(self) -> bool:
        return not self.ephemeral

    @property
    def show_gear(self) -> bool:
        return not self.ephemeral

    def shows(self, event: Event) -> bool:
        return not (self.ephemeral and isinstance(event, Retreat))

    def events(self, r: Result) -> list[Event]:
        return [e for e in r.transcript if self.shows(e)]

    def story(self, r: Result) -> list[str]:
        """The visible story as text (no art)."""
        return [e.text for e in self.events(r) if not isinstance(e, Art)]

    def shadow_width(self, art_block: str) -> int:
        """Shadow width in pixels: a little narrower than the art, same parity so the centres line up."""
        pixels = max(visible_len(ln) for ln in art_block.split("\n")) // self.pixels.cell_width
        pixels = pixels * 9 // 10
        return pixels - pixels % 2

    def box_width(self, lines: list[str]) -> int:
        return self.pixels.width or max(MIN_WIDTH, *(visible_len(ln) + 4 for ln in lines))

    def layout_width(self, blocks: list[str], box_width: int) -> int:
        """The width everything is centred in; wide backends grow it instead of truncating."""
        return self.pixels.width or max(box_width, *(visible_len(ln) for b in blocks for ln in b.split("\n")))
