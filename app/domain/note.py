"""音符・小節のドメインモデル（設計書 6.1 / 6.1.1）。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Accidental(str, Enum):
    NONE = "none"
    SHARP = "sharp"
    FLAT = "flat"
    NATURAL = "natural"


class Duration(str, Enum):
    WHOLE = "whole"
    HALF = "half"
    QUARTER = "quarter"
    EIGHTH = "eighth"
    SIXTEENTH = "sixteenth"


DURATION_BEATS: dict[Duration, float] = {
    Duration.WHOLE: 4.0,
    Duration.HALF: 2.0,
    Duration.QUARTER: 1.0,
    Duration.EIGHTH: 0.5,
    Duration.SIXTEENTH: 0.25,
}

ACCIDENTAL_ALTER: dict[Accidental, int] = {
    Accidental.NONE: 0,
    Accidental.SHARP: 1,
    Accidental.FLAT: -1,
    Accidental.NATURAL: 0,
}

STEP_SEMITONES: dict[str, int] = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}

SHARP_ORDER = ["F", "C", "G", "D", "A", "E", "B"]
FLAT_ORDER = ["B", "E", "A", "D", "G", "C", "F"]

KEY_SIGNATURE_FIFTHS: dict[str, int] = {
    "C": 0, "G": 1, "D": 2, "A": 3, "E": 4, "B": 5, "F#": 6, "C#": 7,
    "F": -1, "Bb": -2, "Eb": -3, "Ab": -4, "Db": -5, "Gb": -6, "Cb": -7,
    "Am": 0, "Em": 1, "Bm": 2, "F#m": 3, "C#m": 4, "G#m": 5, "D#m": 6, "A#m": 7,
    "Dm": -1, "Gm": -2, "Cm": -3, "Fm": -4, "Bbm": -5, "Ebm": -6, "Abm": -7,
}


def key_signature_fifths(key_signature: str) -> int:
    return KEY_SIGNATURE_FIFTHS.get(key_signature, 0)


def key_alteration(step: str, key_signature: str) -> int:
    """調号によって、その音名に付く変化記号（+1/-1/0）を返す。"""
    fifths = key_signature_fifths(key_signature)
    step = step.upper()
    if fifths > 0 and step in SHARP_ORDER[:fifths]:
        return 1
    if fifths < 0 and step in FLAT_ORDER[: -fifths]:
        return -1
    return 0


def midi_number(step: str, octave: int, accidental: Accidental, key_signature: str = "C") -> int:
    """音名・オクターブ・臨時記号・調号からMIDIノート番号を求める。

    臨時記号が指定されている場合（ナチュラル含む）は調号より優先される。
    """
    base = STEP_SEMITONES[step.upper()] + (octave + 1) * 12
    if accidental == Accidental.NONE:
        return base + key_alteration(step, key_signature)
    return base + ACCIDENTAL_ALTER[accidental]


@dataclass
class Note:
    midiNumber: int | None
    pitchName: str
    octave: int
    accidental: Accidental = Accidental.NONE
    duration: Duration = Duration.QUARTER
    isDotted: bool = False
    tieToNext: bool = False
    isRest: bool = False
    onsetBeat: float = 0.0
    measureIndex: int = 0

    @property
    def beats(self) -> float:
        base = DURATION_BEATS[self.duration]
        return base * 1.5 if self.isDotted else base


@dataclass
class MeasureInfo:
    measureIndex: int
    keySignature: str = "C"
    timeSignature: str = "4/4"

    @property
    def beats_per_measure(self) -> float:
        numerator, denominator = self.timeSignature.split("/")
        return int(numerator) * 4.0 / int(denominator)
