"""music21 のスコアを共通の Note 列へ変換する（設計書 11.2 / 17.2）。"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from music21 import chord, converter, note as m21_note, stream
from music21.note import Unpitched

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


@dataclass
class ParsedPart:
    """1トラック（パート）分の抽出結果（設計書 17.2 パート選択）。"""

    index: int
    name: str
    score: ParsedScore


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


def list_parts(score) -> list[stream.Stream]:
    """スコアに含まれる全パート（トラック）を返す。パートが無い場合はスコア自体を1パートとして扱う。"""
    parts = list(score.parts) if hasattr(score, "parts") else []
    return parts if parts else [score]


def _part_display_name(part: stream.Stream, index: int) -> str:
    """パートの表示名を決める（トラック名 → 楽器名 → 連番の順に採用）。"""
    name = getattr(part, "partName", None)
    if name and str(name).strip():
        return str(name).strip()

    instrument_obj = part.getInstrument(returnDefault=False)
    if instrument_obj is not None and instrument_obj.instrumentName:
        return str(instrument_obj.instrumentName)

    return f"トラック {index + 1}"


def _extract_part(part: stream.Stream) -> ParsedScore:
    """1パート分の音符列を抽出する（設計書 5.1 / 9.2）。"""
    result = ParsedScore()

    measures = list(part.getElementsByClass(stream.Measure))
    if not measures:
        part = part.makeMeasures()
        measures = list(part.getElementsByClass(stream.Measure))

    key_signature = "C"
    time_signature = "4/4"
    has_chord = False
    skipped_unpitched = 0

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

            if isinstance(element, Unpitched):
                # 打楽器トラックなどの「高さを持たない音」は、単音/和音モデルでは
                # 表現できないためスキップする（設計書はギターの音高付き旋律が対象）
                skipped_unpitched += 1
                continue

            tie_to_next = element.tie is not None and element.tie.type in ("start", "continue")
            # 和音は、同じ拍位置に複数のNoteとして展開する（設計書 9.2）
            pitches = (
                sorted(element.pitches, key=lambda item: item.midi)
                if isinstance(element, chord.Chord)
                else [element.pitch]
            )
            if len(pitches) > 1:
                has_chord = True

            for pitch in pitches:
                accidental = Accidental.NONE
                if pitch.accidental is not None:
                    accidental = ACCIDENTAL_NAMES.get(pitch.accidental.name, Accidental.NONE)
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
        result.warnings.append("和音を含む譜面として読み込みました。")
    if skipped_unpitched:
        result.warnings.append(
            f"高さを持たない音（打楽器など）を{skipped_unpitched}個スキップしました。"
        )
    if not result.measures:
        result.measures.append(MeasureInfo(measureIndex=0))

    return result


def score_to_parts(score) -> list[ParsedPart]:
    """スコアに含まれる全パートを抽出する（設計書 17.2 パート選択）。"""
    return [
        ParsedPart(index=index, name=_part_display_name(part, index), score=_extract_part(part))
        for index, part in enumerate(list_parts(score))
    ]


def score_to_notes(score) -> ParsedScore:
    """music21 スコアから、単音旋律としての Note 列を取り出す（後方互換: 先頭パートのみ）。"""
    result = ParsedScore()
    metadata = getattr(score, "metadata", None)
    if metadata is not None and metadata.title:
        result.title = metadata.title

    extracted = _extract_part(list_parts(score)[0])
    extracted.title = result.title
    return extracted


def score_title(score) -> str | None:
    metadata = getattr(score, "metadata", None)
    if metadata is not None and metadata.title:
        return metadata.title
    return None


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
