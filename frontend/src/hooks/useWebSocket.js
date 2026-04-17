/**
 * useWebSocket — Custom React hook for WebSocket connections
 *
 * Features:
 *   - Auto-reconnect with exponential backoff (1s → 30s max)
 *   - Connection state tracking
 *   - Event filtering by type
 *   - JWT authentication via query param
 */

import { useState, useEffect, useRef, useCallback } from 'react'

// Connection states
export const WS_STATES = {
  CONNECTING: 'CONNECTING',
  CONNECTED: 'CONNECTED',
  DISCONNECTED: 'DISCONNECTED',
  RECONNECTING: 'RECONNECTING',
}

const BACKOFF_BASE = 1000
const BACKOFF_MAX = 30000
const MAX_EVENTS = 100

export default function useWebSocket(endpoint = '/ws/events', options = {}) {
  const {
    enabled = true,
    filterTypes = null,       // array of event_type strings, or null for all
    maxEvents = MAX_EVENTS,
    onEvent = null,           // callback for each incoming event
  } = options

  const [connectionState, setConnectionState] = useState(WS_STATES.DISCONNECTED)
  const [events, setEvents] = useState([])
  const [lastEvent, setLastEvent] = useState(null)
  const [reconnectCount, setReconnectCount] = useState(0)

  const wsRef = useRef(null)
  const reconnectTimer = useRef(null)
  const backoffMs = useRef(BACKOFF_BASE)
  const isMounted = useRef(true)

  const connect = useCallback(() => {
    if (!enabled) return

    const token = localStorage.getItem('gs_token')
    if (!token) {
      setConnectionState(WS_STATES.DISCONNECTED)
      return
    }

    // Build WebSocket URL
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = import.meta.env.VITE_API_BASE_URL
      ? new URL(import.meta.env.VITE_API_BASE_URL).host
      : window.location.host
    const wsUrl = `${protocol}//${host}${endpoint}?token=${token}`

    setConnectionState(WS_STATES.CONNECTING)

    try {
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        if (!isMounted.current) return
        setConnectionState(WS_STATES.CONNECTED)
        backoffMs.current = BACKOFF_BASE
        setReconnectCount(0)
        console.log(`[WS] Connected to ${endpoint}`)
      }

      ws.onmessage = (msg) => {
        if (!isMounted.current) return
        try {
          const event = JSON.parse(msg.data)

          // Apply type filter
          if (filterTypes && !filterTypes.includes(event.event_type)) return

          setLastEvent(event)
          setEvents(prev => {
            const next = [event, ...prev]
            return next.slice(0, maxEvents)
          })

          if (onEvent) onEvent(event)
        } catch (e) {
          console.warn('[WS] Failed to parse message:', e)
        }
      }

      ws.onclose = (e) => {
        if (!isMounted.current) return
        console.log(`[WS] Disconnected (code=${e.code})`)

        // Don't reconnect on auth failures
        if (e.code === 4001 || e.code === 4003) {
          setConnectionState(WS_STATES.DISCONNECTED)
          return
        }

        setConnectionState(WS_STATES.RECONNECTING)
        scheduleReconnect()
      }

      ws.onerror = (err) => {
        console.warn('[WS] Error:', err)
      }
    } catch (err) {
      console.error('[WS] Connection failed:', err)
      setConnectionState(WS_STATES.RECONNECTING)
      scheduleReconnect()
    }
  }, [enabled, endpoint, filterTypes, maxEvents, onEvent])

  const scheduleReconnect = useCallback(() => {
    if (reconnectTimer.current) clearTimeout(reconnectTimer.current)

    const delay = Math.min(backoffMs.current, BACKOFF_MAX)
    console.log(`[WS] Reconnecting in ${delay}ms...`)

    reconnectTimer.current = setTimeout(() => {
      if (!isMounted.current) return
      backoffMs.current = Math.min(backoffMs.current * 2, BACKOFF_MAX)
      setReconnectCount(prev => prev + 1)
      connect()
    }, delay)
  }, [connect])

  const disconnect = useCallback(() => {
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current)
      reconnectTimer.current = null
    }
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    setConnectionState(WS_STATES.DISCONNECTED)
  }, [])

  const sendMessage = useCallback((data) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data))
    }
  }, [])

  const clearEvents = useCallback(() => {
    setEvents([])
    setLastEvent(null)
  }, [])

  // Connect on mount, disconnect on unmount
  useEffect(() => {
    isMounted.current = true
    connect()

    return () => {
      isMounted.current = false
      disconnect()
    }
  }, [endpoint, enabled])

  return {
    events,
    lastEvent,
    connectionState,
    reconnectCount,
    sendMessage,
    clearEvents,
    connect,
    disconnect,
  }
}
