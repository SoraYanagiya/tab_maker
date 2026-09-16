"""ギターのチューニング定義（設計書 6.2）。"""

from __future__ import annotations

from dataclasses import dataclass, field

MAX_FRET = 24
FINGER_COUNT = 4


@dataclass(frozen=True)
class Tuning:
    """開放弦のMIDIノート番号。index 0 が1弦（最も高い音）。"""

    name: str
    open_pitches: tuple[int, ...]
    labels: tuple[str, ...]

    @property
    def string_count(self) -> int:
        return len(self.open_pitches)

    def fret_for(self, string_index: int, midi: int) -> int | None:
        fret = midi - self.open_pitches[string_index]
        if 0 <= fret <= MAX_FRET:
            return fret
        return None

    def pitch_range(self) -> tuple[int, int]:
        lowest = min(self.open_pitches)
        highest = max(self.open_pitches) + MAX_FRET
        return lowest, highest


STANDARD_TUNING = Tuning(
    name="standard",
    open_pitches=(64, 59, 55, 50, 45, 40),
    labels=("e", "B", "G", "D", "A", "E"),
)

TUNINGS: dict[str, Tuning] = {
    "standard": STANDARD_TUNING,
    "drop_d": Tuning(
        name="drop_d",
        open_pitches=(64, 59, 55, 50, 45, 38),
        labels=("e", "B", "G", "D", "A", "D"),
    ),
    "half_step_down": Tuning(
        name="half_step_down",
        open_pitches=(63, 58, 54, 49, 44, 39),
        labels=("e♭", "B♭", "G♭", "D♭", "A♭", "E♭"),
    ),
}


def get_tuning(name: str | None) -> Tuning:
    if not name:
        return STANDARD_TUNING
    return TUNINGS.get(name, STANDARD_TUNING)
