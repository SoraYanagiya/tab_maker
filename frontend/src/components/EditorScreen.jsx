import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { api } from '../api'
import { DURATIONS, diatonicIndex, pitchFromDiatonic, pitchLabel } from '../music/pitch'
import { absoluteOnsets, buildPlaybackEvents, createPlayer } from '../music/player'
import {
  addMeasure,
  chordSiblingIds,
  deleteNotes,
  emptyScore,
  fromApiScore,
  insertNotes,
  makeNote,
  nextNoteId,
  removeLastMeasure,
  setMeasureAttribute,
  toApiScore,
  updateNote,
  updateNotes,
} from '../music/score'
import { useHistory } from '../hooks/useHistory'
import ScoreEditor from './ScoreEditor'
import TabPreview from './TabPreview'
import TabSvg from './TabSvg'
import Toolbar from './Toolbar'
import WarningsPanel from './WarningsPanel'

const DEFAULT_SETTINGS = {
  tuning: 'standard',
  notationOctaveShift: -1,
  bpm: 90,
  weights: {},
}

const AUTOSAVE_DELAY = 1500
// 書き出す画像は、ウィンドウ幅によらず常にこの幅・この倍率で描く
const EXPORT_WIDTH = 1080
const EXPORT_SCALE = 2

export default function EditorScreen({ projectId, onBack }) {
  const history = useHistory(emptyScore())
  const score = history.state

  const [projectName, setProjectName] = useState('')
  const [settings, setSettings] = useState(DEFAULT_SETTINGS)
  const [selectedIds, setSelectedIds] = useState([])
  const [hoveredNoteId, setHoveredNoteId] = useState(null)
  const [editorState, setEditorState] = useState({
    duration: 'quarter',
    accidental: 'none',
    isDotted: false,
    isRest: false,
    chordMode: false,
  })
  const [result, setResult] = useState(null)
  const [toggles, setToggles] = useState({ fingers: true, positions: true, shifts: false })
  const [saveStatus, setSaveStatus] = useState('saved')
  const [status, setStatus] = useState(null)
  const [error, setError] = useState(null)
  const [isGenerating, setIsGenerating] = useState(false)
  const [topHeight, setTopHeight] = useState(360)
  const [scoreWidth, setScoreWidth] = useState(900)
  const [tabWidth, setTabWidth] = useState(900)
  const [isPlaying, setIsPlaying] = useState(false)
  const [playingNoteId, setPlayingNoteId] = useState(null)

  const playerRef = useRef(null)
  const loadedRef = useRef(false)
  const clipboardRef = useRef([])
  const fileInputRef = useRef(null)
  const scorePaneRef = useRef(null)
  const tabPaneRef = useRef(null)
  const dividerRef = useRef(null)

  // --- プロジェクト読み込み -------------------------------------------------
  useEffect(() => {
    let cancelled = false
    loadedRef.current = false
    api
      .getProject(projectId)
      .then((project) => {
        if (cancelled) return
        setProjectName(project.name)
        setSettings({ ...DEFAULT_SETTINGS, ...(project.settings ?? {}) })
        history.reset(fromApiScore(project))
        setResult(project.generatedTab?.fingerings ? project.generatedTab : null)
        setSaveStatus('saved')
        loadedRef.current = true
      })
      .catch((loadError) => setError(loadError.message))
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId])

  // --- 自動保存（設計書 17.7.2）-------------------------------------------
  useEffect(() => {
    if (!loadedRef.current) return
    setSaveStatus('dirty')
    const timer = setTimeout(async () => {
      try {
        setSaveStatus('saving')
        const payload = toApiScore(score)
        await api.updateProject(projectId, {
          name: projectName,
          notes: payload.notes,
          measures: payload.measures,
          settings,
          generatedTab: result,
        })
        setSaveStatus('saved')
      } catch (saveError) {
        setSaveStatus('error')
        setError(`保存に失敗しました: ${saveError.message}`)
      }
    }, AUTOSAVE_DELAY)
    return () => clearTimeout(timer)
  }, [score, projectName, settings, result, projectId])

  // --- 幅の追従 -------------------------------------------------------------
  useEffect(() => {
    const update = () => {
      if (scorePaneRef.current) setScoreWidth(scorePaneRef.current.clientWidth)
      if (tabPaneRef.current) setTabWidth(tabPaneRef.current.clientWidth)
    }
    update()
    window.addEventListener('resize', update)
    return () => window.removeEventListener('resize', update)
  }, [topHeight])

  const currentMeasure = useMemo(() => {
    const selected = score.notes.find((note) => note.id === selectedIds[0])
    const index = selected ? selected.measureIndex : score.measures.length - 1
    return score.measures[index] ?? score.measures[0]
  }, [score, selectedIds])

  // --- 編集操作 -------------------------------------------------------------
  const handleInsert = useCallback(
    (request) => {
      if (request.type === 'chord') {
        // 既存の音に重ねて和音にする
        history.set((current) => {
          const siblings = chordSiblingIds(current, request.targetId)
          const target = current.notes.find((note) => note.id === request.targetId)
          if (!target || target.isRest) return current
          const lastIndex = current.notes.findIndex(
            (note) => note.id === siblings[siblings.length - 1],
          )
          const added = makeNote({
            ...request.pitch,
            accidental: editorState.accidental,
            duration: target.duration,
            isDotted: target.isDotted,
            inChord: true,
          })
          const next = insertNotes(current, lastIndex + 1, [added])
          setSelectedIds([added.id])
          return next
        })
        return
      }

      const note = makeNote({
        ...request.pitch,
        accidental: editorState.accidental,
        duration: editorState.duration,
        isDotted: editorState.isDotted,
        isRest: editorState.isRest,
      })
      history.set((current) => insertNotes(current, request.index, [note]))
      setSelectedIds([note.id])
    },
    [editorState, history],
  )

  const handleDragPitch = useCallback(
    (id, pitch) => {
      history.set((current) => updateNote(current, id, pitch), { coalesceKey: `drag:${id}` })
    },
    [history],
  )

  const handleSelectionChange = useCallback((id, options = {}) => {
    if (id === null) {
      setSelectedIds([])
      return
    }
    setSelectedIds((current) => {
      if (!options.additive) return [id]
      return current.includes(id) ? current.filter((item) => item !== id) : [...current, id]
    })
  }, [])

  const applyToSelectionOrDefault = useCallback(
    (patch, editorPatch) => {
      setEditorState((current) => ({ ...current, ...editorPatch }))
      if (selectedIds.length > 0) {
        history.set((current) => updateNotes(current, selectedIds, patch))
      }
    },
    [history, selectedIds],
  )

  const handleEditorStateChange = useCallback(
    (change) => {
      if (change.toggleTie) {
        if (selectedIds.length === 0) return
        const first = score.notes.find((note) => note.id === selectedIds[0])
        const nextValue = !first?.tieToNext
        history.set((current) => updateNotes(current, selectedIds, { tieToNext: nextValue }))
        return
      }
      if ('duration' in change) {
        applyToSelectionOrDefault({ duration: change.duration }, change)
        return
      }
      if ('accidental' in change) {
        applyToSelectionOrDefault({ accidental: change.accidental }, change)
        return
      }
      if ('isDotted' in change) {
        applyToSelectionOrDefault({ isDotted: change.isDotted }, change)
        return
      }
      if ('isRest' in change) {
        applyToSelectionOrDefault({ isRest: change.isRest }, change)
        return
      }
      if ('chordMode' in change) {
        setEditorState((current) => ({ ...current, chordMode: change.chordMode }))
        return
      }
      setEditorState((current) => ({ ...current, ...change }))
    },
    [applyToSelectionOrDefault, history, score.notes, selectedIds],
  )

  const shiftPitch = useCallback(
    (steps) => {
      if (selectedIds.length === 0) return
      history.set((current) => {
        let next = current
        selectedIds.forEach((id) => {
          const note = next.notes.find((item) => item.id === id)
          if (!note || note.isRest) return
          const target = diatonicIndex(note.pitchName, note.octave) + steps
          const pitch = pitchFromDiatonic(target)
          next = updateNote(next, id, { pitchName: pitch.step, octave: pitch.octave })
        })
        return next
      })
    },
    [history, selectedIds],
  )

  const moveSelection = useCallback(
    (offset) => {
      if (score.notes.length === 0) return
      const currentIndex = score.notes.findIndex((note) => note.id === selectedIds[0])
      const nextIndex = Math.min(
        score.notes.length - 1,
        Math.max(0, (currentIndex === -1 ? 0 : currentIndex) + offset),
      )
      setSelectedIds([score.notes[nextIndex].id])
    },
    [score.notes, selectedIds],
  )

  const deleteSelection = useCallback(() => {
    if (selectedIds.length === 0) return
    history.set((current) => deleteNotes(current, selectedIds))
    setSelectedIds([])
  }, [history, selectedIds])

  const copySelection = useCallback(() => {
    clipboardRef.current = score.notes.filter((note) => selectedIds.includes(note.id))
    setStatus(`${clipboardRef.current.length} 個の音符をコピーしました`)
  }, [score.notes, selectedIds])

  const pasteClipboard = useCallback(() => {
    if (clipboardRef.current.length === 0) return
    const copies = clipboardRef.current.map((note) => ({ ...note, id: nextNoteId() }))
    const anchor = score.notes.findIndex((note) => note.id === selectedIds[selectedIds.length - 1])
    const index = anchor === -1 ? score.notes.length : anchor + 1
    history.set((current) => insertNotes(current, index, copies))
    setSelectedIds(copies.map((note) => note.id))
  }, [history, score.notes, selectedIds])

  // --- TAB生成 --------------------------------------------------------------
  const generate = useCallback(async () => {
    setIsGenerating(true)
    setError(null)
    try {
      const payload = toApiScore(score)
      const response = await api.convert({
        inputType: 'note_list',
        content: payload,
        settings: { ...settings, includeDetails: true },
      })
      setResult(response)
      setStatus(`TAB譜を生成しました（音符 ${payload.notes.length} 個）`)
    } catch (convertError) {
      setError(`TAB生成に失敗しました: ${convertError.message}`)
    } finally {
      setIsGenerating(false)
    }
  }, [score, settings])

  // --- 再生 -----------------------------------------------------------------
  const stopPlayback = useCallback(() => {
    playerRef.current?.stop()
    setIsPlaying(false)
    setPlayingNoteId(null)
  }, [])

  const togglePlayback = useCallback(() => {
    if (isPlaying) {
      stopPlayback()
      return
    }
    const events = buildPlaybackEvents(score, settings.notationOctaveShift ?? -1)
    if (events.length === 0) {
      setStatus('再生できる音符がありません')
      return
    }
    if (!playerRef.current) playerRef.current = createPlayer()

    // 音符が選択されていれば、その位置から再生する
    const selectedIndex = score.notes.findIndex((note) => note.id === selectedIds[0])
    const fromBeat = selectedIndex >= 0 ? absoluteOnsets(score)[selectedIndex] : 0

    setIsPlaying(true)
    playerRef.current.play(events, {
      bpm: settings.bpm ?? 90,
      fromBeat,
      onNote: setPlayingNoteId,
      onEnd: () => {
        setIsPlaying(false)
        setPlayingNoteId(null)
      },
    })
  }, [isPlaying, score, selectedIds, settings, stopPlayback])

  useEffect(() => stopPlayback, [stopPlayback])

  // --- インポート -----------------------------------------------------------
  const importFile = async (event) => {
    const file = event.target.files?.[0]
    if (!file) return
    try {
      const imported = await api.importScore(file)
      history.set(fromApiScore(imported))
      setSelectedIds([])
      setStatus(
        [`${imported.notes.length} 個の音符を読み込みました`, ...(imported.warnings ?? [])].join(' / '),
      )
    } catch (importError) {
      setError(`読み込みに失敗しました: ${importError.message}`)
    } finally {
      event.target.value = ''
    }
  }

  // --- エクスポート ---------------------------------------------------------
  const download = (blob, filename) => {
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.click()
    URL.revokeObjectURL(url)
  }

  const exportText = () => {
    if (!result) return
    const body = result.details ? `${result.tab}\n\n${result.details}` : result.tab
    download(new Blob([body], { type: 'text/plain;charset=utf-8' }), `${projectName || 'tab'}.txt`)
  }

  /**
   * 画面のSVGではなく、固定幅で組み直したSVGを書き出す。
   * こうすることで、ウィンドウサイズを変えても同じ小節割り・同じ解像度の画像になる。
   */
  const exportImage = () => {
    if (!result) return
    const markup = renderToStaticMarkup(
      <TabSvg result={result} score={score} toggles={toggles} width={EXPORT_WIDTH} />,
    )
    const svgElement = new DOMParser().parseFromString(markup, 'image/svg+xml').documentElement
    const width = Number(svgElement.getAttribute('width'))
    const height = Number(svgElement.getAttribute('height'))

    const image = new Image()
    const url = URL.createObjectURL(new Blob([markup], { type: 'image/svg+xml;charset=utf-8' }))
    image.onload = () => {
      const canvas = document.createElement('canvas')
      canvas.width = width * EXPORT_SCALE
      canvas.height = height * EXPORT_SCALE
      const context = canvas.getContext('2d')
      context.fillStyle = '#ffffff'
      context.fillRect(0, 0, canvas.width, canvas.height)
      context.scale(EXPORT_SCALE, EXPORT_SCALE)
      context.drawImage(image, 0, 0)
      URL.revokeObjectURL(url)
      canvas.toBlob((blob) => download(blob, `${projectName || 'tab'}.png`))
    }
    image.src = url
  }

  // --- キーボードショートカット（設計書 17.2）------------------------------
  useEffect(() => {
    const handler = (event) => {
      const tag = event.target.tagName
      if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') return
      const meta = event.metaKey || event.ctrlKey

      if (meta && event.key.toLowerCase() === 'z') {
        event.preventDefault()
        event.shiftKey ? history.redo() : history.undo()
        return
      }
      if (meta && event.key.toLowerCase() === 'c') {
        copySelection()
        return
      }
      if (meta && event.key.toLowerCase() === 'v') {
        pasteClipboard()
        return
      }
      if (meta && event.key === 'Enter') {
        event.preventDefault()
        generate()
        return
      }
      if (event.key === ' ') {
        event.preventDefault()
        togglePlayback()
        return
      }
      if (event.key === 'Delete' || event.key === 'Backspace') {
        event.preventDefault()
        deleteSelection()
        return
      }
      if (event.key === 'ArrowUp' || event.key === 'ArrowDown') {
        event.preventDefault()
        const direction = event.key === 'ArrowUp' ? 1 : -1
        shiftPitch(event.shiftKey ? direction * 7 : direction)
        return
      }
      if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
        event.preventDefault()
        moveSelection(event.key === 'ArrowLeft' ? -1 : 1)
        return
      }
      const durationIndex = Number(event.key)
      if (durationIndex >= 1 && durationIndex <= DURATIONS.length) {
        handleEditorStateChange({ duration: DURATIONS[durationIndex - 1].id })
        return
      }
      const key = event.key.toLowerCase()
      if (key === 'c') handleEditorStateChange({ chordMode: !editorState.chordMode })
      if (key === 'r') handleEditorStateChange({ isRest: !editorState.isRest })
      if (key === 's') handleEditorStateChange({ accidental: 'sharp' })
      if (key === 'f') handleEditorStateChange({ accidental: 'flat' })
      if (key === 'n') handleEditorStateChange({ accidental: 'natural' })
      if (key === '.') handleEditorStateChange({ isDotted: !editorState.isDotted })
      if (key === 't') handleEditorStateChange({ toggleTie: true })
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [
    copySelection,
    deleteSelection,
    editorState,
    generate,
    handleEditorStateChange,
    history,
    moveSelection,
    pasteClipboard,
    shiftPitch,
    togglePlayback,
  ])

  // --- 分割位置のドラッグ ---------------------------------------------------
  useEffect(() => {
    const divider = dividerRef.current
    if (!divider) return
    let dragging = false
    const start = () => {
      dragging = true
      document.body.style.cursor = 'row-resize'
    }
    const move = (event) => {
      if (!dragging) return
      const top = divider.parentElement.getBoundingClientRect().top
      setTopHeight(Math.min(700, Math.max(200, event.clientY - top - 60)))
    }
    const end = () => {
      dragging = false
      document.body.style.cursor = ''
    }
    divider.addEventListener('mousedown', start)
    window.addEventListener('mousemove', move)
    window.addEventListener('mouseup', end)
    return () => {
      divider.removeEventListener('mousedown', start)
      window.removeEventListener('mousemove', move)
      window.removeEventListener('mouseup', end)
    }
  }, [])

  useEffect(() => {
    if (!status) return
    const timer = setTimeout(() => setStatus(null), 4000)
    return () => clearTimeout(timer)
  }, [status])

  const saveLabel = {
    saved: '保存済み',
    saving: '保存中…',
    dirty: '未保存の変更',
    error: '保存エラー',
  }[saveStatus]

  const selectedNote = score.notes.find((note) => note.id === selectedIds[0])

  return (
    <div className="screen editor-screen">
      <header className="app-header">
        <div className="app-title">
          <button type="button" className="text-button" onClick={onBack}>
            ← 一覧
          </button>
          <input
            className="project-name"
            value={projectName}
            onChange={(event) => setProjectName(event.target.value)}
            aria-label="プロジェクト名"
          />
          <span className={`save-status is-${saveStatus}`}>{saveLabel}</span>
        </div>

        <div className="header-actions">
          <button
            type="button"
            className="icon-button"
            onClick={history.undo}
            disabled={!history.canUndo}
            title="元に戻す (⌘Z)"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
              <path d="M9 8L4 12l5 4" />
              <path d="M4 12h11a5 5 0 0 1 0 10h-1" />
            </svg>
          </button>
          <button
            type="button"
            className="icon-button"
            onClick={history.redo}
            disabled={!history.canRedo}
            title="やり直す (⇧⌘Z)"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
              <path d="M15 8l5 4-5 4" />
              <path d="M20 12H9a5 5 0 0 0 0 10h1" />
            </svg>
          </button>
          <button type="button" className="text-button" onClick={() => fileInputRef.current.click()}>
            MusicXML / MIDI 読込
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".musicxml,.xml,.mxl,.mid,.midi"
            hidden
            onChange={importFile}
          />
          <button type="button" className="primary-button" onClick={generate} disabled={isGenerating}>
            {isGenerating ? '生成中…' : 'TAB譜を生成 (⌘⏎)'}
          </button>
        </div>
      </header>

      {error && (
        <div className="error-banner" onClick={() => setError(null)} role="alert">
          {error}（クリックで閉じる）
        </div>
      )}
      {status && <div className="status-banner">{status}</div>}

      <div className="split">
        <section className="pane score-pane" style={{ height: topHeight }} ref={scorePaneRef}>
          <div className="pane-head">
            <h2>五線譜入力</h2>
            <span className="hint">
              五線をクリックで音符追加 / ドラッグで音高変更 / ↑↓で音程、1〜5で音価
              {editorState.chordMode ? ' / 和音モード: クリックで重ねる' : ' / Cキーで和音モード'}
              {selectedNote && ` — 選択中: ${pitchLabel(selectedNote)}`}
            </span>
            <div className="playback">
              <button
                type="button"
                className={`play-button${isPlaying ? ' is-playing' : ''}`}
                onClick={togglePlayback}
                title={
                  selectedIds.length > 0 ? '選択した音符から再生 (Space)' : '先頭から再生 (Space)'
                }
              >
                {isPlaying ? (
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                    <rect x="5" y="4" width="5" height="16" />
                    <rect x="14" y="4" width="5" height="16" />
                  </svg>
                ) : (
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M7 4l13 8-13 8z" />
                  </svg>
                )}
                {isPlaying ? '停止' : '再生'}
              </button>
              <label className="tempo">
                <input
                  type="number"
                  min="40"
                  max="240"
                  step="1"
                  value={settings.bpm ?? 90}
                  onChange={(event) =>
                    setSettings((current) => ({ ...current, bpm: Number(event.target.value) }))
                  }
                />
                BPM
              </label>
            </div>
          </div>
          <Toolbar
            editorState={editorState}
            onEditorStateChange={handleEditorStateChange}
            measure={currentMeasure}
            onMeasureChange={(patch) =>
              history.set((current) =>
                setMeasureAttribute(current, currentMeasure?.measureIndex ?? 0, patch),
              )
            }
            onAddMeasure={() => history.set((current) => addMeasure(current))}
            onRemoveMeasure={() => history.set((current) => removeLastMeasure(current))}
            hasSelection={selectedIds.length > 0}
          />
          <div className="score-scroll">
            <ScoreEditor
              score={score}
              selectedIds={selectedIds}
              onSelectionChange={handleSelectionChange}
              onScoreChange={handleInsert}
              onDragPitch={handleDragPitch}
              highlightedNoteId={playingNoteId ?? hoveredNoteId}
              onHoverNote={setHoveredNoteId}
              chordMode={editorState.chordMode}
              width={scoreWidth}
            />
          </div>
        </section>

        <div className="divider" ref={dividerRef}>
          <span className="divider-grip" />
          <span className="divider-label">五線譜 ⇔ TAB 同期（音符をクリックすると連動）</span>
        </div>

        <section className="pane tab-pane">
          <div className="pane-head">
            <h2>TABプレビュー</h2>
            <div className="toggles">
              {[
                ['fingers', '指番号'],
                ['positions', 'ポジション'],
                ['shifts', '手の移動量'],
              ].map(([key, label]) => (
                <label key={key} className="chip">
                  <input
                    type="checkbox"
                    checked={toggles[key]}
                    onChange={(event) =>
                      setToggles((current) => ({ ...current, [key]: event.target.checked }))
                    }
                  />
                  {label}
                </label>
              ))}
              <button type="button" className="text-button" onClick={exportText} disabled={!result}>
                テキストで書き出し
              </button>
              <button type="button" className="text-button" onClick={exportImage} disabled={!result}>
                画像で書き出し
              </button>
            </div>
          </div>

          <div className="tab-body">
            <div className="tab-scroll" ref={tabPaneRef}>
              <TabPreview
                result={result}
                score={score}
                selectedIds={selectedIds}
                highlightedNoteId={playingNoteId ?? hoveredNoteId}
                onSelectNote={(id) => handleSelectionChange(id)}
                onHoverNote={setHoveredNoteId}
                toggles={toggles}
                width={tabWidth}
              />
            </div>
            <WarningsPanel
              result={result}
              settings={settings}
              onSettingsChange={setSettings}
              onFocusNote={(noteIndex) => {
                const note = score.notes[noteIndex]
                if (note) setSelectedIds([note.id])
              }}
            />
          </div>
        </section>
      </div>
    </div>
  )
}
