import { beatsPerMeasure, durationBeats } from './pitch'

const DAMPING = 0.995
const PEAK_GAIN = 0.3
const RELEASE = 0.5
// 減衰しきった後まで合成しても無駄なので、1音あたりの長さはここで頭打ちにする
const MAX_BUFFER_SECONDS = 2.5

/** 各音符の、曲頭からの通算拍位置。 */
export function absoluteOnsets(score) {
  const starts = []
  let cursor = 0
  score.measures.forEach((measure) => {
    starts.push(cursor)
    cursor += beatsPerMeasure(measure)
  })
  return score.notes.map((note) => (starts[note.measureIndex] ?? 0) + note.onsetBeat)
}

/** 再生用のイベント列を作る。タイで繋がれた音は1つの長い音にまとめる。 */
export function buildPlaybackEvents(score, octaveShift = -1) {
  const onsets = absoluteOnsets(score)
  const events = []
  let index = 0

  while (index < score.notes.length) {
    const note = score.notes[index]
    if (note.isRest || note.midiNumber == null) {
      index += 1
      continue
    }
    let last = index
    let beats = durationBeats(note)
    while (
      score.notes[last]?.tieToNext &&
      score.notes[last + 1] &&
      !score.notes[last + 1].isRest &&
      score.notes[last + 1].midiNumber === score.notes[last].midiNumber
    ) {
      beats += durationBeats(score.notes[last + 1])
      last += 1
    }
    events.push({
      noteIds: score.notes.slice(index, last + 1).map((item) => item.id),
      midis: [note.midiNumber + 12 * octaveShift],
      startBeat: onsets[index],
      beats,
    })
    index = last + 1
  }

  // 同じ拍位置の音は和音としてまとめて鳴らす
  const merged = []
  events.forEach((event) => {
    const last = merged[merged.length - 1]
    if (last && Math.abs(last.startBeat - event.startBeat) < 1e-9) {
      last.midis.push(...event.midis)
      last.noteIds.push(...event.noteIds)
      last.beats = Math.max(last.beats, event.beats)
    } else {
      merged.push(event)
    }
  })
  return merged
}

/**
 * Karplus-Strong 方式で撥弦音を合成する。
 * ノイズを弦の長さ分のリングバッファに詰め、平均化しながら読み出すと弦の減衰音になる。
 */
function pluckBuffer(context, midi, seconds) {
  const frequency = 440 * 2 ** ((midi - 69) / 12)
  const sampleRate = context.sampleRate
  const length = Math.max(1, Math.floor(sampleRate * seconds))
  const buffer = context.createBuffer(1, length, sampleRate)
  const data = buffer.getChannelData(0)

  const period = Math.max(2, Math.round(sampleRate / frequency))
  const ring = new Float32Array(period)
  for (let i = 0; i < period; i += 1) ring[i] = Math.random() * 2 - 1

  let cursor = 0
  for (let i = 0; i < length; i += 1) {
    const current = ring[cursor]
    const next = ring[(cursor + 1) % period]
    data[i] = current
    ring[cursor] = (current + next) * 0.5 * DAMPING
    cursor = (cursor + 1) % period
  }
  return buffer
}

let previewContext = null

/** 鍵盤入力のクリック/キー押下に対する、単発の試聴音。 */
export function previewPitch(midi, seconds = 0.35) {
  if (!previewContext) {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext
    previewContext = new AudioContextClass()
  }
  if (previewContext.state === 'suspended') previewContext.resume()

  const when = previewContext.currentTime + 0.005
  const source = previewContext.createBufferSource()
  source.buffer = pluckBuffer(previewContext, midi, Math.min(seconds + RELEASE, MAX_BUFFER_SECONDS))
  const gain = previewContext.createGain()
  gain.gain.setValueAtTime(0.0001, when)
  gain.gain.exponentialRampToValueAtTime(PEAK_GAIN, when + 0.01)
  gain.gain.exponentialRampToValueAtTime(0.0001, when + seconds + RELEASE)
  source.connect(gain).connect(previewContext.destination)
  source.start(when)
  source.stop(when + seconds + RELEASE)
}

export function createPlayer() {
  let context = null
  let sources = []
  let frame = null

  const ensureContext = () => {
    if (!context) {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext
      context = new AudioContextClass()
    }
    if (context.state === 'suspended') context.resume()
    return context
  }

  const stop = () => {
    if (frame !== null) {
      cancelAnimationFrame(frame)
      frame = null
    }
    sources.forEach((source) => {
      try {
        source.stop()
      } catch {
        // 再生前/再生済みのソースは停止できないが、無視してよい
      }
    })
    sources = []
  }

  const play = (events, { bpm = 90, fromBeat = 0, onNote = () => {}, onEnd = () => {} } = {}) => {
    stop()
    const target = events.filter((event) => event.startBeat >= fromBeat - 1e-6)
    if (target.length === 0) {
      onEnd()
      return
    }

    const audio = ensureContext()
    const secondsPerBeat = 60 / bpm
    const startTime = audio.currentTime + 0.12
    const offset = target[0].startBeat

    target.forEach((event) => {
      const duration = Math.max(0.18, event.beats * secondsPerBeat)
      // 和音は低い弦から順にわずかにずらして鳴らす（ストロークの再現）
      const spread = event.midis.length > 1 ? 0.012 : 0
      const ordered = [...event.midis].sort((a, b) => a - b)
      ordered.forEach((midi, index) => {
        const when = startTime + (event.startBeat - offset) * secondsPerBeat + index * spread
        const source = audio.createBufferSource()
        source.buffer = pluckBuffer(audio, midi, Math.min(duration + RELEASE, MAX_BUFFER_SECONDS))
        const gain = audio.createGain()
        gain.gain.setValueAtTime(0.0001, when)
        gain.gain.exponentialRampToValueAtTime(PEAK_GAIN / Math.sqrt(ordered.length), when + 0.01)
        gain.gain.exponentialRampToValueAtTime(0.0001, when + duration + RELEASE)
        source.connect(gain).connect(audio.destination)
        source.start(when)
        source.stop(when + duration + RELEASE)
        sources.push(source)
      })
    })

    const totalBeats = Math.max(...target.map((event) => event.startBeat - offset + event.beats))
    const tick = () => {
      const elapsed = audio.currentTime - startTime
      const beat = elapsed / secondsPerBeat
      const current = target.find(
        (event) =>
          beat >= event.startBeat - offset && beat < event.startBeat - offset + event.beats,
      )
      onNote(current ? current.noteIds[0] : null)
      if (elapsed > totalBeats * secondsPerBeat + 0.25) {
        stop()
        onNote(null)
        onEnd()
        return
      }
      frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
  }

  return { play, stop }
}
