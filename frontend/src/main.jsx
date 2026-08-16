import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.jsx'
import AppState from './state/AppState.jsx'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <AppState>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </AppState>
  </React.StrictMode>,
)
