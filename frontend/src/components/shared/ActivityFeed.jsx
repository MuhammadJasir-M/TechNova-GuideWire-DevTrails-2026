/**
 * ActivityFeed — Live event timeline component
 *
 * Shows a scrolling feed of incoming real-time events with:
 *   - Animated entry for new items
 *   - Color-coded by priority
 *   - Relative timestamps
 *   - Connection status indicator
 */

import { useState, useEffect, useRef } from 'react'
import { useRealtime } from '../../context/RealtimeContext'
import { Activity, Wifi, WifiOff, ChevronDown, ChevronUp } from 'lucide-react'

const PRIORITY_COLORS = {
  CRITICAL: { bg: 'bg-red-500/20', border: 'border-red-500/40', text: 'text-red-400', dot: 'bg-red-500' },
  HIGH: { bg: 'bg-amber-500/20', border: 'border-amber-500/40', text: 'text-amber-400', dot: 'bg-amber-500' },
  MEDIUM: { bg: 'bg-blue-500/20', border: 'border-blue-500/40', text: 'text-blue-400', dot: 'bg-blue-500' },
  LOW: { bg: 'bg-slate-500/20', border: 'border-slate-500/40', text: 'text-slate-400', dot: 'bg-slate-500' },
}

const EVENT_ICONS = {
  TRIGGER_DETECTED: '⚡',
  ZONE_ALERT: '🔔',
  CLAIM_AUTO_FILED: '📋',
  INVESTIGATION_STARTED: '🔍',
  INVESTIGATION_COMPLETED: '✅',
  CLAIM_APPROVED: '✓',
  CLAIM_REJECTED: '✗',
  PAYOUT_INITIATED: '💳',
  PAYOUT_COMPLETED: '💰',
  FRAUD_RING_DETECTED: '🚨',
}

function relativeTime(isoStr) {
  if (!isoStr) return ''
  const diff = (Date.now() - new Date(isoStr).getTime()) / 1000
  if (diff < 5) return 'just now'
  if (diff < 60) return `${Math.floor(diff)}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  return `${Math.floor(diff / 3600)}h ago`
}

function formatEventType(type) {
  return (type || '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

export default function ActivityFeed({ maxItems = 25, compact = false }) {
  const { recentEvents, connectionHealth } = useRealtime()
  const [collapsed, setCollapsed] = useState(false)
  const [autoScroll, setAutoScroll] = useState(true)
  const feedRef = useRef(null)
  const prevCountRef = useRef(0)

  // Auto-scroll when new events arrive
  useEffect(() => {
    if (autoScroll && feedRef.current && recentEvents.length > prevCountRef.current) {
      feedRef.current.scrollTop = 0
    }
    prevCountRef.current = recentEvents.length
  }, [recentEvents.length, autoScroll])

  const displayEvents = recentEvents.slice(0, maxItems)
  const { isConnected } = connectionHealth

  return (
    <div className="glass-card overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-white/10">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-shield-400" />
          <h3 className="text-sm font-semibold text-white">Live Activity</h3>
          {/* Connection indicator */}
          <span className="flex items-center gap-1 ml-2">
            {isConnected ? (
              <>
                <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                <span className="text-xs text-green-400">Live</span>
              </>
            ) : (
              <>
                <span className="w-2 h-2 rounded-full bg-red-500" />
                <span className="text-xs text-red-400">
                  {connectionHealth.state === 'RECONNECTING' ? 'Reconnecting...' : 'Offline'}
                </span>
              </>
            )}
          </span>
        </div>
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="text-gray-400 hover:text-white transition-colors"
        >
          {collapsed ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
        </button>
      </div>

      {/* Feed */}
      {!collapsed && (
        <div
          ref={feedRef}
          className={`overflow-y-auto ${compact ? 'max-h-60' : 'max-h-96'} p-2 space-y-1.5`}
          onScroll={(e) => {
            // Pause auto-scroll if user scrolls away from top
            setAutoScroll(e.target.scrollTop < 10)
          }}
        >
          {displayEvents.length === 0 ? (
            <div className="text-center py-8 text-gray-500 text-sm">
              <Activity className="w-6 h-6 mx-auto mb-2 opacity-50" />
              {isConnected ? 'Waiting for events...' : 'Connect to see live events'}
            </div>
          ) : (
            displayEvents.map((event, idx) => {
              const colors = PRIORITY_COLORS[event.priority] || PRIORITY_COLORS.LOW
              const icon = EVENT_ICONS[event.event_type] || '📌'
              const isNew = idx === 0 && Date.now() - new Date(event.timestamp).getTime() < 5000

              return (
                <div
                  key={event.event_id || idx}
                  className={`flex items-start gap-3 p-2.5 rounded-xl border transition-all duration-500 ${colors.bg} ${colors.border}
                    ${isNew ? 'animate-slide-in ring-1 ring-white/10' : ''}`}
                >
                  {/* Priority dot + icon */}
                  <div className="flex flex-col items-center gap-1 pt-0.5">
                    <span className={`w-2 h-2 rounded-full ${colors.dot} ${isNew ? 'animate-pulse' : ''}`} />
                    <span className="text-sm">{icon}</span>
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className={`text-xs font-semibold uppercase tracking-wide ${colors.text}`}>
                        {formatEventType(event.event_type)}
                      </span>
                      <span className="text-[10px] text-gray-500">
                        {relativeTime(event.timestamp)}
                      </span>
                    </div>

                    {/* Zone + Worker */}
                    <div className="flex items-center gap-2 text-[11px] text-gray-400">
                      {event.zone_code && (
                        <span className="px-1.5 py-0.5 rounded bg-white/5">{event.zone_code}</span>
                      )}
                      {event.worker_id && (
                        <span>Worker: {event.worker_id}</span>
                      )}
                    </div>

                    {/* Key data snippet */}
                    {event.data && !compact && (
                      <div className="mt-1 text-[11px] text-gray-500 truncate">
                        {_dataSnippet(event)}
                      </div>
                    )}
                  </div>
                </div>
              )
            })
          )}
        </div>
      )}

      {/* Footer - event count */}
      {!collapsed && displayEvents.length > 0 && (
        <div className="px-4 py-2 border-t border-white/5 text-[10px] text-gray-500 flex justify-between">
          <span>{displayEvents.length} events</span>
          {!autoScroll && (
            <button
              onClick={() => { setAutoScroll(true); if (feedRef.current) feedRef.current.scrollTop = 0 }}
              className="text-shield-400 hover:text-shield-300"
            >
              ↑ Jump to latest
            </button>
          )}
        </div>
      )}
    </div>
  )
}

function _dataSnippet(event) {
  const d = event.data || {}
  switch (event.event_type) {
    case 'TRIGGER_DETECTED':
      return `${d.trigger_type || ''} — ${d.rainfall_mm ? d.rainfall_mm + 'mm' : ''} ${d.temperature_c ? d.temperature_c + '°C' : ''}`
    case 'CLAIM_AUTO_FILED':
      return `₹${d.amount?.toLocaleString() || '?'} • ${d.disruption_hours || '?'}h disruption`
    case 'PAYOUT_COMPLETED':
      return `₹${d.amount?.toLocaleString() || '?'} via ${d.method || 'UPI'} (${d.transaction_id || ''})`
    case 'FRAUD_RING_DETECTED':
      return `${d.member_count || '?'} members • ${d.detection_method || ''} • ₹${d.frozen_amount?.toLocaleString() || '?'} frozen`
    case 'INVESTIGATION_COMPLETED':
      return `${d.result || ''} — ${d.confidence_score?.toFixed(0) || '?'}% confidence`
    default:
      return Object.entries(d).slice(0, 3).map(([k, v]) => `${k}: ${v}`).join(' • ')
  }
}
