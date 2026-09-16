"""運指最適化エンジン（設計書 8. アルゴリズム設計 / 9. 和音への対応）。

候補生成 → スコア計算 → ビームサーチで最小コスト経路を選ぶ。
単音も和音も「同時に鳴る音の集合（イベント）」として同じ経路で扱う。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import NamedTuple

from ..domain.candidate import Candidate, EventPlacement
from ..domain.note import MeasureInfo, Note, midi_number
from ..domain.state import State
from ..domain.tuning import FINGER_COUNT, MAX_FRET, STANDARD_TUNING, Tuning
from .scoring import (
    ScoringWeights,
    allowed_shift,
    base_cost,
    event_base_cost,
    event_transition_cost,
    transition_cost,
)

MAX_PLACEMENTS_PER_EVENT = 60


@dataclass
class Fingering:
    noteIndex: int
    measureIndex: int
    onsetBeat: float
    isRest: bool
    stringIndex: int | None = None
    stringLabel: str | None = None
    fret: int | None = None
    finger: int = 0
    position: int | None = None
    handShift: int = 0
    isTiedContinuation: bool = False
    isBarre: bool = False
    chordSize: int = 1


@dataclass
class ConversionWarning:
    noteIndex: int
    measureIndex: int
    onsetBeat: float
    kind: str
    message: str


@dataclass
class OptimizationResult:
    fingerings: list[Fingering] = field(default_factory=list)
    warnings: list[ConversionWarning] = field(default_factory=list)
    totalCost: float = 0.0


class _Event(NamedTuple):
    noteIndices: tuple[int, ...]
    midis: tuple[int, ...]
    tied: bool
    availableBeats: float


@dataclass
class _Node:
    placement: EventPlacement | None
    parent: "_Node | None"


@dataclass
class _Beam:
    state: State
    cost: float
    node: _Node


def resolve_midi(
    note: Note, measures: dict[int, MeasureInfo], notation_octave_shift: int = 0
) -> int | None:
    """Noteの音高を実音のMIDIノート番号として確定させる。

    ギター譜は実音より1オクターブ高く記譜するため、記譜音高から実音への変換を
    notation_octave_shift（オクターブ単位）で行う。
    """
    if note.isRest:
        return None
    if note.midiNumber is not None:
        written = note.midiNumber
    else:
        measure = measures.get(note.measureIndex)
        key_signature = measure.keySignature if measure else "C"
        written = midi_number(note.pitchName, note.octave, note.accidental, key_signature)
    return written + 12 * notation_octave_shift


def _fit_into_range(midi: int, tuning: Tuning) -> tuple[int, int]:
    """音域外の音をオクターブ単位で移調して収める。移調したオクターブ数を返す。"""
    lowest, highest = tuning.pitch_range()
    shifted = 0
    while midi < lowest:
        midi += 12
        shifted += 1
    while midi > highest:
        midi -= 12
        shifted -= 1
    return midi, shifted


def generate_candidates(
    note_index: int, midi: int, tuning: Tuning, state: State
) -> list[Candidate]:
    """1音に対する弦・フレット・運指の候補を列挙する（設計書 8.2）。"""
    candidates: list[Candidate] = []
    for string_index in range(tuning.string_count):
        fret = tuning.fret_for(string_index, midi)
        if fret is None:
            continue
        if fret == 0:
            # 開放弦は左手を使わないため、手の位置は直前のまま引き継ぐ（設計書 7.4）
            candidates.append(
                Candidate(
                    noteIndex=note_index,
                    stringIndex=string_index,
                    fret=0,
                    finger=0,
                    handPosition=state.handPosition,
                    pitch=midi,
                )
            )
            continue
        lowest_position = max(1, fret - (FINGER_COUNT - 1))
        for hand_position in range(lowest_position, fret + 1):
            if hand_position + FINGER_COUNT - 1 > MAX_FRET:
                continue
            candidates.append(
                Candidate(
                    noteIndex=note_index,
                    stringIndex=string_index,
                    fret=fret,
                    finger=fret - hand_position + 1,
                    handPosition=hand_position,
                    pitch=midi,
                )
            )
    return candidates


def _assign_strings(
    options: list[list[tuple[int, int]]],
    index: int,
    used: dict[int, tuple[int, int]],
    results: list[dict[int, tuple[int, int]]],
    limit: int,
) -> None:
    """各音を別々の弦に割り当てる組み合わせを列挙する（バックトラック）。"""
    if len(results) >= limit:
        return
    if index == len(options):
        results.append(dict(used))
        return
    for string_index, fret in options[index]:
        if string_index in used:
            continue
        used[string_index] = (index, fret)
        _assign_strings(options, index + 1, used, results, limit)
        del used[string_index]


def assign_fingers(
    fretted: list[tuple[int, int]], position: int
) -> tuple[dict[int, int], int | None] | None:
    """押さえる音に指を割り当てる（設計書 9.2）。

    低いフレットから、低い弦の側から順に指を当てる。これは実際の運指と一致する
    （例: Eメジャーなら 3弦1f=人差し指、5弦2f=中指、4弦2f=薬指）。
    指が4本で足りない場合のみ、最低フレットをまとめて押さえるセーハを使う。

    戻り値は (弦→指番号, セーハのフレット or None)。押さえられない場合は None。
    """
    if not fretted:
        return {}, None

    ordered = sorted(fretted, key=lambda item: (item[1], -item[0]))

    if len(ordered) <= FINGER_COUNT:
        assignment = {}
        for finger, (string_index, _) in enumerate(ordered, start=1):
            assignment[string_index] = finger
        return assignment, None

    # セーハ: 最低フレット（＝ポジション）の音を人差し指1本でまとめて押さえる
    lowest = ordered[0][1]
    if lowest != position:
        return None
    barred = [item for item in ordered if item[1] == lowest]
    remaining = [item for item in ordered if item[1] != lowest]
    if len(barred) < 2 or 1 + len(remaining) > FINGER_COUNT:
        return None

    assignment = {string_index: 1 for string_index, _ in barred}
    for offset, (string_index, _) in enumerate(remaining, start=2):
        assignment[string_index] = offset
    return assignment, lowest


def _barre_blocks_open_string(shape: dict[int, tuple[int, int]], barre_fret: int | None) -> bool:
    """セーハが押さえてしまう弦を、開放弦として鳴らそうとしていないか。"""
    if barre_fret is None:
        return False
    barred = [string for string, (_, fret) in shape.items() if fret == barre_fret]
    low, high = min(barred), max(barred)
    return any(
        low < string < high and fret < barre_fret for string, (_, fret) in shape.items()
    )


def generate_event_placements(
    event: _Event, tuning: Tuning, state: State, weights: ScoringWeights
) -> list[EventPlacement]:
    """イベント（単音または和音）に対する押さえ方の候補を列挙する（設計書 9.2）。"""
    if len(event.midis) == 1:
        return [
            EventPlacement(candidates=(candidate,), handPosition=candidate.handPosition)
            for candidate in generate_candidates(
                event.noteIndices[0], event.midis[0], tuning, state
            )
        ]

    per_note_options: list[list[tuple[int, int]]] = []
    for midi in event.midis:
        options = []
        for string_index in range(tuning.string_count):
            fret = tuning.fret_for(string_index, midi)
            if fret is not None:
                options.append((string_index, fret))
        if not options:
            return []
        per_note_options.append(options)

    # 和音のポジションは「押さえる中で最も低いフレット」とする
    positions = sorted(
        {fret for options in per_note_options for _, fret in options if fret > 0}
    )
    positions = [fret for fret in positions if fret + FINGER_COUNT - 1 <= MAX_FRET]

    placements: list[EventPlacement] = []
    seen: set[tuple] = set()

    def add_placement(shape: dict[int, tuple[int, int]], position: int | None) -> None:
        fretted = [(string, fret) for string, (_, fret) in shape.items() if fret > 0]
        assignment = assign_fingers(fretted, position) if position is not None else ({}, None)
        if assignment is None:
            return
        fingers, barre_fret = assignment
        if _barre_blocks_open_string(shape, barre_fret):
            return

        candidates = tuple(
            Candidate(
                noteIndex=event.noteIndices[note_position],
                stringIndex=string_index,
                fret=fret,
                finger=fingers.get(string_index, 0),
                handPosition=position,
                pitch=event.midis[note_position],
            )
            for string_index, (note_position, fret) in sorted(shape.items())
        )
        effective_position = (
            state.handPosition if all(item.fret == 0 for item in candidates) else position
        )
        key = (tuple((item.stringIndex, item.fret) for item in candidates), effective_position)
        if key in seen:
            return
        seen.add(key)
        placements.append(
            EventPlacement(
                candidates=candidates,
                handPosition=effective_position,
                barreFret=barre_fret,
            )
        )

    # すべて開放弦で鳴らせる場合は、手を動かさずに弾ける
    open_only = [[option for option in options if option[1] == 0] for options in per_note_options]
    if all(open_only):
        shapes: list[dict[int, tuple[int, int]]] = []
        _assign_strings(open_only, 0, {}, shapes, 4)
        for shape in shapes:
            add_placement(shape, state.handPosition)

    for position in positions:
        reachable = []
        for options in per_note_options:
            usable = [
                (string_index, fret)
                for string_index, fret in options
                if fret == 0 or position <= fret <= position + FINGER_COUNT - 1
            ]
            if not usable:
                reachable = []
                break
            reachable.append(usable)
        if not reachable:
            continue

        shapes = []
        _assign_strings(reachable, 0, {}, shapes, MAX_PLACEMENTS_PER_EVENT)
        for shape in shapes:
            fretted = [fret for _, (_, fret) in shape.items() if fret > 0]
            # ポジションの定義を一意にするため、最低フレットが position の形だけを採る
            if not fretted or min(fretted) != position:
                continue
            add_placement(shape, position)

    placements.sort(key=lambda item: event_base_cost(item, weights))
    return placements[:MAX_PLACEMENTS_PER_EVENT]


def _retarget(placement: EventPlacement, event: _Event) -> EventPlacement:
    """直前と同じ押さえ方を、このイベントの音符に割り当て直す（タイの継続音用）。"""
    remaining = list(event.noteIndices)
    pitches = list(event.midis)
    candidates = []
    for candidate in placement.candidates:
        position = pitches.index(candidate.pitch) if candidate.pitch in pitches else 0
        note_index = remaining.pop(position)
        pitches.pop(position)
        candidates.append(
            Candidate(
                noteIndex=note_index,
                stringIndex=candidate.stringIndex,
                fret=candidate.fret,
                finger=candidate.finger,
                handPosition=candidate.handPosition,
                pitch=candidate.pitch,
            )
        )
    return EventPlacement(
        candidates=tuple(candidates),
        handPosition=placement.handPosition,
        barreFret=placement.barreFret,
    )


def _beam_search(
    events: list[_Event], tuning: Tuning, weights: ScoringWeights
) -> tuple[list[EventPlacement], float, list["_Event"]]:
    beams = [_Beam(state=State.initial(), cost=0.0, node=_Node(placement=None, parent=None))]
    unplayable: list[_Event] = []

    for event in events:
        next_beams: list[_Beam] = []
        for beam in beams:
            if (
                event.tied
                and beam.node.placement is not None
                and len(beam.node.placement.candidates) == len(event.noteIndices)
            ):
                placements = [_retarget(beam.node.placement, event)]
            else:
                placements = generate_event_placements(event, tuning, beam.state, weights)

            for placement in placements:
                # タイで繋がれた音は弾き直さないため、コストを課さない
                base = 0.0 if event.tied else event_base_cost(placement, weights)
                transition = (
                    0.0
                    if event.tied
                    else event_transition_cost(
                        beam.state, placement, weights, event.availableBeats
                    )
                )
                scored = placement.with_costs(base, transition)
                next_beams.append(
                    _Beam(
                        state=beam.state.advance_event(scored),
                        cost=beam.cost + base + transition,
                        node=_Node(placement=scored, parent=beam.node),
                    )
                )

        if not next_beams:
            # この和音は6弦に収まらないなど、押さえられる形が見つからなかった
            unplayable.append(event)
            continue

        next_beams.sort(key=lambda item: item.cost)
        deduped: dict[tuple, _Beam] = {}
        for beam in next_beams:
            key = beam.state.key()
            if key not in deduped:
                deduped[key] = beam
        beams = list(deduped.values())[: weights.beam_width]

    best = min(beams, key=lambda item: item.cost)
    path: list[EventPlacement] = []
    node: _Node | None = best.node
    while node is not None and node.placement is not None:
        path.append(node.placement)
        node = node.parent
    path.reverse()
    return path, best.cost, unplayable


def _build_warnings(
    fingerings: list[Fingering],
    weights: ScoringWeights,
    available_beats: dict[int, float] | None = None,
) -> list[ConversionWarning]:
    warnings: list[ConversionWarning] = []
    available_beats = available_beats or {}

    # 同時に鳴る音をまとめ、イベント単位で前後を比較する
    events: list[list[Fingering]] = []
    for fingering in fingerings:
        if fingering.isRest or fingering.fret is None:
            continue
        if (
            events
            and events[-1][0].measureIndex == fingering.measureIndex
            and abs(events[-1][0].onsetBeat - fingering.onsetBeat) < 1e-9
        ):
            events[-1].append(fingering)
        else:
            events.append([fingering])

    def anchor(event: list[Fingering]) -> int | None:
        fretted = [item.fret for item in event if item.fret]
        return min(fretted) if fretted else None

    for previous, current in zip(events, events[1:]):
        head = current[0]
        if head.isTiedContinuation:
            continue
        location = f"{head.measureIndex + 1}小節目 {head.onsetBeat + 1:g}拍目"
        previous_position = previous[0].position
        current_position = head.position

        if anchor(previous) and anchor(current) and previous_position and current_position:
            shift = abs(current_position - previous_position)
            limit = allowed_shift(available_beats.get(head.noteIndex, 1.0), weights)
            if shift > limit:
                warnings.append(
                    ConversionWarning(
                        noteIndex=head.noteIndex,
                        measureIndex=head.measureIndex,
                        onsetBeat=head.onsetBeat,
                        kind="shift_too_fast",
                        message=(
                            f"{location}: 短い音価の間に{shift}フレットの移動が必要です"
                            f"（この音価で動かせる目安は{limit:.0f}フレットまで）"
                        ),
                    )
                )
            elif shift >= weights.large_shift_threshold:
                warnings.append(
                    ConversionWarning(
                        noteIndex=head.noteIndex,
                        measureIndex=head.measureIndex,
                        onsetBeat=head.onsetBeat,
                        kind="large_position_shift",
                        message=(
                            f"{location}: ポジション移動が大きくなっています"
                            f"（{previous_position}→{current_position}フレット）"
                        ),
                    )
                )

        if len(previous) == 1 and len(current) == 1:
            first, second = previous[0], current[0]
            if (
                first.stringIndex == second.stringIndex
                and first.fret
                and second.fret
                and abs(second.fret - first.fret) >= 5
            ):
                warnings.append(
                    ConversionWarning(
                        noteIndex=second.noteIndex,
                        measureIndex=second.measureIndex,
                        onsetBeat=second.onsetBeat,
                        kind="same_string_stretch",
                        message=(
                            f"{location}: 同弦で大きく運指が移動します"
                            f"（{first.fret}→{second.fret}フレット）"
                        ),
                    )
                )

    for event in events:
        head = event[0]
        location = f"{head.measureIndex + 1}小節目 {head.onsetBeat + 1:g}拍目"
        fretted = [item.fret for item in event if item.fret]
        if fretted and max(fretted) >= 15:
            warnings.append(
                ConversionWarning(
                    noteIndex=head.noteIndex,
                    measureIndex=head.measureIndex,
                    onsetBeat=head.onsetBeat,
                    kind="high_position",
                    message=(
                        f"{location}: 高いポジション（{max(fretted)}フレット）を使用しています"
                    ),
                )
            )
        if len(fretted) >= 2:
            span = max(fretted) - min(fretted)
            if span >= 4:
                warnings.append(
                    ConversionWarning(
                        noteIndex=head.noteIndex,
                        measureIndex=head.measureIndex,
                        onsetBeat=head.onsetBeat,
                        kind="wide_chord",
                        message=(
                            f"{location}: 和音の指板上の幅が{span}フレットあり、押さえるのが難しい可能性があります"
                        ),
                    )
                )
        if any(item.isBarre for item in event):
            warnings.append(
                ConversionWarning(
                    noteIndex=head.noteIndex,
                    measureIndex=head.measureIndex,
                    onsetBeat=head.onsetBeat,
                    kind="barre",
                    message=f"{location}: セーハ（{min(fretted)}フレット）が必要です",
                )
            )

    return warnings


def _absolute_onsets(notes: list[Note], measures: dict[int, MeasureInfo]) -> list[float]:
    """各音符の、曲頭からの通算拍位置を求める。"""
    measure_starts: dict[int, float] = {}
    cursor = 0.0
    for measure_index in sorted({note.measureIndex for note in notes}):
        measure_starts[measure_index] = cursor
        measure = measures.get(measure_index)
        cursor += measure.beats_per_measure if measure else 4.0
    return [measure_starts[note.measureIndex] + note.onsetBeat for note in notes]


def optimize(
    notes: list[Note],
    measures: list[MeasureInfo] | None = None,
    tuning: Tuning = STANDARD_TUNING,
    weights: ScoringWeights | None = None,
    notation_octave_shift: int = 0,
) -> OptimizationResult:
    """音符列から最適な運指を求める（設計書 8.1 基本フロー）。"""
    weights = weights or ScoringWeights()
    measure_map = {m.measureIndex: m for m in (measures or [])}
    onsets = _absolute_onsets(notes, measure_map)
    result = OptimizationResult()

    # 同じ拍位置の音をひとつのイベント（和音）にまとめる
    grouped: list[tuple[float, list[int], list[int]]] = []
    range_warnings: list[ConversionWarning] = []

    for index, note in enumerate(notes):
        midi = resolve_midi(note, measure_map, notation_octave_shift)
        if midi is None:
            continue
        fitted, octave_shift = _fit_into_range(midi, tuning)
        if octave_shift != 0:
            direction = "上" if octave_shift > 0 else "下"
            range_warnings.append(
                ConversionWarning(
                    noteIndex=index,
                    measureIndex=note.measureIndex,
                    onsetBeat=note.onsetBeat,
                    kind="out_of_range",
                    message=(
                        f"{note.measureIndex + 1}小節目 {note.onsetBeat + 1:g}拍目: "
                        f"ギターの音域外のため{abs(octave_shift)}オクターブ{direction}に移調しました"
                    ),
                )
            )
        if grouped and abs(grouped[-1][0] - onsets[index]) < 1e-9:
            grouped[-1][1].append(index)
            grouped[-1][2].append(fitted)
        else:
            grouped.append((onsets[index], [index], [fitted]))

    if not grouped:
        result.warnings = range_warnings
        result.fingerings = [
            Fingering(
                noteIndex=index,
                measureIndex=note.measureIndex,
                onsetBeat=note.onsetBeat,
                isRest=True,
            )
            for index, note in enumerate(notes)
        ]
        return result

    events: list[_Event] = []
    previous_onset: float | None = None
    previous_midis: tuple[int, ...] | None = None
    previous_tie = False

    for onset, indices, midis in grouped:
        available = (
            weights.shift_time_reference_beats
            if previous_onset is None
            else max(onset - previous_onset, 0.125)
        )
        tied = previous_tie and previous_midis == tuple(midis)
        events.append(
            _Event(
                noteIndices=tuple(indices),
                midis=tuple(midis),
                tied=tied,
                availableBeats=available,
            )
        )
        previous_onset = onset
        previous_midis = tuple(midis)
        previous_tie = all(notes[index].tieToNext for index in indices)

    path, total_cost, unplayable = _beam_search(events, tuning, weights)

    chosen: dict[int, tuple[Candidate, EventPlacement]] = {}
    for placement in path:
        for candidate in placement.candidates:
            chosen[candidate.noteIndex] = (candidate, placement)
    tied_map = {index: event.tied for event in events for index in event.noteIndices}
    beats_map = {
        event.noteIndices[0]: event.availableBeats for event in events
    }

    previous_position: int | None = None
    previous_event_key: tuple[int, float] | None = None

    for index, note in enumerate(notes):
        entry = chosen.get(index)
        if entry is None:
            result.fingerings.append(
                Fingering(
                    noteIndex=index,
                    measureIndex=note.measureIndex,
                    onsetBeat=note.onsetBeat,
                    isRest=True,
                )
            )
            continue

        candidate, placement = entry
        event_key = (note.measureIndex, note.onsetBeat)
        position = placement.handPosition
        hand_shift = 0
        if (
            not placement.is_all_open
            and position is not None
            and previous_position is not None
            and event_key != previous_event_key
        ):
            hand_shift = position - previous_position

        result.fingerings.append(
            Fingering(
                noteIndex=index,
                measureIndex=note.measureIndex,
                onsetBeat=note.onsetBeat,
                isRest=False,
                stringIndex=candidate.stringIndex,
                stringLabel=tuning.labels[candidate.stringIndex],
                fret=candidate.fret,
                finger=candidate.finger,
                position=position,
                handShift=hand_shift,
                isTiedContinuation=tied_map.get(index, False),
                isBarre=placement.barreFret is not None and candidate.fret == placement.barreFret,
                chordSize=len(placement.candidates),
            )
        )

        if event_key != previous_event_key:
            if not placement.is_all_open and position is not None:
                previous_position = position
            previous_event_key = event_key

    for event in unplayable:
        note = notes[event.noteIndices[0]]
        range_warnings.append(
            ConversionWarning(
                noteIndex=event.noteIndices[0],
                measureIndex=note.measureIndex,
                onsetBeat=note.onsetBeat,
                kind="unplayable_chord",
                message=(
                    f"{note.measureIndex + 1}小節目 {note.onsetBeat + 1:g}拍目: "
                    f"{len(event.midis)}音を同時に押さえられる形が見つかりませんでした"
                ),
            )
        )

    result.totalCost = total_cost
    result.warnings = range_warnings + _build_warnings(result.fingerings, weights, beats_map)
    return result
