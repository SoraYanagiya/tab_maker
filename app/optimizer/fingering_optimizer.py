"""運指最適化エンジン（設計書 8. アルゴリズム設計）。

候補生成 → スコア計算 → ビームサーチで最小コスト経路を選ぶ。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import NamedTuple

from ..domain.candidate import Candidate
from ..domain.note import Accidental, MeasureInfo, Note, midi_number
from ..domain.state import State
from ..domain.tuning import FINGER_COUNT, MAX_FRET, STANDARD_TUNING, Tuning
from .scoring import ScoringWeights, allowed_shift, base_cost, transition_cost


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


class _PlayableNote(NamedTuple):
    noteIndex: int
    midi: int
    tied: bool
    availableBeats: float


@dataclass
class _Node:
    candidate: Candidate | None
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
                )
            )
    return candidates


def _beam_search(
    playable: list["_PlayableNote"],
    tuning: Tuning,
    weights: ScoringWeights,
) -> tuple[list[Candidate], float]:
    """演奏対象の音の列に対して最適経路を探索する。"""
    beams = [_Beam(state=State.initial(), cost=0.0, node=_Node(candidate=None, parent=None))]

    for note_index, midi, tied, available_beats in playable:
        next_beams: list[_Beam] = []
        for beam in beams:
            if tied and beam.node.candidate is not None:
                previous = beam.node.candidate
                candidates = [
                    Candidate(
                        noteIndex=note_index,
                        stringIndex=previous.stringIndex,
                        fret=previous.fret,
                        finger=previous.finger,
                        handPosition=previous.handPosition,
                    )
                ]
            else:
                candidates = generate_candidates(note_index, midi, tuning, beam.state)

            for candidate in candidates:
                # タイで繋がれた音は再度弾き直さないため、コストを課さない
                base = 0.0 if tied else base_cost(candidate, weights)
                transition = (
                    0.0
                    if tied
                    else transition_cost(beam.state, candidate, weights, available_beats)
                )
                scored = Candidate(
                    noteIndex=candidate.noteIndex,
                    stringIndex=candidate.stringIndex,
                    fret=candidate.fret,
                    finger=candidate.finger,
                    handPosition=candidate.handPosition,
                    baseCost=base,
                    transitionCost=transition,
                )
                next_beams.append(
                    _Beam(
                        state=beam.state.advance(scored),
                        cost=beam.cost + base + transition,
                        node=_Node(candidate=scored, parent=beam.node),
                    )
                )

        if not next_beams:
            continue

        next_beams.sort(key=lambda b: b.cost)
        deduped: dict[tuple, _Beam] = {}
        for beam in next_beams:
            key = (
                beam.state.previousString,
                beam.state.previousFret,
                beam.state.previousFinger,
                beam.state.handPosition,
            )
            if key not in deduped:
                deduped[key] = beam
        beams = list(deduped.values())[: weights.beam_width]

    best = min(beams, key=lambda b: b.cost)
    path: list[Candidate] = []
    node: _Node | None = best.node
    while node is not None and node.candidate is not None:
        path.append(node.candidate)
        node = node.parent
    path.reverse()
    return path, best.cost


def _build_warnings(
    fingerings: list[Fingering],
    weights: ScoringWeights,
    available_beats: dict[int, float] | None = None,
) -> list[ConversionWarning]:
    warnings: list[ConversionWarning] = []
    played = [f for f in fingerings if not f.isRest and f.fret is not None]
    available_beats = available_beats or {}

    for previous, current in zip(played, played[1:]):
        if current.isTiedContinuation:
            continue
        if (
            previous.fret
            and current.fret
            and previous.position is not None
            and current.position is not None
        ):
            shift = abs(current.position - previous.position)
            location = f"{current.measureIndex + 1}小節目 {current.onsetBeat + 1:g}拍目"
            limit = allowed_shift(available_beats.get(current.noteIndex, 1.0), weights)
            if shift > limit:
                warnings.append(
                    ConversionWarning(
                        noteIndex=current.noteIndex,
                        measureIndex=current.measureIndex,
                        onsetBeat=current.onsetBeat,
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
                        noteIndex=current.noteIndex,
                        measureIndex=current.measureIndex,
                        onsetBeat=current.onsetBeat,
                        kind="large_position_shift",
                        message=(
                            f"{location}: ポジション移動が大きくなっています"
                            f"（{previous.position}→{current.position}フレット）"
                        ),
                    )
                )
        if (
            previous.stringIndex == current.stringIndex
            and previous.fret is not None
            and current.fret is not None
            and previous.fret > 0
            and current.fret > 0
            and abs(current.fret - previous.fret) >= 5
        ):
            warnings.append(
                ConversionWarning(
                    noteIndex=current.noteIndex,
                    measureIndex=current.measureIndex,
                    onsetBeat=current.onsetBeat,
                    kind="same_string_stretch",
                    message=(
                        f"{current.measureIndex + 1}小節目 {current.onsetBeat + 1:g}拍目: "
                        f"同弦で大きく運指が移動します"
                        f"（{previous.fret}→{current.fret}フレット）"
                    ),
                )
            )

    for fingering in played:
        if fingering.fret is not None and fingering.fret >= 15:
            warnings.append(
                ConversionWarning(
                    noteIndex=fingering.noteIndex,
                    measureIndex=fingering.measureIndex,
                    onsetBeat=fingering.onsetBeat,
                    kind="high_position",
                    message=(
                        f"{fingering.measureIndex + 1}小節目 {fingering.onsetBeat + 1:g}拍目: "
                        f"高いポジション（{fingering.fret}フレット）を使用しています"
                    ),
                )
            )

    return warnings


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
    result = OptimizationResult()

    onsets = _absolute_onsets(notes, measure_map)

    playable: list[_PlayableNote] = []
    range_warnings: list[ConversionWarning] = []
    previous_midi: int | None = None
    previous_onset: float | None = None
    previous_tie = False

    for index, note in enumerate(notes):
        midi = resolve_midi(note, measure_map, notation_octave_shift)
        if midi is None:
            previous_tie = False
            previous_midi = None
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
        tied = previous_tie and previous_midi == fitted
        # 直前に弾いた音からこの音までの時間が、手を動かせる余裕になる（設計書 8.3.1）
        if previous_onset is None:
            available_beats = weights.shift_time_reference_beats
        else:
            available_beats = max(onsets[index] - previous_onset, 0.125)
        playable.append(_PlayableNote(index, fitted, tied, available_beats))
        previous_midi = fitted
        previous_onset = onsets[index]
        previous_tie = note.tieToNext

    if not playable:
        result.warnings = range_warnings
        return result

    path, total_cost = _beam_search(playable, tuning, weights)
    chosen = {candidate.noteIndex: candidate for candidate in path}
    tied_map = {item.noteIndex: item.tied for item in playable}
    beats_map = {item.noteIndex: item.availableBeats for item in playable}

    previous_position: int | None = None
    for index, note in enumerate(notes):
        candidate = chosen.get(index)
        if candidate is None:
            result.fingerings.append(
                Fingering(
                    noteIndex=index,
                    measureIndex=note.measureIndex,
                    onsetBeat=note.onsetBeat,
                    isRest=True,
                )
            )
            continue
        position = candidate.handPosition
        hand_shift = 0
        if not candidate.is_open and position is not None and previous_position is not None:
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
            )
        )
        if not candidate.is_open and position is not None:
            previous_position = position

    result.totalCost = total_cost
    result.warnings = range_warnings + _build_warnings(result.fingerings, weights, beats_map)
    return result


def _absolute_onsets(notes: list[Note], measures: dict[int, MeasureInfo]) -> list[float]:
    """各音符の、曲頭からの通算拍位置を求める。"""
    measure_starts: dict[int, float] = {}
    cursor = 0.0
    for measure_index in sorted({note.measureIndex for note in notes}):
        measure_starts[measure_index] = cursor
        measure = measures.get(measure_index)
        cursor += measure.beats_per_measure if measure else 4.0
    return [measure_starts[note.measureIndex] + note.onsetBeat for note in notes]
