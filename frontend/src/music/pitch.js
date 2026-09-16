export const STEPS = ['C', 'D', 'E', 'F', 'G', 'A', 'B']
const STEP_SEMITONES = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 }
const SHARP_ORDER = ['F', 'C', 'G', 'D', 'A', 'E', 'B']
const FLAT_ORDER = ['B', 'E', 'A', 'D', 'G', 'C', 'F']

export const KEY_FIFTHS = {
  C: 0, G: 1, D: 2, A: 3, E: 4, B: 5, 'F#': 6, 'C#': 7,
  F: -1, Bb: -2, Eb: -3, Ab: -4, Db: -5, Gb: -6, Cb: -7,
  Am: 0, Em: 1, Bm: 2, 'F#m': 3, 'C#m': 4, 'G#m': 5, 'D#m': 6, 'A#m': 7,
  Dm: -1, Gm: -2, Cm: -3, Fm: -4, Bbm: -5, Ebm: -6, Abm: -7,
}

export const KEY_OPTIONS = [
  'C', 'G', 'D', 'A', 'E', 'B', 'F#', 'C#',
  'F', 'Bb', 'Eb', 'Ab', 'Db', 'Gb', 'Cb',
  'Am', 'Em', 'Bm', 'F#m', 'C#m', 'G#m', 'D#m', 'A#m',
  'Dm', 'Gm', 'Cm', 'Fm', 'Bbm', 'Ebm', 'Abm',
]

export const TIME_OPTIONS = ['4/4', '3/4', '2/4', '6/8', '5/4', '2/2']

export const DURATIONS = [
  { id: 'whole', label: '全音符', vex: 'w', beats: 4 },
  { id: 'half', label: '2分音符', vex: 'h', beats: 2 },
  { id: 'quarter', label: '4分音符', vex: 'q', beats: 1 },
  { id: 'eighth', label: '8分音符', vex: '8', beats: 0.5 },
  { id: 'sixteenth', label: '16分音符', vex: '16', beats: 0.25 },
]

export const ACCIDENTALS = [
  { id: 'none', label: '♮なし', symbol: '' },
  { id: 'sharp', label: 'シャープ', symbol: '♯' },
  { id: 'flat', label: 'フラット', symbol: '♭' },
  { id: 'natural', label: 'ナチュラル', symbol: '♮' },
]

const ACCIDENTAL_ALTER = { none: 0, sharp: 1, flat: -1, natural: 0 }
const ACCIDENTAL_GLYPH = { sharp: '#', flat: 'b', natural: 'n' }

export function keyAlteration(step, keySignature) {
  const fifths = KEY_FIFTHS[keySignature] ?? 0
  if (fifths > 0 && SHARP_ORDER.slice(0, fifths).includes(step)) return 1
  if (fifths < 0 && FLAT_ORDER.slice(0, -fifths).includes(step)) return -1
  return 0
}

export function midiFromPitch(step, octave, accidental = 'none', keySignature = 'C') {
  const base = STEP_SEMITONES[step] + (octave + 1) * 12
  if (accidental === 'none') return base + keyAlteration(step, keySignature)
  return base + ACCIDENTAL_ALTER[accidental]
}

/** C0 を 0 とした全音階上の位置。五線譜の縦位置と1対1で対応する。 */
export function diatonicIndex(step, octave) {
  return octave * 7 + STEPS.indexOf(step)
}

const SHARP_SPELLING = [
  ['C', 'none'], ['C', 'sharp'], ['D', 'none'], ['D', 'sharp'], ['E', 'none'], ['F', 'none'],
  ['F', 'sharp'], ['G', 'none'], ['G', 'sharp'], ['A', 'none'], ['A', 'sharp'], ['B', 'none'],
]
const FLAT_SPELLING = [
  ['C', 'none'], ['D', 'flat'], ['D', 'none'], ['E', 'flat'], ['E', 'none'], ['F', 'none'],
  ['G', 'flat'], ['G', 'none'], ['A', 'flat'], ['A', 'none'], ['B', 'flat'], ['B', 'none'],
]

/** MIDIノート番号を、調号に合った音名・オクターブ・臨時記号に読み替える。 */
export function pitchFromMidi(midi, keySignature = 'C') {
  const table = (KEY_FIFTHS[keySignature] ?? 0) < 0 ? FLAT_SPELLING : SHARP_SPELLING
  const [step, accidental] = table[((midi % 12) + 12) % 12]
  const octave = Math.floor(midi / 12) - 1
  // 調号だけで同じ音になるなら、臨時記号は書かない
  if (midiFromPitch(step, octave, 'none', keySignature) === midi) {
    return { pitchName: step, octave, accidental: 'none' }
  }
  return { pitchName: step, octave, accidental }
}

export function pitchFromDiatonic(index) {
  return { step: STEPS[((index % 7) + 7) % 7], octave: Math.floor(index / 7) }
}

/**
 * 鍵盤入力の配列。オクターブ+完全4度（18半音）ぶんを白鍵11・黒鍵7で並べる。
 * PCキーボードのタイピングピアノ（A S D F G H J K L ; ' が白鍵、
 * W E T Y U O P が黒鍵）と、画面上の仮想鍵盤の両方で共有する。
 */
export const PIANO_WHITE_KEYS = [
  { key: 'a', semitone: 0 },
  { key: 's', semitone: 2 },
  { key: 'd', semitone: 4 },
  { key: 'f', semitone: 5 },
  { key: 'g', semitone: 7 },
  { key: 'h', semitone: 9 },
  { key: 'j', semitone: 11 },
  { key: 'k', semitone: 12 },
  { key: 'l', semitone: 14 },
  { key: ';', semitone: 16 },
  { key: "'", semitone: 17 },
]

export const PIANO_BLACK_KEYS = [
  { key: 'w', semitone: 1, afterWhiteIndex: 0 },
  { key: 'e', semitone: 3, afterWhiteIndex: 1 },
  { key: 't', semitone: 6, afterWhiteIndex: 3 },
  { key: 'y', semitone: 8, afterWhiteIndex: 4 },
  { key: 'u', semitone: 10, afterWhiteIndex: 5 },
  { key: 'o', semitone: 13, afterWhiteIndex: 7 },
  { key: 'p', semitone: 15, afterWhiteIndex: 8 },
]

export const PIANO_KEY_TO_SEMITONE = Object.fromEntries(
  [...PIANO_WHITE_KEYS, ...PIANO_BLACK_KEYS].map(({ key, semitone }) => [key, semitone]),
)

export const PIANO_MIN_OCTAVE = 0
export const PIANO_MAX_OCTAVE = 7

/** 鍵盤オクターブと半音オフセットから、実際のMIDIノート番号を求める。 */
export function pianoMidi(octave, semitone) {
  return (octave + 1) * 12 + semitone
}

export function durationBeats(note) {
  const base = DURATIONS.find((d) => d.id === note.duration)?.beats ?? 1
  return note.isDotted ? base * 1.5 : base
}

export function beatsPerMeasure(measure) {
  const [numerator, denominator] = (measure?.timeSignature ?? '4/4').split('/').map(Number)
  return (numerator * 4) / denominator
}

export function vexDuration(note) {
  const vex = DURATIONS.find((d) => d.id === note.duration)?.vex ?? 'q'
  return note.isRest ? `${vex}r` : vex
}

export function vexKey(note) {
  if (note.isRest) return 'b/4'
  const glyph = ACCIDENTAL_GLYPH[note.accidental] ?? ''
  return `${note.pitchName.toLowerCase()}${glyph}/${note.octave}`
}

export function accidentalGlyph(accidental) {
  return ACCIDENTAL_GLYPH[accidental] ?? null
}

export function pitchLabel(note) {
  if (note.isRest) return '休符'
  const symbol = ACCIDENTALS.find((a) => a.id === note.accidental)?.symbol ?? ''
  return `${note.pitchName}${symbol}${note.octave}`
}
