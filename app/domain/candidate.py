"""弦・フレット候補および運指候補のモデル（設計書 6.2 / 6.3）。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StringFret:
    stringIndex: int
    fret: int
    pitch: int

    @property
    def is_open(self) -> bool:
        return self.fret == 0


@dataclass(frozen=True)
class Candidate:
    """1音に対する具体的な運指の選択肢。

    handPosition は人差し指が置かれるフレット。開放弦は手の位置に依存しないため
    None（未確定）または直前の値を引き継ぐ（設計書 7.4）。
    """

    noteIndex: int
    stringIndex: int
    fret: int
    finger: int
    handPosition: int | None
    baseCost: float = 0.0
    transitionCost: float = 0.0

    @property
    def is_open(self) -> bool:
        return self.fret == 0

    @property
    def position(self) -> int | None:
        return self.handPosition
