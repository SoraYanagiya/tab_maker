"""探索中の左手の状態モデル（設計書 6.4 / 9）。"""

from __future__ import annotations

from dataclasses import dataclass, field

from .candidate import Candidate


@dataclass(frozen=True)
class State:
    previousString: int | None = None
    previousFret: int | None = None
    previousFinger: int = 0
    handPosition: int | None = None
    fingersOnString: tuple[tuple[int, int], ...] = ()

    @classmethod
    def initial(cls) -> "State":
        return cls()

    def advance(self, candidate: Candidate) -> "State":
        """候補を採用した後の状態を返す。

        開放弦は左手を使わないため、ポジションは直前の値をそのまま引き継ぐ。
        """
        hand_position = self.handPosition if candidate.is_open else candidate.handPosition
        fingers = dict(self.fingersOnString)
        if candidate.is_open:
            fingers.pop(candidate.stringIndex, None)
        else:
            fingers[candidate.stringIndex] = candidate.finger
        return State(
            previousString=candidate.stringIndex,
            previousFret=candidate.fret,
            previousFinger=candidate.finger,
            handPosition=hand_position,
            fingersOnString=tuple(sorted(fingers.items())),
        )

    @property
    def fingers_in_use(self) -> int:
        return len({finger for _, finger in self.fingersOnString if finger > 0})
