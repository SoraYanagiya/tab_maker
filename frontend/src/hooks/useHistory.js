import { useCallback, useRef, useState } from 'react'

const LIMIT = 100

/**
 * Undo/Redo 付きの状態。
 * coalesceKey を指定すると、同じキーの連続した更新は1つの操作としてまとめられる
 * （ドラッグによる音高変更などで履歴が埋まらないようにするため）。
 */
export function useHistory(initialState) {
  const [state, setState] = useState({ past: [], present: initialState, future: [] })
  const lastKey = useRef(null)

  const set = useCallback((value, options = {}) => {
    const { coalesceKey = null } = options
    setState((current) => {
      const next = typeof value === 'function' ? value(current.present) : value
      if (next === current.present) return current
      const shouldCoalesce = coalesceKey !== null && coalesceKey === lastKey.current
      lastKey.current = coalesceKey
      if (shouldCoalesce) {
        return { ...current, present: next, future: [] }
      }
      return {
        past: [...current.past, current.present].slice(-LIMIT),
        present: next,
        future: [],
      }
    })
  }, [])

  const reset = useCallback((value) => {
    lastKey.current = null
    setState({ past: [], present: value, future: [] })
  }, [])

  const undo = useCallback(() => {
    lastKey.current = null
    setState((current) => {
      if (current.past.length === 0) return current
      const previous = current.past[current.past.length - 1]
      return {
        past: current.past.slice(0, -1),
        present: previous,
        future: [current.present, ...current.future],
      }
    })
  }, [])

  const redo = useCallback(() => {
    lastKey.current = null
    setState((current) => {
      if (current.future.length === 0) return current
      const [next, ...rest] = current.future
      return { past: [...current.past, current.present], present: next, future: rest }
    })
  }, [])

  return {
    state: state.present,
    set,
    reset,
    undo,
    redo,
    canUndo: state.past.length > 0,
    canRedo: state.future.length > 0,
  }
}
