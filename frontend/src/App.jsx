import { useEffect, useState } from 'react'
import EditorScreen from './components/EditorScreen'
import ProjectList from './components/ProjectList'

function currentProjectId() {
  const hash = window.location.hash.replace('#', '')
  return hash.startsWith('project/') ? hash.slice('project/'.length) : null
}

export default function App() {
  const [projectId, setProjectId] = useState(currentProjectId)

  useEffect(() => {
    const onHashChange = () => setProjectId(currentProjectId())
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  const open = (id) => {
    window.location.hash = `project/${id}`
    setProjectId(id)
  }

  const back = () => {
    window.location.hash = ''
    setProjectId(null)
  }

  return projectId ? (
    <EditorScreen projectId={projectId} onBack={back} />
  ) : (
    <ProjectList onOpen={open} />
  )
}
