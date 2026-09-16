"""運指最適化のテスト（設計書 13）。"""

from __future__ import annotations

import pytest

from app.domain.candidate import Candidate
from app.domain.note import Accidental, Duration, MeasureInfo, Note, midi_number
from app.domain.state import State
from app.domain.tuning import STANDARD_TUNING
from app.optimizer.fingering_optimizer import allowed_shift, generate_candidates, optimize
from app.optimizer.scoring import ScoringWeights, transition_cost
from app.renderer.tab_renderer import render_text

DURATION_BEATS = {
    Duration.SIXTEENTH: 0.25,
    Duration.EIGHTH: 0.5,
    Duration.QUARTER: 1.0,
    Duration.HALF: 2.0,
    Duration.WHOLE: 4.0,
}


def make_notes(midis: list[int], beats_per_measure: int = 4) -> list[Note]:
    return [
        Note(
            midiNumber=midi,
            pitchName="C",
            octave=4,
            onsetBeat=float(index % beats_per_measure),
            measureIndex=index // beats_per_measure,
        )
        for index, midi in enumerate(midis)
    ]


def timed_notes(midis: list[int], duration: Duration) -> list[Note]:
    """指定した音価で並べた音符列を作る（拍位置・小節番号を正しく割り当てる）。"""
    beats = DURATION_BEATS[duration]
    notes: list[Note] = []
    position = 0.0
    measure = 0
    for midi in midis:
        if position >= 4.0:
            position -= 4.0
            measure += 1
        notes.append(
            Note(
                midiNumber=midi,
                pitchName="C",
                octave=4,
                duration=duration,
                onsetBeat=position,
                measureIndex=measure,
            )
        )
        position += beats
    return notes


def measures_for(notes: list[Note]) -> list[MeasureInfo]:
    return [MeasureInfo(index) for index in sorted({note.measureIndex for note in notes})]


class TestPitchResolution:
    def test_midi_number_uses_key_signature(self):
        # ト長調では F は自動的に F#
        assert midi_number("F", 4, Accidental.NONE, "G") == 66
        assert midi_number("F", 4, Accidental.NONE, "C") == 65

    def test_explicit_accidental_overrides_key(self):
        assert midi_number("F", 4, Accidental.NATURAL, "G") == 65
        assert midi_number("F", 4, Accidental.SHARP, "C") == 66

    def test_dotted_duration_beats(self):
        note = Note(midiNumber=60, pitchName="C", octave=4, duration=Duration.QUARTER, isDotted=True)
        assert note.beats == 1.5


class TestCandidateGeneration:
    def test_every_playable_string_is_offered(self):
        # E4(64) は 1弦開放 / 2弦5f / 3弦9f / 4弦14f / 5弦19f / 6弦24f
        candidates = generate_candidates(0, 64, STANDARD_TUNING, State.initial())
        strings = {c.stringIndex for c in candidates}
        assert strings == {0, 1, 2, 3, 4, 5}

    def test_open_string_has_no_finger(self):
        candidates = generate_candidates(0, 64, STANDARD_TUNING, State.initial())
        open_candidates = [c for c in candidates if c.stringIndex == 0]
        assert len(open_candidates) == 1
        assert open_candidates[0].fret == 0
        assert open_candidates[0].finger == 0

    def test_fretted_note_offers_four_hand_positions(self):
        # 2弦5f (E4) は人差し指〜小指のどれで押さえるかで4通り
        candidates = generate_candidates(0, 64, STANDARD_TUNING, State.initial())
        second_string = [c for c in candidates if c.stringIndex == 1]
        assert {c.finger for c in second_string} == {1, 2, 3, 4}
        assert {c.handPosition for c in second_string} == {2, 3, 4, 5}

    def test_out_of_range_note_is_transposed_with_warning(self):
        # C1(24) はギターの音域外
        result = optimize([Note(midiNumber=24, pitchName="C", octave=1)])
        assert any(w.kind == "out_of_range" for w in result.warnings)
        assert result.fingerings[0].fret is not None


class TestOpenStringRule:
    """開放弦はポジション移動の制限に入らない（設計書 7.4）。"""

    def test_open_string_transition_has_no_position_cost(self):
        weights = ScoringWeights()
        # 12フレットで押さえた直後に開放弦を弾く
        state = State.initial().advance(Candidate(0, 1, 12, 1, 12))
        open_candidate = Candidate(1, 0, 0, 0, None)
        cost = transition_cost(state, open_candidate, weights)
        # 弦移動のコストのみが残る
        assert cost == weights.string_change

    def test_position_carries_over_across_open_string(self):
        state = State.initial().advance(Candidate(0, 1, 7, 1, 7))
        state = state.advance(Candidate(1, 0, 0, 0, None))
        assert state.handPosition == 7

    def test_fretted_transition_still_costs_position_change(self):
        weights = ScoringWeights()
        state = State.initial().advance(Candidate(0, 1, 2, 2, 1))
        far = Candidate(1, 1, 12, 1, 12)
        cost = transition_cost(state, far, weights)
        assert cost > weights.string_change

    def test_open_string_does_not_trigger_shift_warning(self):
        # 実音 E2(40, 6弦開放) と E4(64, 1弦開放) の往復は手の移動を伴わない
        result = optimize(make_notes([40, 64, 40, 64]), notation_octave_shift=0)
        assert [f.fret for f in result.fingerings] == [0, 0, 0, 0]
        assert not [w for w in result.warnings if w.kind == "large_position_shift"]


class TestHandSpeedLimit:
    """短い時間では5フレット以内しか手を動かせない（設計書 8.3.1）。"""

    def test_allowed_shift_grows_with_available_time(self):
        weights = ScoringWeights()
        assert allowed_shift(0.25, weights) == 5  # 16分音符
        assert allowed_shift(0.5, weights) == 5  # 8分音符
        assert allowed_shift(1.0, weights) == 5  # 4分音符
        assert allowed_shift(2.0, weights) == 10  # 2分音符
        assert allowed_shift(4.0, weights) == 20  # 全音符

    def test_shift_beyond_limit_is_heavily_penalised_when_fast(self):
        weights = ScoringWeights()
        state = State.initial().advance(Candidate(0, 1, 2, 2, 1))
        far = Candidate(1, 1, 12, 1, 12)
        fast = transition_cost(state, far, weights, available_beats=0.5)
        slow = transition_cost(state, far, weights, available_beats=4.0)
        assert fast > slow
        assert fast - slow == pytest.approx(
            weights.infeasible_shift_penalty * (11 - allowed_shift(0.5, weights))
        )

    def test_shift_within_limit_costs_the_same_regardless_of_time(self):
        weights = ScoringWeights()
        state = State.initial().advance(Candidate(0, 1, 2, 2, 1))
        near = Candidate(1, 1, 5, 1, 5)
        assert transition_cost(state, near, weights, 0.25) == transition_cost(
            state, near, weights, 4.0
        )

    def test_fast_leap_warns_that_the_hand_cannot_move_in_time(self):
        notes = timed_notes([41, 76, 41, 76], Duration.EIGHTH)
        result = optimize(notes, measures_for(notes), notation_octave_shift=0)
        assert any(w.kind == "shift_too_fast" for w in result.warnings)

    def test_same_leap_is_acceptable_with_long_notes(self):
        notes = timed_notes([41, 76, 41, 76], Duration.WHOLE)
        result = optimize(notes, measures_for(notes), notation_octave_shift=0)
        assert not any(w.kind == "shift_too_fast" for w in result.warnings)

    def test_open_strings_are_exempt_from_the_speed_limit(self):
        # 6弦開放(40) と 1弦開放(64) の16分音符での往復は手を動かさない
        notes = timed_notes([40, 64, 40, 64], Duration.SIXTEENTH)
        result = optimize(notes, measures_for(notes), notation_octave_shift=0)
        assert not any(w.kind == "shift_too_fast" for w in result.warnings)


class TestFingeringQuality:
    def test_open_position_c_major_scale(self):
        # ギター記譜の C4..C5（実音 C3..C4）は開放ポジションが定番運指
        result = optimize(make_notes([60, 62, 64, 65, 67, 69, 71, 72]), notation_octave_shift=-1)
        placements = [(f.stringIndex, f.fret) for f in result.fingerings]
        assert placements == [(4, 3), (3, 0), (3, 2), (3, 3), (2, 0), (2, 2), (1, 0), (1, 1)]

    def test_stays_in_one_position_for_nearby_notes(self):
        # 同じポジションで弾ける音列では手を動かさない
        result = optimize(make_notes([67, 69, 71, 72, 71, 69]), notation_octave_shift=0)
        positions = {f.position for f in result.fingerings if f.fret and f.position}
        assert len(positions) <= 1

    def test_fingers_stay_within_four(self):
        result = optimize(make_notes([55, 57, 59, 60, 62, 64, 65, 67]), notation_octave_shift=0)
        for fingering in result.fingerings:
            assert 0 <= fingering.finger <= 4

    def test_rests_are_preserved(self):
        notes = make_notes([60, 62])
        notes.insert(1, Note(midiNumber=None, pitchName="C", octave=4, isRest=True, measureIndex=0))
        result = optimize(notes)
        assert [f.isRest for f in result.fingerings] == [False, True, False]

    def test_tied_note_reuses_same_placement(self):
        notes = make_notes([60, 60])
        notes[0].tieToNext = True
        result = optimize(notes)
        first, second = result.fingerings
        assert (first.stringIndex, first.fret) == (second.stringIndex, second.fret)
        assert second.isTiedContinuation

    def test_large_shift_produces_warning(self):
        # 実音で低音から高音へ跳躍させ、ポジション移動を強制する
        result = optimize(make_notes([41, 76]), notation_octave_shift=0)
        assert any(
            w.kind in ("large_position_shift", "shift_too_fast") for w in result.warnings
        )

    @pytest.mark.parametrize("length", [50, 200])
    def test_performance_on_long_melodies(self, length):
        import time

        midis = [60 + (i * 2) % 12 for i in range(length)]
        started = time.perf_counter()
        optimize(make_notes(midis))
        assert time.perf_counter() - started < 2.0


class TestRenderer:
    def test_text_tab_has_six_lines_per_block(self):
        notes = make_notes([60, 62, 64, 65])
        result = optimize(notes)
        lines = [line for line in render_text(notes, result.fingerings).splitlines() if line]
        assert len(lines) == 6
        assert lines[0].lstrip().startswith("e|")
        assert lines[-1].lstrip().startswith("E|")

    def test_measures_are_separated_by_barlines(self):
        notes = make_notes([60, 62, 64, 65, 67, 69, 71, 72])
        result = optimize(notes)
        assert render_text(notes, result.fingerings).splitlines()[0].count("|") == 3

    def test_tied_note_is_parenthesised(self):
        notes = make_notes([60, 60])
        notes[0].tieToNext = True
        result = optimize(notes)
        assert "(" in render_text(notes, result.fingerings)
