from __future__ import annotations

import pytest

MUSICXML = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 3.1 Partwise//EN"
  "http://www.musicxml.org/dtds/partwise.dtd">
<score-partwise version="3.1">
  <part-list>
    <score-part id="P1"><part-name>Melody</part-name></score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>1</divisions>
        <key><fifths>0</fifths></key>
        <time><beats>4</beats><beat-type>4</beat-type></time>
        <clef><sign>G</sign><line>2</line></clef>
      </attributes>
      <note><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration><type>quarter</type></note>
      <note><pitch><step>D</step><octave>4</octave></pitch><duration>1</duration><type>quarter</type></note>
      <note><pitch><step>E</step><octave>4</octave></pitch><duration>1</duration><type>quarter</type></note>
      <note><rest/><duration>1</duration><type>quarter</type></note>
    </measure>
  </part>
</score-partwise>
"""


@pytest.fixture
def musicxml_bytes() -> bytes:
    return MUSICXML.encode("utf-8")


MULTI_PART_MUSICXML = """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="3.1">
  <part-list>
    <score-part id="P1"><part-name>Bass</part-name></score-part>
    <score-part id="P2"><part-name>Lead Guitar</part-name></score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>1</divisions>
        <key><fifths>0</fifths></key>
        <time><beats>4</beats><beat-type>4</beat-type></time>
        <clef><sign>F</sign><line>4</line></clef>
      </attributes>
      <note><pitch><step>C</step><octave>2</octave></pitch><duration>1</duration><type>quarter</type></note>
      <note><pitch><step>C</step><octave>2</octave></pitch><duration>1</duration><type>quarter</type></note>
      <note><pitch><step>C</step><octave>2</octave></pitch><duration>1</duration><type>quarter</type></note>
      <note><pitch><step>C</step><octave>2</octave></pitch><duration>1</duration><type>quarter</type></note>
    </measure>
  </part>
  <part id="P2">
    <measure number="1">
      <attributes>
        <divisions>1</divisions>
        <key><fifths>0</fifths></key>
        <time><beats>4</beats><beat-type>4</beat-type></time>
        <clef><sign>G</sign><line>2</line></clef>
      </attributes>
      <note><pitch><step>C</step><octave>5</octave></pitch><duration>1</duration><type>quarter</type></note>
      <note><pitch><step>D</step><octave>5</octave></pitch><duration>1</duration><type>quarter</type></note>
      <note><pitch><step>E</step><octave>5</octave></pitch><duration>1</duration><type>quarter</type></note>
      <note><pitch><step>F</step><octave>5</octave></pitch><duration>1</duration><type>quarter</type></note>
    </measure>
  </part>
</score-partwise>
"""


@pytest.fixture
def multi_part_musicxml_bytes() -> bytes:
    return MULTI_PART_MUSICXML.encode("utf-8")


@pytest.fixture
def percussion_midi_bytes() -> bytes:
    """打楽器トラック(General MIDIのチャンネル10)＋通常の旋律トラックを持つMIDI。"""
    import io

    import mido

    mid = mido.MidiFile(type=1, ticks_per_beat=480)

    meta = mido.MidiTrack()
    meta.append(mido.MetaMessage("set_tempo", tempo=500000, time=0))
    meta.append(mido.MetaMessage("time_signature", numerator=4, denominator=4, time=0))
    mid.tracks.append(meta)

    def make_track(name: str, pitches: list[int], channel: int) -> "mido.MidiTrack":
        track = mido.MidiTrack()
        track.append(mido.MetaMessage("track_name", name=name, time=0))
        for pitch in pitches:
            track.append(mido.Message("note_on", note=pitch, velocity=80, time=0, channel=channel))
            track.append(mido.Message("note_off", note=pitch, velocity=64, time=480, channel=channel))
        return track

    mid.tracks.append(make_track("Drums", [36, 38, 36, 38], channel=9))
    mid.tracks.append(make_track("Lead Guitar", [72, 74, 76, 77], channel=0))

    buffer = io.BytesIO()
    mid.save(file=buffer)
    return buffer.getvalue()
