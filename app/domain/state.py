"""探索中の左手の状態モデル（設計書 6.4 / 9）。"""

from __future__ import annotations

from dataclasses import dataclass

from .candidate import Candidate, EventPlacement


@dataclass(frozen=True)
class State:
    """直前に押さえていた形と手の位置。

    単音・和音のどちらも「同時に鳴る音の集合（イベント）」として同じ形で保持する。
    """

    previousPlacements: tuple[tuple[int, int, int], ...] = ()  # (弦, フレット, 指)
    handPosition: int | None = None

    @classmethod
    def initial(cls) -> "State":
        return cls()

    # --- 単音のための参照（イベントの要素が1つのときのみ意味を持つ）---
    @property
    def previousString(self) -> int | None:
        return self.previousPlacements[0][0] if self.previousPlacements else None

    @property
    def previousFret(self) -> int | None:
        return self.previousPlacements[0][1] if self.previousPlacements else None

    @property
    def previousFinger(self) -> int:
        return self.previousPlacements[0][2] if self.previousPlacements else 0

    @property
    def fingersOnString(self) -> tuple[tuple[int, int], ...]:
        return tuple((string, finger) for string, _, finger in self.previousPlacements if finger > 0)

    @property
    def fingers_in_use(self) -> int:
        return len({finger for _, _, finger in self.previousPlacements if finger > 0})

    @property
    def previous_frets(self) -> tuple[int, ...]:
        return tuple(fret for _, fret, _ in self.previousPlacements)

    @property
    def previous_strings(self) -> frozenset[int]:
        return frozenset(string for string, _, _ in self.previousPlacements)

    def advance(self, candidate: Candidate) -> "State":
        """単音の候補を採用した後の状態。"""
        return self.advance_event(EventPlacement(candidates=(candidate,), handPosition=candidate.handPosition))

    def advance_event(self, placement: EventPlacement) -> "State":
        """イベント（和音を含む）を採用した後の状態。

        開放弦のみのイベントは左手を使わないため、ポジションは直前の値を引き継ぐ。
        """
        hand_position = (
            self.handPosition if placement.is_all_open else placement.handPosition
        )
        return State(
            previousPlacements=tuple(
                (candidate.stringIndex, candidate.fret, candidate.finger)
                for candidate in placement.candidates
            ),
            handPosition=hand_position,
        )

    def key(self) -> tuple:
        return (self.previousPlacements, self.handPosition)
