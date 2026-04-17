/**
 * RealtimeContext — Shared live state from WebSocket events
 *
 * Provides:
 *   - recentEvents (last 50)
 *   - activeTriggers
 *   - claimUpdates
 *   - connectionHealth
 *   - liveNotifications (HIGH/CRITICAL events as toasts)
 */

import { createContext, useContext, useState, useCallback, useEffect, useRef } from 'react'
import useWebSocket, { WS_STATES } from '../hooks/useWebSocket'
import { useAuth } from '../hooks/useAuth'

const RealtimeContext = createContext(null)

const TRIGGER_EVENT_TYPES = ['TRIGGER_DETECTED', 'ZONE_ALERT']
const CLAIM_EVENT_TYPES = [
  'CLAIM_AUTO_FILED', 'INVESTIGATION_STARTED', 'INVESTIGATION_COMPLETED',
  'CLAIM_APPROVED', 'CLAIM_REJECTED', 'PAYOUT_INITIATED', 'PAYOUT_COMPLETED',
]
const NOTIFICATION_PRIORITIES = ['HIGH', 'CRITICAL']
const MAX_NOTIFICATIONS = 5
const NOTIFICATION_DISMISS_MS = 6000

export function RealtimeProvider({ children }) {
  const { user, isAuthenticated } = useAuth()
  const isAdmin = user?.role === 'ADMIN' || user?.role === 'SUPER_ADMIN'

  // Determine endpoint based on role
  const endpoint = isAdmin ? '/ws/admin' : '/ws/events'

  const [activeTriggers, setActiveTriggers] = useState([])
  const [claimUpdates, setClaimUpdates] = useState([])
  const [liveNotifications, setLiveNotifications] = useState([])
  const notifCounter = useRef(0)

  // Dismiss a notification
  const dismissNotification = useCallback((id) => {
    setLiveNotifications(prev => prev.filter(n => n.id !== id))
  }, [])

  // Auto-dismiss notifications after timeout
  useEffect(() => {
    if (liveNotifications.length === 0) return
    const timer = setTimeout(() => {
      setLiveNotifications(prev => prev.slice(0, -1))
    }, NOTIFICATION_DISMISS_MS)
    return () => clearTimeout(timer)
  }, [liveNotifications])

  // Handle incoming events
  const handleEvent = useCallback((event) => {
    // Update triggers
    if (TRIGGER_EVENT_TYPES.includes(event.event_type)) {
      setActiveTriggers(prev => {
        const next = [event, ...prev].slice(0, 20)
        return next
      })
    }

    // Update claims
    if (CLAIM_EVENT_TYPES.includes(event.event_type)) {
      setClaimUpdates(prev => {
        const next = [event, ...prev].slice(0, 30)
        return next
      })
    }

    // Create toast notification for high-priority events
    if (NOTIFICATION_PRIORITIES.includes(event.priority)) {
      notifCounter.current += 1
      const notif = {
        id: `notif_${notifCounter.current}`,
        event_type: event.event_type,
        priority: event.priority,
        zone_code: event.zone_code,
        message: _formatNotificationMessage(event),
        timestamp: event.timestamp,
      }
      setLiveNotifications(prev => [notif, ...prev].slice(0, MAX_NOTIFICATIONS))
    }
  }, [])

  const {
    events: recentEvents,
    connectionState,
    reconnectCount,
    lastEvent,
  } = useWebSocket(endpoint, {
    enabled: isAuthenticated,
    onEvent: handleEvent,
    maxEvents: 50,
  })

  const connectionHealth = {
    state: connectionState,
    reconnectCount,
    lastEventAt: lastEvent?.timestamp || null,
    isConnected: connectionState === WS_STATES.CONNECTED,
  }

  return (
    <RealtimeContext.Provider value={{
      recentEvents,
      activeTriggers,
      claimUpdates,
      liveNotifications,
      connectionHealth,
      dismissNotification,
      lastEvent,
      isAdmin,
    }}>
      {children}
    </RealtimeContext.Provider>
  )
}

export function useRealtime() {
  const ctx = useContext(RealtimeContext)
  if (!ctx) {
    // Return safe defaults when not wrapped in provider
    return {
      recentEvents: [],
      activeTriggers: [],
      claimUpdates: [],
      liveNotifications: [],
      connectionHealth: { state: 'DISCONNECTED', reconnectCount: 0, lastEventAt: null, isConnected: false },
      dismissNotification: () => {},
      lastEvent: null,
      isAdmin: false,
    }
  }
  return ctx
}

// ── Helpers ──────────────────────────────────────────────────────

function _formatNotificationMessage(event) {
  const d = event.data || {}
  switch (event.event_type) {
    case 'TRIGGER_DETECTED':
      return `${d.trigger_type || 'Event'} detected in ${d.zone_code || event.zone_code} — ${d.severity || 'HIGH'} severity`
    case 'ZONE_ALERT':
      return d.message || `Zone alert for ${event.zone_code}`
    case 'CLAIM_AUTO_FILED':
      return `Auto-claim filed for ₹${d.amount?.toLocaleString() || '?'} in ${event.zone_code}`
    case 'CLAIM_APPROVED':
      return `Claim approved — ₹${d.amount?.toLocaleString() || '?'} payout`
    case 'CLAIM_REJECTED':
      return `Claim rejected: ${d.reason || 'under review'}`
    case 'PAYOUT_COMPLETED':
      return `₹${d.amount?.toLocaleString() || '?'} paid via ${d.method || 'UPI'}`
    case 'FRAUD_RING_DETECTED':
      return `Fraud ring detected — ${d.member_count || '?'} workers flagged`
    case 'INVESTIGATION_STARTED':
      return `Investigation started on claim ${d.claim_id || ''}`
    case 'INVESTIGATION_COMPLETED':
      return `Investigation complete: ${d.result || ''} (${d.confidence_score?.toFixed(0) || '?'}% confidence)`
    case 'PAYOUT_INITIATED':
      return `Payout of ₹${d.amount?.toLocaleString() || '?'} initiated`
    default:
      return `${event.event_type} in ${event.zone_code}`
  }
}

export default RealtimeContext
