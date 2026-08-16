import { useEffect, useState } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import Shell from './components/shell/Shell.jsx'
import CommandPalette from './components/CommandPalette.jsx'
import Overview from './pages/Overview.jsx'
import UploadPage from './pages/Upload.jsx'
import DataBrowser from './pages/DataBrowser.jsx'
import ReportsPage from './pages/Reports.jsx'
import FormatsPage from './pages/Formats.jsx'
import SettingsPage from './pages/Settings.jsx'
import { useApp } from './state/AppState.jsx'
import { api, fmt } from './api.js'

/** Row counts shown against the sidebar items. */
function useNavCounts() {
  const { clientId, ready } = useApp()
  const [counts, setCounts] = useState({})

  useEffect(() => {
    if (!ready || !clientId) return
    let alive = true
    Promise.all([api.summary(), api.uploads(), api.reports()])
      .then(([summary, uploads, reports]) => {
        if (!alive) return
        const rows = Object.values(summary.tables || {}).reduce((sum, t) => sum + (t.rows || 0), 0)
        setCounts({
          '/data': fmt.compact(rows),
          '/ingest': uploads.length || undefined,
          '/reports': reports.length || undefined,
        })
      })
      .catch(() => setCounts({}))
    return () => { alive = false }
  }, [clientId, ready])

  return counts
}

export default function App() {
  const counts = useNavCounts()

  return (
    <>
      <Shell counts={counts}>
        <Routes>
          <Route path="/" element={<Navigate to="/overview" replace />} />
          <Route path="/dashboard" element={<Navigate to="/overview" replace />} />
          <Route path="/overview" element={<Overview />} />
          <Route path="/data" element={<DataBrowser />} />
          <Route path="/ingest" element={<UploadPage />} />
          <Route path="/upload" element={<Navigate to="/ingest" replace />} />
          <Route path="/reports" element={<ReportsPage />} />
          <Route path="/reports/:id" element={<ReportsPage />} />
          <Route path="/formats" element={<FormatsPage />} />
          <Route path="/methodology" element={<SettingsPage />} />
          <Route path="/settings" element={<Navigate to="/methodology" replace />} />
          <Route path="*" element={<Navigate to="/overview" replace />} />
        </Routes>
      </Shell>
      <CommandPalette />
    </>
  )
}
