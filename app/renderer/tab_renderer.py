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


def _group_events(
    notes: list[Note], fingerings: list[Fingering]
) -> dict[int, list[list[Fingering]]]:
    """小節ごとに、同時に鳴る音をひとつの列としてまとめる。"""
    by_measure: dict[int, list[list[Fingering]]] = {}
    for note, fingering in zip(notes, fingerings):
        columns = by_measure.setdefault(note.measureIndex, [])
        if (
            columns
            and not fingering.isRest
            and not columns[-1][0].isRest
            and abs(columns[-1][0].onsetBeat - fingering.onsetBeat) < 1e-9
        ):
            columns[-1].append(fingering)
        else:
            columns.append([fingering])
    return by_measure


def render_text(
    notes: list[Note],
    fingerings: list[Fingering],
    tuning: Tuning = STANDARD_TUNING,
    measures_per_line: int = 4,
) -> str:
    """6線のTAB譜テキストを生成する。和音は同じ列に縦に並べる。"""
    if not notes:
        return "\n".join(f"{label}|{GAP * 8}" for label in tuning.labels)

    by_measure = _group_events(notes, fingerings)
    measure_indexes = sorted(by_measure)
    lines: list[str] = []

    for block_start in range(0, len(measure_indexes), measures_per_line):
        block = measure_indexes[block_start : block_start + measures_per_line]
        rows = ["" for _ in tuning.labels]

        for measure_index in block:
            for column in by_measure[measure_index]:
                played = [item for item in column if not item.isRest and item.stringIndex is not None]
                if not played:
                    for string_index in range(tuning.string_count):
                        rows[string_index] += GAP * REST_WIDTH
                    continue

                texts = {item.stringIndex: _cell_text(item) for item in played}
                width = max(len(text) for text in texts.values()) + 2
                for string_index in range(tuning.string_count):
                    text = texts.get(string_index)
                    if text is None:
                        rows[string_index] += GAP * width
                    else:
                        padding = width - len(text) - 1
                        rows[string_index] += GAP + text + GAP * padding
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
    by_measure = _group_events(notes, fingerings)

    for measure_index in sorted(by_measure):
        for column in by_measure[measure_index]:
            head = column[0]
            location = f"{head.measureIndex + 1}小節目 {head.onsetBeat + 1:g}拍目"
            played = [item for item in column if not item.isRest and item.stringIndex is not None]
            if not played:
                lines.append(f"{location}: 休符")
                continue

            if len(played) == 1:
                lines.append(f"{location}: {_describe(played[0], tuning)}")
                continue

            barre = next((item for item in played if item.isBarre), None)
            suffix = f"（{barre.fret}フレットでセーハ）" if barre else ""
            lines.append(f"{location}: 和音{suffix}")
            for item in sorted(played, key=lambda entry: entry.stringIndex):
                lines.append(f"  - {_describe(item, tuning)}")

    return "\n".join(lines)


def _describe(fingering: Fingering, tuning: Tuning) -> str:
    string_number = fingering.stringIndex + 1
    finger_text = "開放弦" if fingering.finger == 0 else f"指{fingering.finger}"
    position_text = "－" if fingering.position is None else f"{fingering.position}フレット"
    shift_text = "移動なし" if fingering.handShift == 0 else f"{fingering.handShift:+d}フレット移動"
    barre_text = "、セーハ" if fingering.isBarre else ""
    return (
        f"{string_number}弦{fingering.fret}フレット "
        f"({finger_text}, ポジション{position_text}, {shift_text}{barre_text})"
    )
