const TUNINGS = [
  { id: 'standard', label: 'レギュラー (EADGBE)' },
  { id: 'drop_d', label: 'ドロップD (DADGBE)' },
  { id: 'half_step_down', label: '半音下げ' },
]

const WARNING_LABELS = {
  shift_too_fast: '移動が間に合わない',
  large_position_shift: 'ポジション移動が大きい',
  same_string_stretch: '同弦での運指移動',
  high_position: '高ポジション',
  out_of_range: '音域外',
  parser: '読み込み',
}

/** 警告表示と生成設定（設計書 17.2 / 17.7.1）。 */
export default function WarningsPanel({ result, settings, onSettingsChange, onFocusNote }) {
  const warnings = result?.warnings ?? []

  const setWeight = (key, value) =>
    onSettingsChange({
      ...settings,
      weights: { ...settings.weights, [key]: value },
    })

  return (
    <aside className="side-panel">
      <section>
        <h3>警告 ({warnings.length})</h3>
        {warnings.length === 0 && (
          <p className="empty-note">
            {result ? '演奏上の問題は見つかりませんでした。' : 'TAB譜を生成すると表示されます。'}
          </p>
        )}
        <ul className="warning-list">
          {warnings.map((warning, index) => (
            <li key={`${warning.kind}-${warning.noteIndex}-${index}`}>
              <button type="button" onClick={() => onFocusNote(warning.noteIndex)}>
                <span className="warning-kind">{WARNING_LABELS[warning.kind] ?? warning.kind}</span>
                <span className="warning-message">{warning.message}</span>
              </button>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h3>生成設定</h3>
        <label className="field">
          <span>チューニング</span>
          <select
            value={settings.tuning}
            onChange={(event) => onSettingsChange({ ...settings, tuning: event.target.value })}
          >
            {TUNINGS.map((tuning) => (
              <option key={tuning.id} value={tuning.id}>
                {tuning.label}
              </option>
            ))}
          </select>
        </label>

        <label className="field">
          <span>記譜オクターブ</span>
          <select
            value={settings.notationOctaveShift}
            onChange={(event) =>
              onSettingsChange({ ...settings, notationOctaveShift: Number(event.target.value) })
            }
          >
            <option value={-1}>ギター記譜（実音より1オクターブ上）</option>
            <option value={0}>実音どおり</option>
          </select>
        </label>

        <label className="field">
          <span>
            ポジション移動を避ける度合い: {settings.weights?.position_change ?? 15}
          </span>
          <input
            type="range"
            min="0"
            max="30"
            step="1"
            value={settings.weights?.position_change ?? 15}
            onChange={(event) => setWeight('position_change', Number(event.target.value))}
          />
        </label>

        <label className="field">
          <span>開放弦を使う度合い: {settings.weights?.open_string_bonus ?? 2}</span>
          <input
            type="range"
            min="0"
            max="8"
            step="0.5"
            value={settings.weights?.open_string_bonus ?? 2}
            onChange={(event) => setWeight('open_string_bonus', Number(event.target.value))}
          />
        </label>

        <label className="field">
          <span>
            短い音価で動かせるフレット数: {settings.weights?.max_shift_short ?? 5}
          </span>
          <input
            type="range"
            min="2"
            max="12"
            step="1"
            value={settings.weights?.max_shift_short ?? 5}
            onChange={(event) => setWeight('max_shift_short', Number(event.target.value))}
          />
        </label>
      </section>

      {result?.totalCost != null && (
        <p className="cost-note">運指コスト合計: {result.totalCost.toFixed(1)}</p>
      )}
    </aside>
  )
}
