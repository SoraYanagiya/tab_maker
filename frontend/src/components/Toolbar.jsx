import { ACCIDENTALS, DURATIONS, KEY_OPTIONS, TIME_OPTIONS } from '../music/pitch'

function NoteIcon({ duration }) {
  const filled = duration !== 'whole' && duration !== 'half'
  const stem = duration !== 'whole'
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true">
      <ellipse
        cx="9"
        cy="16"
        rx="5"
        ry="3.6"
        transform="rotate(-18 9 16)"
        fill={filled ? 'currentColor' : 'none'}
        stroke="currentColor"
        strokeWidth="1.6"
      />
      {stem && <line x1="13.5" y1="14.5" x2="13.5" y2="3" stroke="currentColor" strokeWidth="1.6" />}
      {duration === 'eighth' && (
        <path d="M13.5 3c3 0 4.5 2 4.5 4.5" fill="none" stroke="currentColor" strokeWidth="1.6" />
      )}
      {duration === 'sixteenth' && (
        <>
          <path d="M13.5 3c3 0 4.5 2 4.5 4.5" fill="none" stroke="currentColor" strokeWidth="1.6" />
          <path d="M13.5 7c3 0 4.5 2 4.5 4.5" fill="none" stroke="currentColor" strokeWidth="1.6" />
        </>
      )}
    </svg>
  )
}

export default function Toolbar({
  editorState,
  onEditorStateChange,
  measure,
  onMeasureChange,
  onAddMeasure,
  onRemoveMeasure,
  hasSelection,
}) {
  return (
    <div className="toolbar">
      <div className="toolbar-group">
        <span className="toolbar-label">音価</span>
        {DURATIONS.map((duration) => (
          <button
            key={duration.id}
            type="button"
            className={`icon-button${editorState.duration === duration.id ? ' is-active' : ''}`}
            title={`${duration.label}${hasSelection ? '（選択中の音符に適用）' : ''}`}
            onClick={() => onEditorStateChange({ duration: duration.id })}
          >
            <NoteIcon duration={duration.id} />
          </button>
        ))}
        <button
          type="button"
          className={`icon-button${editorState.isDotted ? ' is-active' : ''}`}
          title="付点"
          onClick={() => onEditorStateChange({ isDotted: !editorState.isDotted })}
        >
          <svg width="20" height="20" viewBox="0 0 24 24">
            <ellipse cx="8" cy="14" rx="4.5" ry="3.2" fill="currentColor" transform="rotate(-18 8 14)" />
            <circle cx="17" cy="14" r="2" fill="currentColor" />
          </svg>
        </button>
        <button
          type="button"
          className={`icon-button${editorState.isRest ? ' is-active' : ''}`}
          title="休符"
          onClick={() => onEditorStateChange({ isRest: !editorState.isRest })}
        >
          <span className="glyph">𝄽</span>
        </button>
      </div>

      <div className="toolbar-group">
        <span className="toolbar-label">臨時記号</span>
        {ACCIDENTALS.map((accidental) => (
          <button
            key={accidental.id}
            type="button"
            className={`icon-button${editorState.accidental === accidental.id ? ' is-active' : ''}`}
            title={accidental.label}
            onClick={() => onEditorStateChange({ accidental: accidental.id })}
          >
            <span className="glyph">{accidental.symbol || '♮なし'.slice(0, 1)}</span>
          </button>
        ))}
        <button
          type="button"
          className="icon-button"
          title="選択した音符にタイを付ける / 外す"
          disabled={!hasSelection}
          onClick={() => onEditorStateChange({ toggleTie: true })}
        >
          <svg width="20" height="20" viewBox="0 0 24 24">
            <path d="M4 10c4 6 12 6 16 0" fill="none" stroke="currentColor" strokeWidth="1.8" />
          </svg>
        </button>
      </div>

      <div className="toolbar-group">
        <span className="toolbar-label">小節 {measure ? measure.measureIndex + 1 : '-'}</span>
        <select
          value={measure?.keySignature ?? 'C'}
          onChange={(event) => onMeasureChange({ keySignature: event.target.value })}
          title="調号"
        >
          {KEY_OPTIONS.map((key) => (
            <option key={key} value={key}>
              {key}
            </option>
          ))}
        </select>
        <select
          value={measure?.timeSignature ?? '4/4'}
          onChange={(event) => onMeasureChange({ timeSignature: event.target.value })}
          title="拍子記号"
        >
          {TIME_OPTIONS.map((time) => (
            <option key={time} value={time}>
              {time}
            </option>
          ))}
        </select>
        <button type="button" className="text-button" onClick={onAddMeasure}>
          小節を追加
        </button>
        <button type="button" className="text-button" onClick={onRemoveMeasure}>
          小節を削除
        </button>
      </div>
    </div>
  )
}
