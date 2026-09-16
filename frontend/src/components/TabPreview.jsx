import TabSvg from './TabSvg'

/** 画面上のTABプレビュー。書き出し用の固定レイアウトも同じ TabSvg を使う。 */
export default function TabPreview(props) {
  if (!props.result) {
    return (
      <div className="tab-empty">
        「TAB譜を生成」を押すと、ここに運指つきのTAB譜が表示されます。
      </div>
    )
  }
  return <TabSvg {...props} />
}
