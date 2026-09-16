import {
  PIANO_BLACK_KEYS,
  PIANO_MAX_OCTAVE,
  PIANO_MIN_OCTAVE,
  PIANO_WHITE_KEYS,
  pianoMidi,
  pitchFromMidi,
} from '../music/pitch'

const WHITE_WIDTH = 34
const BLACK_WIDTH = 22

/**
 * 鍵盤入力（設計書 17.2）。クリック、またはPCキーボード（A〜' が白鍵、W〜P が黒鍵）
 * で音を入力する。オクターブは Z / X キーまたはボタンで切り替える。
 */
export default function PianoKeyboard({ octave, onOctaveChange, onPlay, activeSemitone, keySignature }) {
  const width = PIANO_WHITE_KEYS.length * WHITE_WIDTH

  const play = (semitone) => {
    const midi = pianoMidi(octave, semitone)
    onPlay(pitchFromMidi(midi, keySignature), semitone)
  }

  return (
    <div className="piano-keyboard">
      <div className="piano-octave">
        <button
          type="button"
          className="text-button"
          disabled={octave <= PIANO_MIN_OCTAVE}
          onClick={() => onOctaveChange(octave - 1)}
          title="1オクターブ下げる (Z)"
        >
          ▼
        </button>
        <span className="piano-range">
          {PIANO_WHITE_KEYS[0].key.toUpperCase()}={`C${octave}`} 〜{' '}
          {`F${octave + 1}`}
        </span>
        <button
          type="button"
          className="text-button"
          disabled={octave >= PIANO_MAX_OCTAVE}
          onClick={() => onOctaveChange(octave + 1)}
          title="1オクターブ上げる (X)"
        >
          ▲
        </button>
      </div>

      <div className="piano-keys" style={{ width }}>
        {PIANO_WHITE_KEYS.map((white, index) => (
          <button
            key={white.key}
            type="button"
            className={`piano-key piano-key-white${activeSemitone === white.semitone ? ' is-active' : ''}`}
            style={{ left: index * WHITE_WIDTH, width: WHITE_WIDTH }}
            onMouseDown={(event) => {
              event.preventDefault()
              play(white.semitone)
            }}
          >
            <span className="piano-key-label">{white.key.toUpperCase()}</span>
          </button>
        ))}
        {PIANO_BLACK_KEYS.map((black) => (
          <button
            key={black.key}
            type="button"
            className={`piano-key piano-key-black${activeSemitone === black.semitone ? ' is-active' : ''}`}
            style={{
              left: (black.afterWhiteIndex + 1) * WHITE_WIDTH - BLACK_WIDTH / 2,
              width: BLACK_WIDTH,
            }}
            onMouseDown={(event) => {
              event.preventDefault()
              play(black.semitone)
            }}
          >
            <span className="piano-key-label">{black.key.toUpperCase()}</span>
          </button>
        ))}
      </div>
    </div>
  )
}
