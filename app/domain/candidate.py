"""弦・フレット候補および運指候補のモデル（設計書 6.2 / 6.3 / 9.2）。"""

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
    pitch: int = 0
    baseCost: float = 0.0
    transitionCost: float = 0.0

    @property
    def is_open(self) -> bool:
        return self.fret == 0

    @property
    def position(self) -> int | None:
        return self.handPosition


@dataclass(frozen=True)
class EventPlacement:
    """同時に鳴る音（単音または和音）に対する、押さえ方ひとそろい（設計書 9.2）。

    barreFret が設定されている場合、そのフレットを1本の指で複数弦まとめて押さえる
    （セーハ）ことを意味する。
    """

    candidates: tuple[Candidate, ...]
    handPosition: int | None
    barreFret: int | None = None
    baseCost: float = 0.0
    transitionCost: float = 0.0

    @property
    def is_all_open(self) -> bool:
        return all(candidate.is_open for candidate in self.candidates)

    @property
    def fretted(self) -> tuple[Candidate, ...]:
        return tuple(candidate for candidate in self.candidates if not candidate.is_open)

    @property
    def anchor_fret(self) -> int:
        """押さえている中で最も低いフレット。開放弦のみの場合は0。"""
        fretted = self.fretted
        return min(candidate.fret for candidate in fretted) if fretted else 0

    @property
    def strings(self) -> frozenset[int]:
        return frozenset(candidate.stringIndex for candidate in self.candidates)

    def with_costs(self, base: float, transition: float) -> "EventPlacement":
        return EventPlacement(
            candidates=tuple(
                Candidate(
                    noteIndex=candidate.noteIndex,
                    stringIndex=candidate.stringIndex,
                    fret=candidate.fret,
                    finger=candidate.finger,
                    handPosition=self.handPosition,
                    pitch=candidate.pitch,
                    baseCost=base,
                    transitionCost=transition,
                )
                for candidate in self.candidates
            ),
            handPosition=self.handPosition,
            barreFret=self.barreFret,
            baseCost=base,
            transitionCost=transition,
        )
