import { useMemo } from 'react'

const LABEL_WIDTH = 26
const COLUMN_WIDTH = 34
// 和音では指番号を数字の左に置くため、列幅を広げて隣の列と重ならないようにする
const CHORD_COLUMN_WIDTH = 48
const MEASURE_PADDING = 18
const STRING_SPACING = 18
const BADGE_AREA = 34
const BRACKET_AREA = 40

const INK = '#2a2a28'
const MUTED = '#8a8a86'
const ACCENT = '#3f6fa8'
const HIGHLIGHT = '#d68b2c'
const WARN = '#b4652a'

/**
 * TAB譜のSVG（設計書 17.2 TAB譜プレビュー画面）。
 * 画面表示と画像書き出しの両方で使う。レイアウトは width だけで決まるため、
 * 書き出し時に固定幅を渡せばウィンドウサイズによらず同じ形になる。
 */
export default function TabSvg({
  result,
  score,
  selectedIds = [],
  highlightedNoteId = null,
  onSelectNote = () => {},
  onHoverNote = () => {},
  toggles,
  width,
  svgRef,
}) {
  const stringLabels = ['e', 'B', 'G', 'D', 'A', 'E']

  const hasChord = result?.fingerings?.some((fingering) => fingering.chordSize > 1) ?? false
  const columnWidth = hasChord && toggles.fingers ? CHORD_COLUMN_WIDTH : COLUMN_WIDTH

  const layout = useMemo(() => {
    if (!result) return null
    const available = Math.max(480, (width || 900) - 24)
    // 同じ拍位置の音（和音）はひとつの列にまとめる
    const byMeasure = new Map()
    result.fingerings.forEach((fingering) => {
      if (!byMeasure.has(fingering.measureIndex)) byMeasure.set(fingering.measureIndex, [])
      const columns = byMeasure.get(fingering.measureIndex)
      const last = columns[columns.length - 1]
      if (
        last &&
        !fingering.isRest &&
        !last[0].isRest &&
        Math.abs(last[0].onsetBeat - fingering.onsetBeat) < 1e-9
      ) {
        last.push(fingering)
      } else {
        columns.push([fingering])
      }
    })

    const rows = []
    let current = []
    let used = LABEL_WIDTH
    Array.from(byMeasure.keys())
      .sort((a, b) => a - b)
      .forEach((measureIndex) => {
        const items = byMeasure.get(measureIndex)
        const measureWidth = items.length * columnWidth + MEASURE_PADDING
        if (current.length > 0 && used + measureWidth > available) {
          rows.push(current)
          current = []
          used = LABEL_WIDTH
        }
        current.push({ measureIndex, items, width: measureWidth })
        used += measureWidth
      })
    if (current.length > 0) rows.push(current)

    const rowHeight = BADGE_AREA + STRING_SPACING * 5 + BRACKET_AREA
    const warningsByNote = new Map()
    result.warnings.forEach((warning) => {
      if (warning.noteIndex < 0) return
      if (!warningsByNote.has(warning.noteIndex)) warningsByNote.set(warning.noteIndex, [])
      warningsByNote.get(warning.noteIndex).push(warning)
    })

    const placed = rows.map((row, rowIndex) => {
      let x = LABEL_WIDTH
      const measures = row.map((measure) => {
        const startX = x
        const columns = measure.items.map((group, index) => ({
          group,
          fingering: group[0],
          x: startX + MEASURE_PADDING / 2 + index * columnWidth + columnWidth / 2,
          warnings: group.flatMap((item) => warningsByNote.get(item.noteIndex) ?? []),
        }))
        x += measure.width
        return { ...measure, startX, endX: x, columns }
      })
      return {
        rowIndex,
        y: rowIndex * (rowHeight + 16),
        measures,
        width: x,
      }
    })

    return { rows: placed, rowHeight, totalWidth: available }
  }, [result, width, columnWidth])

  if (!result || !layout) return null

  const totalHeight =
    layout.rows.length * (layout.rowHeight + 16) + 12 || layout.rowHeight

  const positionSpans = (columns) => {
    const spans = []
    columns.forEach(({ fingering, x }) => {
      if (fingering.isRest || fingering.position == null) return
      const last = spans[spans.length - 1]
      if (last && last.position === fingering.position) {
        last.endX = x
      } else {
        spans.push({ position: fingering.position, startX: x, endX: x })
      }
    })
    return spans.filter((span) => span.endX > span.startX)
  }

  return (
    <svg
      ref={svgRef}
      className="tab-svg"
      width={layout.totalWidth}
      height={totalHeight}
      viewBox={`0 0 ${layout.totalWidth} ${totalHeight}`}
      xmlns="http://www.w3.org/2000/svg"
    >
      <rect x="0" y="0" width={layout.totalWidth} height={totalHeight} fill="#ffffff" />
      {layout.rows.map((row) => {
        const top = row.y + BADGE_AREA
        const bottom = top + STRING_SPACING * 5
        return (
          <g key={row.rowIndex}>
            {stringLabels.map((label, index) => (
              <text
                key={label}
                x={4}
                y={top + index * STRING_SPACING + 4}
                fontSize="12"
                fontFamily="Georgia, serif"
                fill={INK}
              >
                {label}
              </text>
            ))}
            {stringLabels.map((label, index) => (
              <line
                key={`line-${label}`}
                x1={LABEL_WIDTH}
                x2={row.width}
                y1={top + index * STRING_SPACING}
                y2={top + index * STRING_SPACING}
                stroke={INK}
                strokeWidth="1"
              />
            ))}

            {row.measures.map((measure) => (
              <line
                key={`bar-${measure.measureIndex}`}
                x1={measure.endX}
                x2={measure.endX}
                y1={top}
                y2={bottom}
                stroke={MUTED}
                strokeWidth="1"
              />
            ))}

            {toggles.positions &&
              positionSpans(row.measures.flatMap((measure) => measure.columns)).map((span) => (
                <g key={`pos-${span.startX}`}>
                  <path
                    d={`M${span.startX} ${bottom + 14} L${span.startX} ${bottom + 20} L${span.endX} ${bottom + 20} L${span.endX} ${bottom + 14}`}
                    fill="none"
                    stroke={MUTED}
                    strokeWidth="1"
                  />
                  <text
                    x={(span.startX + span.endX) / 2}
                    y={bottom + 33}
                    fontSize="10"
                    fill={MUTED}
                    textAnchor="middle"
                  >
                    {span.position}フレットポジション
                  </text>
                </g>
              ))}

            {row.measures.flatMap((measure) =>
              measure.columns.map(({ group, fingering, x, warnings }) => {
                const noteIds = group.map((item) => score.notes[item.noteIndex]?.id)
                const noteId = noteIds[0]
                const isSelected = noteIds.some((id) => id && selectedIds.includes(id))
                const isHighlighted = noteIds.some((id) => id && highlightedNoteId === id)

                return (
                  <g
                    key={`col-${fingering.noteIndex}`}
                    className="tab-column"
                    onMouseEnter={() => onHoverNote(noteId ?? null)}
                    onMouseLeave={() => onHoverNote(null)}
                    onClick={() => noteId && onSelectNote(noteId)}
                  >
                    <rect
                      x={x - columnWidth / 2}
                      y={row.y + 6}
                      width={columnWidth}
                      height={BADGE_AREA + STRING_SPACING * 5 + 8}
                      fill={
                        isSelected
                          ? 'rgba(63,111,168,0.16)'
                          : isHighlighted
                            ? 'rgba(214,139,44,0.18)'
                            : 'transparent'
                      }
                      rx="4"
                    />

                    {group
                      .filter((item) => item.stringIndex != null)
                      .map((item) => {
                        const stringY = top + item.stringIndex * STRING_SPACING
                        const itemId = score.notes[item.noteIndex]?.id
                        const itemSelected = itemId && selectedIds.includes(itemId)
                        return (
                          <g key={`fret-${item.noteIndex}`}>
                            <rect x={x - 9} y={stringY - 8} width="18" height="16" fill="#ffffff" />
                            <text
                              x={x}
                              y={stringY + 4}
                              fontSize="13"
                              textAnchor="middle"
                              fontWeight={isSelected || isHighlighted ? '700' : '400'}
                              fill={itemSelected ? ACCENT : isHighlighted ? HIGHLIGHT : INK}
                            >
                              {item.isTiedContinuation ? `(${item.fret})` : item.fret}
                            </text>
                          </g>
                        )
                      })}

                    {toggles.fingers &&
                      group
                        .filter((item) => item.finger > 0 && item.stringIndex != null)
                        .map((item) => {
                          const stringY = top + item.stringIndex * STRING_SPACING
                          return (
                            <g key={`finger-${item.noteIndex}`}>
                              <circle
                                cx={x - 13}
                                cy={stringY}
                                r="6"
                                fill={item.isBarre ? ACCENT : INK}
                              />
                              <text
                                x={x - 13}
                                y={stringY + 3}
                                fontSize="8"
                                fill="#ffffff"
                                textAnchor="middle"
                              >
                                {item.finger}
                              </text>
                            </g>
                          )
                        })}

                    {toggles.shifts && fingering.handShift !== 0 && (
                      <text
                        x={x}
                        y={row.y + 8}
                        fontSize="9"
                        fill={WARN}
                        textAnchor="middle"
                      >
                        {fingering.handShift > 0 ? `▲${fingering.handShift}` : `▼${Math.abs(fingering.handShift)}`}
                      </text>
                    )}

                    {warnings.length > 0 && (
                      <path
                        d={`M${x} ${bottom + 4} l5 8 l-10 0 z`}
                        fill={WARN}
                      >
                        <title>{warnings.map((w) => w.message).join('\n')}</title>
                      </path>
                    )}
                  </g>
                )
              }),
            )}
          </g>
        )
      })}
    </svg>
  )
}
