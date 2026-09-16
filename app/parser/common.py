"""music21 のスコアを共通の Note 列へ変換する（設計書 11.2）。"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from music21 import chord, converter, note as m21_note, stream

from ..domain.note import Accidental, Duration, MeasureInfo, Note

QUARTER_LENGTH_TABLE: list[tuple[float, Duration, bool]] = [
    (4.0, Duration.WHOLE, False),
    (3.0, Duration.HALF, True),
    (2.0, Duration.HALF, False),
    (1.5, Duration.QUARTER, True),
    (1.0, Duration.QUARTER, False),
    (0.75, Duration.EIGHTH, True),
    (0.5, Duration.EIGHTH, False),
    (0.375, Duration.SIXTEENTH, True),
    (0.25, Duration.SIXTEENTH, False),
]

ACCIDENTAL_NAMES: dict[str, Accidental] = {
    "sharp": Accidental.SHARP,
    "flat": Accidental.FLAT,
    "natural": Accidental.NATURAL,
}


@dataclass
class ParsedScore:
    notes: list[Note] = field(default_factory=list)
    measures: list[MeasureInfo] = field(default_factory=list)
    title: str | None = None
    warnings: list[str] = field(default_factory=list)


def duration_from_quarter_length(quarter_length: float) -> tuple[Duration, bool]:
    best = min(QUARTER_LENGTH_TABLE, key=lambda row: abs(row[0] - quarter_length))
    return best[1], best[2]


def parse_file(content: bytes, suffix: str):
    """一時ファイル経由で music21 に読み込ませる。"""
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
        handle.write(content)
        path = Path(handle.name)
    try:
        return converter.parse(str(path))
    finally:
        path.unlink(missing_ok=True)


def _first_part(score) -> stream.Stream:
    parts = list(score.parts) if hasattr(score, "parts") else []
    if parts:
        return parts[0]
    return score


def score_to_notes(score) -> ParsedScore:
    """music21 スコアから、単音旋律としての Note 列を取り出す。"""
    result = ParsedScore()
    metadata = getattr(score, "metadata", None)
    if metadata is not None and metadata.title:
        result.title = metadata.title

    part = _first_part(score)
    measures = list(part.getElementsByClass(stream.Measure))
    if not measures:
        part = part.makeMeasures()
        measures = list(part.getElementsByClass(stream.Measure))

    key_signature = "C"
    time_signature = "4/4"
    has_chord = False

    for measure_index, measure in enumerate(measures):
        if measure.keySignature is not None:
            key_signature = _key_signature_name(measure.keySignature)
        if measure.timeSignature is not None:
            time_signature = measure.timeSignature.ratioString

        result.measures.append(
            MeasureInfo(
                measureIndex=measure_index,
                keySignature=key_signature,
                timeSignature=time_signature,
            )
        )

        for element in measure.notesAndRests:
            duration, is_dotted = duration_from_quarter_length(float(element.quarterLength))
            onset = float(element.offset)

            if isinstance(element, m21_note.Rest):
                result.notes.append(
                    Note(
                        midiNumber=None,
                        pitchName="C",
                        octave=4,
                        duration=duration,
                        isDotted=is_dotted,
                        isRest=True,
                        onsetBeat=onset,
                        measureIndex=measure_index,
                    )
                )
                continue

            pitch = element.pitch
            if isinstance(element, chord.Chord):
                has_chord = True
                pitch = max(element.pitches, key=lambda p: p.midi)

            accidental = Accidental.NONE
            if pitch.accidental is not None:
                accidental = ACCIDENTAL_NAMES.get(pitch.accidental.name, Accidental.NONE)

            tie_to_next = element.tie is not None and element.tie.type in ("start", "continue")

            result.notes.append(
                Note(
                    midiNumber=pitch.midi,
                    pitchName=pitch.step,
                    octave=pitch.octave,
                    accidental=accidental,
                    duration=duration,
                    isDotted=is_dotted,
                    tieToNext=tie_to_next,
                    isRest=False,
                    onsetBeat=onset,
                    measureIndex=measure_index,
                )
            )

    if has_chord:
        result.warnings.append("和音が含まれていたため、各和音の最高音のみを読み込みました（v1は単音旋律のみ対応）。")
    if not result.measures:
        result.measures.append(MeasureInfo(measureIndex=0))

    return result


def _key_signature_name(key_signature) -> str:
    """music21 の調号を "C" / "Am" 形式の名前に変換する。"""
    as_key = getattr(key_signature, "asKey", None)
    if callable(as_key):
        key = as_key()
        tonic = key.tonic.name.replace("-", "b")
        return tonic if key.mode == "major" else f"{tonic}m"
    sharps = getattr(key_signature, "sharps", 0) or 0
    majors = {0: "C", 1: "G", 2: "D", 3: "A", 4: "E", 5: "B", 6: "F#", 7: "C#",
              -1: "F", -2: "Bb", -3: "Eb", -4: "Ab", -5: "Db", -6: "Gb", -7: "Cb"}
    return majors.get(sharps, "C")
