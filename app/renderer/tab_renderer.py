"""TAB譜のテキストレンダリング（設計書 5.2）。"""

from __future__ import annotations

from ..domain.note import Note
from ..domain.tuning import STANDARD_TUNING, Tuning
from ..optimizer.fingering_optimizer import Fingering

GAP = "-"
REST_WIDTH = 3


def _cell_text(fingering: Fingering) -> str:
    fret = "" if fingering.fret is None else str(fingering.fret)
    return f"({fret})" if fingering.isTiedContinuation else fret


def render_text(
    notes: list[Note],
    fingerings: list[Fingering],
    tuning: Tuning = STANDARD_TUNING,
    measures_per_line: int = 4,
) -> str:
    """6線のTAB譜テキストを生成する。"""
    if not notes:
        return "\n".join(f"{label}|{GAP * 8}" for label in tuning.labels)

    by_measure: dict[int, list[Fingering]] = {}
    for note, fingering in zip(notes, fingerings):
        by_measure.setdefault(note.measureIndex, []).append(fingering)

    measure_indexes = sorted(by_measure)
    lines: list[str] = []

    for block_start in range(0, len(measure_indexes), measures_per_line):
        block = measure_indexes[block_start : block_start + measures_per_line]
        rows = ["" for _ in tuning.labels]

        for measure_index in block:
            for fingering in by_measure[measure_index]:
                if fingering.isRest or fingering.stringIndex is None:
                    for string_index in range(tuning.string_count):
                        rows[string_index] += GAP * REST_WIDTH
                    continue
                text = _cell_text(fingering)
                width = len(text) + 2
                for string_index in range(tuning.string_count):
                    if string_index == fingering.stringIndex:
                        rows[string_index] += GAP + text + GAP
                    else:
                        rows[string_index] += GAP * width
            for string_index in range(tuning.string_count):
                rows[string_index] += "|"

        for label, row in zip(tuning.labels, rows):
            lines.append(f"{label:>2}|{row}")
        lines.append("")

    return "\n".join(lines).rstrip("\n")


def render_details(
    notes: list[Note],
    fingerings: list[Fingering],
    tuning: Tuning = STANDARD_TUNING,
) -> str:
    """各音の弦・フレット・指番号・ポジション・手の移動量を併記した詳細テキスト。"""
    lines = ["[運指詳細]"]
    for note, fingering in zip(notes, fingerings):
        location = f"{fingering.measureIndex + 1}小節目 {fingering.onsetBeat + 1:g}拍目"
        if fingering.isRest or fingering.stringIndex is None:
            lines.append(f"{location}: 休符")
            continue
        string_number = fingering.stringIndex + 1
        finger_text = "開放弦" if fingering.finger == 0 else f"指{fingering.finger}"
        position_text = "－" if fingering.position is None else f"{fingering.position}フレット"
        shift_text = "移動なし" if fingering.handShift == 0 else f"{fingering.handShift:+d}フレット移動"
        lines.append(
            f"{location}: {string_number}弦{fingering.fret}フレット "
            f"({finger_text}, ポジション{position_text}, {shift_text})"
        )
    return "\n".join(lines)
