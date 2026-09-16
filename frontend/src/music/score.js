import { beatsPerMeasure, durationBeats, midiFromPitch, pitchFromMidi } from './pitch'

let idCounter = 0
export function nextNoteId() {
  idCounter += 1
  return `n${idCounter}`
}

export function emptyScore() {
  return {
    notes: [],
    measures: [
      { measureIndex: 0, keySignature: 'C', timeSignature: '4/4' },
      { measureIndex: 1, keySignature: 'C', timeSignature: '4/4' },
    ],
  }
}

export function makeNote(partial = {}) {
  const note = {
    id: nextNoteId(),
    pitchName: 'B',
    octave: 4,
    accidental: 'none',
    duration: 'quarter',
    isDotted: false,
    tieToNext: false,
    isRest: false,
    // 直前の音と同時に鳴る（和音の構成音）
    inChord: false,
    measureIndex: 0,
    onsetBeat: 0,
    ...partial,
  }
  return { ...note, midiNumber: note.isRest ? null : note.midiNumber ?? null }
}

/**
 * 音符列を先頭から詰め直し、小節番号と拍位置を振り直す。
 * 小節に収まらない音符は次の小節へ送られる（記譜ソフトと同じ挙動）。
 * inChord が立っている音符は、直前の音符と同じ拍位置に重ねる（和音）。
 */
export function reflow(score) {
  const measures = score.measures.map((measure, index) => ({ ...measure, measureIndex: index }))
  const ensureMeasure = (index) => {
    while (measures.length <= index) {
      const previous = measures[measures.length - 1]
      measures.push({
        measureIndex: measures.length,
        keySignature: previous?.keySignature ?? 'C',
        timeSignature: previous?.timeSignature ?? '4/4',
      })
    }
    return measures[index]
  }

  let measureIndex = 0
  let beat = 0
  let lastEvent = null
  const notes = score.notes.map((note, index) => {
    if (note.inChord && index > 0 && lastEvent) {
      // 和音の構成音は、直前の音と同じ位置・同じ音価で鳴る
      return {
        ...note,
        duration: lastEvent.duration,
        isDotted: lastEvent.isDotted,
        measureIndex: lastEvent.measureIndex,
        onsetBeat: lastEvent.onsetBeat,
      }
    }
    const beats = durationBeats(note)
    let capacity = beatsPerMeasure(ensureMeasure(measureIndex))
    if (beat > 0 && beat + beats > capacity + 1e-9) {
      measureIndex += 1
      beat = 0
      capacity = beatsPerMeasure(ensureMeasure(measureIndex))
    }
    const placed = { ...note, measureIndex, onsetBeat: beat }
    lastEvent = {
      measureIndex,
      onsetBeat: beat,
      duration: note.duration,
      isDotted: note.isDotted,
    }
    beat += beats
    if (beat >= capacity - 1e-9) {
      measureIndex += 1
      beat = 0
      ensureMeasure(measureIndex)
    }
    return placed
  })

  return { notes, measures }
}

/** 音高・調号から midiNumber を確定させる（記譜上の音高）。 */
export function withResolvedPitches(score) {
  const notes = score.notes.map((note) => {
    if (note.isRest) return { ...note, midiNumber: null }
    const keySignature = score.measures[note.measureIndex]?.keySignature ?? 'C'
    return {
      ...note,
      midiNumber: midiFromPitch(note.pitchName, note.octave, note.accidental, keySignature),
    }
  })
  return { ...score, notes }
}

export function normalize(score) {
  return withResolvedPitches(reflow(score))
}

export function insertNotes(score, index, newNotes) {
  const notes = [...score.notes]
  notes.splice(index, 0, ...newNotes)
  return normalize({ ...score, notes })
}

export function updateNote(score, id, patch) {
  const notes = score.notes.map((note) => (note.id === id ? { ...note, ...patch } : note))
  return normalize({ ...score, notes })
}

export function updateNotes(score, ids, patch) {
  const target = new Set(ids)
  const notes = score.notes.map((note) => (target.has(note.id) ? { ...note, ...patch } : note))
  return normalize({ ...score, notes })
}

export function deleteNotes(score, ids) {
  const target = new Set(ids)
  return normalize({ ...score, notes: score.notes.filter((note) => !target.has(note.id)) })
}

export function addMeasure(score) {
  const last = score.measures[score.measures.length - 1]
  return {
    ...score,
    measures: [
      ...score.measures,
      {
        measureIndex: score.measures.length,
        keySignature: last?.keySignature ?? 'C',
        timeSignature: last?.timeSignature ?? '4/4',
      },
    ],
  }
}

/** 末尾の小節を、その小節に含まれる音符ごと削除する。 */
export function removeLastMeasure(score) {
  if (score.measures.length <= 1) return score
  const lastIndex = score.measures.length - 1
  const notes = score.notes.filter((note) => note.measureIndex !== lastIndex)
  return normalize({ notes, measures: score.measures.slice(0, lastIndex) })
}

export function setMeasureAttribute(score, measureIndex, patch) {
  const measures = score.measures.map((measure, index) =>
    index === measureIndex ? { ...measure, ...patch } : measure,
  )
  return normalize({ ...score, measures })
}

export function notesInMeasure(score, measureIndex) {
  return score.notes.filter((note) => note.measureIndex === measureIndex)
}

/** 同時に鳴る音（和音）ごとにまとめた配列を返す。 */
export function chordGroups(score) {
  const groups = []
  score.notes.forEach((note) => {
    const last = groups[groups.length - 1]
    if (
      last &&
      !note.isRest &&
      !last[0].isRest &&
      last[0].measureIndex === note.measureIndex &&
      Math.abs(last[0].onsetBeat - note.onsetBeat) < 1e-9
    ) {
      last.push(note)
    } else {
      groups.push([note])
    }
  })
  return groups
}

/** 指定した音符と同時に鳴る音（自身を含む）のIDを返す。 */
export function chordSiblingIds(score, noteId) {
  const group = chordGroups(score).find((notes) => notes.some((note) => note.id === noteId))
  return group ? group.map((note) => note.id) : []
}

export function toApiScore(score) {
  const normalized = normalize(score)
  // id と inChord は画面用。バックエンドは measureIndex と onsetBeat から和音を判定する
  return {
    notes: normalized.notes.map(({ id, inChord, ...note }) => note),
    measures: normalized.measures,
  }
}

export function fromApiScore(data) {
  const measures =
    data.measures?.length > 0
      ? data.measures.map((measure, index) => ({ ...measure, measureIndex: index }))
      : emptyScore().measures
  const notes = (data.notes ?? []).map((note, index, all) => {
    const previous = all[index - 1]
    const inChord =
      Boolean(previous) &&
      !note.isRest &&
      !previous.isRest &&
      previous.measureIndex === note.measureIndex &&
      Math.abs(previous.onsetBeat - note.onsetBeat) < 1e-9

    // 音名を持たない（midiNumberだけの）データでも正しく表示できるようにする
    let spelled = note
    if (!note.isRest && note.midiNumber != null) {
      const keySignature = measures[note.measureIndex]?.keySignature ?? 'C'
      const written = midiFromPitch(note.pitchName, note.octave, note.accidental, keySignature)
      if (written !== note.midiNumber) {
        spelled = { ...note, ...pitchFromMidi(note.midiNumber, keySignature) }
      }
    }
    return { ...spelled, inChord, id: nextNoteId() }
  })
  return normalize({ notes, measures })
}
