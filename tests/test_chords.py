"""和音の運指最適化テスト（設計書 9.2 / 14.1）。"""

from __future__ import annotations

import time

import pytest

from app.domain.note import Duration, MeasureInfo, Note
from app.optimizer.fingering_optimizer import assign_fingers, optimize
from app.renderer.tab_renderer import render_details, render_text

# 実音のMIDIノート番号（記譜ではなく鳴る音）
CHORDS = {
    "E": [40, 47, 52, 56, 59, 64],
    "Am": [45, 52, 57, 60, 64],
    "C": [48, 52, 55, 60, 64],
    "G": [43, 47, 50, 55, 59, 67],
    "D": [50, 57, 62, 66],
    "F": [41, 48, 53, 57, 60, 65],
    "Bm": [47, 54, 59, 62, 66],
}

# 1弦→6弦の順。x は鳴らさない弦
STANDARD_SHAPES = {
    "E": "0 0 1 2 2 0",
    "Am": "0 1 2 2 0 x",
    "C": "0 1 0 2 3 x",
    "G": "3 0 0 0 2 3",
    "D": "2 3 2 0 x x",
    "F": "1 1 2 3 3 1",
    "Bm": "2 3 4 4 2 x",
}


def chord_notes(midis: list[int], measure: int = 0, beat: float = 0.0, duration=Duration.WHOLE):
    return [
        Note(
            midiNumber=midi,
            pitchName="C",
            octave=4,
            duration=duration,
            onsetBeat=beat,
            measureIndex=measure,
        )
        for midi in midis
    ]


def shape_of(result) -> str:
    frets = {f.stringIndex: f.fret for f in result.fingerings if not f.isRest}
    return " ".join(str(frets.get(index, "x")) for index in range(6))


class TestChordShapes:
    @pytest.mark.parametrize("name", sorted(CHORDS))
    def test_matches_standard_fingering(self, name):
        result = optimize(chord_notes(CHORDS[name]), [MeasureInfo(0)], notation_octave_shift=0)
        assert shape_of(result) == STANDARD_SHAPES[name]

    def test_each_note_gets_its_own_string(self):
        result = optimize(chord_notes(CHORDS["C"]), [MeasureInfo(0)], notation_octave_shift=0)
        strings = [f.stringIndex for f in result.fingerings]
        assert len(strings) == len(set(strings))

    def test_open_chord_needs_no_barre(self):
        result = optimize(chord_notes(CHORDS["E"]), [MeasureInfo(0)], notation_octave_shift=0)
        assert not any(f.isBarre for f in result.fingerings)

    def test_six_note_chord_uses_barre(self):
        result = optimize(chord_notes(CHORDS["F"]), [MeasureInfo(0)], notation_octave_shift=0)
        barred = [f for f in result.fingerings if f.isBarre]
        assert len(barred) >= 2
        assert all(f.finger == 1 for f in barred)
        assert any(w.kind == "barre" for w in result.warnings)

    def test_never_uses_more_than_four_fingers(self):
        for midis in CHORDS.values():
            result = optimize(chord_notes(midis), [MeasureInfo(0)], notation_octave_shift=0)
            fingers = {f.finger for f in result.fingerings if f.finger > 0}
            assert fingers.issubset({1, 2, 3, 4})

    def test_fret_span_stays_within_hand(self):
        for midis in CHORDS.values():
            result = optimize(chord_notes(midis), [MeasureInfo(0)], notation_octave_shift=0)
            frets = [f.fret for f in result.fingerings if f.fret]
            assert max(frets) - min(frets) <= 3

    def test_all_notes_of_the_chord_share_one_position(self):
        result = optimize(chord_notes(CHORDS["F"]), [MeasureInfo(0)], notation_octave_shift=0)
        positions = {f.position for f in result.fingerings}
        assert len(positions) == 1


class TestFingerAssignment:
    def test_lowest_fret_gets_the_index_finger(self):
        fingers, barre = assign_fingers([(2, 1), (4, 2), (3, 2)], position=1)
        assert fingers[2] == 1  # 3弦1フレット＝人差し指
        assert barre is None

    def test_same_fret_uses_separate_fingers(self):
        fingers, _ = assign_fingers([(4, 2), (3, 2)], position=2)
        assert fingers[4] != fingers[3]

    def test_barre_only_when_fingers_run_out(self):
        five_notes = [(5, 1), (1, 1), (0, 1), (4, 3), (3, 3)]
        fingers, barre = assign_fingers(five_notes, position=1)
        assert barre == 1
        assert fingers[5] == fingers[1] == fingers[0] == 1

    def test_returns_none_when_unplayable(self):
        # 5音以上あってセーハもできない（最低フレットが1音だけ）形
        assert assign_fingers([(5, 1), (4, 2), (3, 3), (2, 4), (1, 5)], position=1) is None


class TestChordProgression:
    def make_progression(self, names: list[str], duration=Duration.WHOLE):
        notes = []
        for measure, name in enumerate(names):
            notes.extend(chord_notes(CHORDS[name], measure=measure))
        return notes, [MeasureInfo(index) for index in range(len(names))]

    def test_open_chord_progression_stays_in_first_position(self):
        notes, measures = self.make_progression(["C", "Am", "E"])
        result = optimize(notes, measures, notation_octave_shift=0)
        positions = {f.position for f in result.fingerings if f.fret}
        assert positions <= {1, 2}

    def test_progression_renders_as_stacked_columns(self):
        notes, measures = self.make_progression(["C", "G"])
        result = optimize(notes, measures, notation_octave_shift=0)
        tab = render_text(notes, result.fingerings)
        lines = [line for line in tab.splitlines() if line]
        assert len(lines) == 6
        # 各小節に和音1つ分の列があり、複数弦に数字が乗る
        assert sum(1 for line in lines if any(ch.isdigit() for ch in line.split("|", 1)[1])) >= 5

    def test_details_list_every_note_of_the_chord(self):
        notes, measures = self.make_progression(["F"])
        result = optimize(notes, measures, notation_octave_shift=0)
        details = render_details(notes, result.fingerings)
        assert "和音" in details
        assert "セーハ" in details
        assert details.count("弦") >= 6

    def test_melody_and_chords_can_be_mixed(self):
        notes = chord_notes(CHORDS["C"], measure=0, beat=0.0, duration=Duration.HALF)
        notes += [
            Note(midiNumber=64, pitchName="E", octave=4, duration=Duration.QUARTER, onsetBeat=2.0),
            Note(midiNumber=65, pitchName="F", octave=4, duration=Duration.QUARTER, onsetBeat=3.0),
        ]
        result = optimize(notes, [MeasureInfo(0)], notation_octave_shift=0)
        assert len([f for f in result.fingerings if f.chordSize > 1]) == len(CHORDS["C"])
        assert len([f for f in result.fingerings if f.chordSize == 1]) == 2

    def test_performance_on_long_progression(self):
        names = ["C", "G", "Am", "F"] * 8
        notes, measures = self.make_progression(names)
        started = time.perf_counter()
        optimize(notes, measures, notation_octave_shift=0)
        assert time.perf_counter() - started < 5.0
