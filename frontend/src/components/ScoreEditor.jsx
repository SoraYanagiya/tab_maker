import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import {
  Accidental,
  Dot,
  Formatter,
  Renderer,
  Stave,
  StaveNote,
  StaveTie,
  Voice,
} from 'vexflow'
import {
  accidentalGlyph,
  beatsPerMeasure,
  diatonicIndex,
  pitchFromDiatonic,
  vexDuration,
  vexKey,
} from '../music/pitch'

const SYSTEM_HEIGHT = 130
const STAVE_TOP = 30
const FIRST_MEASURE_EXTRA = 110
const MIN_MEASURE_WIDTH = 150
const NOTE_WIDTH = 46
const TOP_LINE_DIATONIC = diatonicIndex('F', 5) // 五線の最上線＝F5
const LOWEST_DIATONIC = diatonicIndex('E', 2)
const HIGHEST_DIATONIC = diatonicIndex('C', 7)

const INK = '#2a2a28'
const ACCENT = '#3f6fa8'
const HIGHLIGHT = '#d68b2c'

/** 五線譜の編集キャンバス（設計書 17.2 五線譜入力画面）。 */
export default function ScoreEditor({
  score,
  selectedIds,
  onSelectionChange,
  onScoreChange,
  onDragPitch,
  highlightedNoteId,
  onHoverNote,
  width,
}) {
  const containerRef = useRef(null)
  const layoutRef = useRef({ notes: [], measures: [] })
  const dragRef = useRef(null)
  const [, forceRender] = useState(0)

  const renderScore = useCallback(() => {
    const container = containerRef.current
    if (!container || !width) return
    container.innerHTML = ''

    const renderer = new Renderer(container, Renderer.Backends.SVG)
    const context = renderer.getContext()
    const available = width - 24

    // 小節を行（システム）に詰める
    const systems = []
    let currentSystem = []
    let usedWidth = 0
    score.measures.forEach((measure, measureIndex) => {
      const noteCount = score.notes.filter((note) => note.measureIndex === measureIndex).length
      const isFirstInSystem = currentSystem.length === 0
      const measureWidth =
        Math.max(MIN_MEASURE_WIDTH, 40 + noteCount * NOTE_WIDTH) +
        (isFirstInSystem ? FIRST_MEASURE_EXTRA : 0)
      if (!isFirstInSystem && usedWidth + measureWidth > available) {
        systems.push(currentSystem)
        currentSystem = []
        usedWidth = 0
      }
      const entryWidth =
        currentSystem.length === 0
          ? Math.max(MIN_MEASURE_WIDTH, 40 + noteCount * NOTE_WIDTH) + FIRST_MEASURE_EXTRA
          : measureWidth
      currentSystem.push({ measureIndex, measure, width: entryWidth })
      usedWidth += entryWidth
    })
    if (currentSystem.length > 0) systems.push(currentSystem)

    const height = systems.length * SYSTEM_HEIGHT + 40
    renderer.resize(width, height)

    const noteLayout = []
    const measureLayout = []
    const drawnNotes = new Map()

    systems.forEach((system, systemIndex) => {
      let x = 12
      const y = STAVE_TOP + systemIndex * SYSTEM_HEIGHT

      system.forEach((entry, indexInSystem) => {
        const stave = new Stave(x, y, entry.width)
        const previousMeasure = score.measures[entry.measureIndex - 1]

        if (indexInSystem === 0) {
          // ギター譜は実音より1オクターブ上で記譜する
          stave.addClef('treble', undefined, '8vb')
          stave.addKeySignature(entry.measure.keySignature)
          stave.addTimeSignature(entry.measure.timeSignature)
        } else {
          if (previousMeasure && previousMeasure.keySignature !== entry.measure.keySignature) {
            stave.addKeySignature(entry.measure.keySignature)
          }
          if (previousMeasure && previousMeasure.timeSignature !== entry.measure.timeSignature) {
            stave.addTimeSignature(entry.measure.timeSignature)
          }
        }

        stave.setContext(context).draw()
        measureLayout.push({
          measureIndex: entry.measureIndex,
          x,
          y,
          width: entry.width,
          stave,
          system: systemIndex,
        })

        const measureNotes = score.notes.filter((note) => note.measureIndex === entry.measureIndex)
        if (measureNotes.length > 0) {
          const staveNotes = measureNotes.map((note) => {
            const staveNote = new StaveNote({
              keys: [vexKey(note)],
              duration: vexDuration(note),
              clef: 'treble',
              auto_stem: true,
            })
            const glyph = note.isRest ? null : accidentalGlyph(note.accidental)
            if (glyph) staveNote.addModifier(new Accidental(glyph), 0)
            if (note.isDotted) Dot.buildAndAttach([staveNote], { all: true })

            if (selectedIds.includes(note.id)) {
              staveNote.setStyle({ fillStyle: ACCENT, strokeStyle: ACCENT })
            } else if (highlightedNoteId === note.id) {
              staveNote.setStyle({ fillStyle: HIGHLIGHT, strokeStyle: HIGHLIGHT })
            } else {
              staveNote.setStyle({ fillStyle: INK, strokeStyle: INK })
            }
            drawnNotes.set(note.id, staveNote)
            return staveNote
          })

          const voice = new Voice({
            num_beats: beatsPerMeasure(entry.measure),
            beat_value: Number(entry.measure.timeSignature.split('/')[1]),
          })
          voice.setMode(Voice.Mode.SOFT)
          voice.addTickables(staveNotes)
          new Formatter()
            .joinVoices([voice])
            .format([voice], entry.width - (indexInSystem === 0 ? FIRST_MEASURE_EXTRA + 20 : 30))
          voice.draw(context, stave)

          measureNotes.forEach((note, index) => {
            const staveNote = staveNotes[index]
            const box = staveNote.getBoundingBox()
            noteLayout.push({
              id: note.id,
              measureIndex: entry.measureIndex,
              x: staveNote.getAbsoluteX(),
              y: box ? box.getY() : y,
              height: box ? box.getH() : 60,
              staveY: y,
              stave,
              system: systemIndex,
            })
          })
        }

        x += entry.width
      })
    })

    // タイを描く（同じシステム内の隣接音のみ）
    score.notes.forEach((note, index) => {
      if (!note.tieToNext) return
      const next = score.notes[index + 1]
      if (!next) return
      const from = drawnNotes.get(note.id)
      const to = drawnNotes.get(next.id)
      const fromLayout = noteLayout.find((item) => item.id === note.id)
      const toLayout = noteLayout.find((item) => item.id === next.id)
      if (!from || !to || fromLayout?.system !== toLayout?.system) return
      const tie = new StaveTie({
        first_note: from,
        last_note: to,
        first_indices: [0],
        last_indices: [0],
      })
      tie.setContext(context).draw()
    })

    layoutRef.current = { notes: noteLayout, measures: measureLayout }
  }, [score, selectedIds, highlightedNoteId, width])

  useLayoutEffect(() => {
    renderScore()
  }, [renderScore])

  const pointerPosition = (event) => {
    const rect = containerRef.current.getBoundingClientRect()
    return { x: event.clientX - rect.left, y: event.clientY - rect.top }
  }

  const findNoteAt = (position) =>
    layoutRef.current.notes.find(
      (item) =>
        Math.abs(item.x + 6 - position.x) < 16 &&
        position.y > item.staveY - 34 &&
        position.y < item.staveY + 90,
    )

  const findMeasureAt = (position) => {
    const inBand = layoutRef.current.measures.filter(
      (item) => position.y >= item.y - 30 && position.y <= item.y + 90,
    )
    const hit = inBand.find(
      (item) => position.x >= item.x && position.x <= item.x + item.width,
    )
    if (hit) return hit
    // 行の最後の小節より右をクリックした場合も、その小節への追加として扱う
    return inBand.length > 0 ? inBand[inBand.length - 1] : undefined
  }

  const diatonicAt = (position, stave) => {
    const spacing = stave.getSpacingBetweenLines()
    const topLineY = stave.getYForLine(0)
    const stepsBelowTop = Math.round((position.y - topLineY) / (spacing / 2))
    const value = TOP_LINE_DIATONIC - stepsBelowTop
    return Math.min(HIGHEST_DIATONIC, Math.max(LOWEST_DIATONIC, value))
  }

  const handleMouseDown = (event) => {
    const position = pointerPosition(event)
    const hit = findNoteAt(position)

    if (hit) {
      const additive = event.shiftKey
      onSelectionChange(hit.id, { additive })
      const note = score.notes.find((item) => item.id === hit.id)
      if (note && !note.isRest) {
        dragRef.current = {
          id: hit.id,
          stave: hit.stave,
          startDiatonic: diatonicIndex(note.pitchName, note.octave),
          startY: position.y,
          moved: false,
        }
      }
      return
    }

    const measure = findMeasureAt(position)
    if (!measure) {
      onSelectionChange(null)
      return
    }

    const diatonic = diatonicAt(position, measure.stave)
    const pitch = pitchFromDiatonic(diatonic)
    const notesHere = layoutRef.current.notes.filter(
      (item) => item.measureIndex === measure.measureIndex,
    )
    const insertOffset = notesHere.filter((item) => item.x < position.x).length
    const measureStart = score.notes.findIndex(
      (note) => note.measureIndex === measure.measureIndex,
    )
    const baseIndex =
      measureStart === -1
        ? score.notes.filter((note) => note.measureIndex < measure.measureIndex).length
        : measureStart
    onScoreChange({
      type: 'insert',
      index: baseIndex + insertOffset,
      pitch: { pitchName: pitch.step, octave: pitch.octave },
    })
  }

  const handleMouseMove = (event) => {
    const position = pointerPosition(event)
    const drag = dragRef.current

    if (!drag) {
      const hit = findNoteAt(position)
      onHoverNote(hit ? hit.id : null)
      return
    }

    const spacing = drag.stave.getSpacingBetweenLines()
    const steps = Math.round((drag.startY - position.y) / (spacing / 2))
    const target = Math.min(
      HIGHEST_DIATONIC,
      Math.max(LOWEST_DIATONIC, drag.startDiatonic + steps),
    )
    const pitch = pitchFromDiatonic(target)
    dragRef.current = { ...drag, moved: true }
    onDragPitch(drag.id, { pitchName: pitch.step, octave: pitch.octave })
  }

  const endDrag = () => {
    dragRef.current = null
  }

  useEffect(() => {
    const handleUp = () => endDrag()
    window.addEventListener('mouseup', handleUp)
    return () => window.removeEventListener('mouseup', handleUp)
  }, [])

  useEffect(() => {
    forceRender((value) => value + 1)
  }, [width])

  return (
    <div
      className="score-canvas"
      ref={containerRef}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseLeave={() => onHoverNote(null)}
    />
  )
}
