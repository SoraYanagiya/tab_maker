import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'

function formatDate(iso) {
  if (!iso) return '-'
  const date = new Date(iso)
  return date.toLocaleString('ja-JP', { dateStyle: 'medium', timeStyle: 'short' })
}

/** プロジェクト一覧画面（設計書 17.2 / 17.7）。 */
export default function ProjectList({ onOpen }) {
  const [projects, setProjects] = useState([])
  const [query, setQuery] = useState('')
  const [sort, setSort] = useState('updatedAt')
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  const reload = async () => {
    try {
      setProjects(await api.listProjects())
      setError(null)
    } catch (loadError) {
      setError(loadError.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    reload()
  }, [])

  const visible = useMemo(() => {
    const filtered = projects.filter((project) =>
      project.name.toLowerCase().includes(query.trim().toLowerCase()),
    )
    return filtered.sort((a, b) => {
      if (sort === 'name') return a.name.localeCompare(b.name, 'ja')
      return (b[sort] ?? '').localeCompare(a[sort] ?? '')
    })
  }, [projects, query, sort])

  const create = async () => {
    const name = window.prompt('プロジェクト名', '新しい曲')
    if (name === null) return
    const project = await api.createProject({ name: name || '無題のプロジェクト' })
    onOpen(project.projectId)
  }

  const rename = async (project) => {
    const name = window.prompt('プロジェクト名', project.name)
    if (name === null || name === project.name) return
    await api.updateProject(project.projectId, { name })
    reload()
  }

  const duplicate = async (project) => {
    await api.duplicateProject(project.projectId, `${project.name} のコピー`)
    reload()
  }

  const remove = async (project) => {
    if (!window.confirm(`「${project.name}」を削除しますか？`)) return
    await api.deleteProject(project.projectId)
    reload()
  }

  return (
    <div className="screen">
      <header className="app-header">
        <div className="app-title">
          <h1>ギターTAB譜メーカー</h1>
          <span className="subtitle">プロジェクト一覧</span>
        </div>
        <button type="button" className="primary-button" onClick={create}>
          新規プロジェクト
        </button>
      </header>

      <div className="list-toolbar">
        <input
          type="search"
          placeholder="プロジェクトを検索"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <select value={sort} onChange={(event) => setSort(event.target.value)}>
          <option value="updatedAt">更新日時順</option>
          <option value="createdAt">作成日時順</option>
          <option value="name">名前順</option>
        </select>
      </div>

      {error && <div className="error-banner">読み込みに失敗しました: {error}</div>}

      <div className="project-grid">
        {loading && <p className="empty-note">読み込み中…</p>}
        {!loading && visible.length === 0 && (
          <p className="empty-note">
            プロジェクトがありません。「新規プロジェクト」から作成してください。
          </p>
        )}
        {visible.map((project) => (
          <article key={project.projectId} className="project-card">
            <button
              type="button"
              className="project-open"
              onClick={() => onOpen(project.projectId)}
            >
              <h2>{project.name}</h2>
              <dl>
                <div>
                  <dt>更新</dt>
                  <dd>{formatDate(project.updatedAt)}</dd>
                </div>
                <div>
                  <dt>音符</dt>
                  <dd>{project.noteCount} 個 / {project.measureCount} 小節</dd>
                </div>
                <div>
                  <dt>TAB</dt>
                  <dd>{project.hasGeneratedTab ? '生成済み' : '未生成'}</dd>
                </div>
              </dl>
            </button>
            <div className="project-actions">
              <button type="button" onClick={() => rename(project)}>
                名前変更
              </button>
              <button type="button" onClick={() => duplicate(project)}>
                複製
              </button>
              <button type="button" className="danger" onClick={() => remove(project)}>
                削除
              </button>
            </div>
          </article>
        ))}
      </div>
    </div>
  )
}
