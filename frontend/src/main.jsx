import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { AuthProvider } from './context/AuthContext'
import { WorkerProvider } from './context/WorkerContext'
import { RealtimeProvider } from './context/RealtimeContext'
import LiveNotificationToast from './components/shared/LiveNotificationToast'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <RealtimeProvider>
          <WorkerProvider>
            <App />
            <LiveNotificationToast />
          </WorkerProvider>
        </RealtimeProvider>
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
)
