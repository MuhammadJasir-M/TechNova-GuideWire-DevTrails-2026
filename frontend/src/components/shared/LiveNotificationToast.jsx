/**
 * LiveNotificationToast — Real-time toast notifications for critical events
 *
 * Displays animated toast notifications in the top-right corner:
 *   - Slide-in animation
 *   - Auto-dismiss after 5 seconds
 *   - Priority-based styling (CRITICAL = red pulse, HIGH = amber)
 *   - Stacks up to 3 visible toasts
 */

import { useRealtime } from '../../context/RealtimeContext'
import { X, AlertTriangle, Zap, ShieldAlert, CircleDollarSign } from 'lucide-react'

const PRIORITY_STYLES = {
  CRITICAL: {
    bg: 'bg-gradient-to-r from-red-900/90 to-red-800/90',
    border: 'border-red-500/50',
    icon: ShieldAlert,
    iconColor: 'text-red-400',
    pulse: true,
  },
  HIGH: {
    bg: 'bg-gradient-to-r from-amber-900/90 to-amber-800/90',
    border: 'border-amber-500/50',
    icon: AlertTriangle,
    iconColor: 'text-amber-400',
    pulse: false,
  },
}

const EVENT_LABELS = {
  TRIGGER_DETECTED: 'Trigger Detected',
  ZONE_ALERT: 'Zone Alert',
  CLAIM_AUTO_FILED: 'Claim Auto-Filed',
  CLAIM_APPROVED: 'Claim Approved',
  CLAIM_REJECTED: 'Claim Rejected',
  PAYOUT_INITIATED: 'Payout Initiated',
  PAYOUT_COMPLETED: 'Payout Completed',
  FRAUD_RING_DETECTED: 'Fraud Ring Detected',
  INVESTIGATION_STARTED: 'Investigation Started',
  INVESTIGATION_COMPLETED: 'Investigation Complete',
}

export default function LiveNotificationToast() {
  const { liveNotifications, dismissNotification, connectionHealth } = useRealtime()

  // Only show when connected
  if (!connectionHealth.isConnected) return null

  // Display max 3
  const visible = liveNotifications.slice(0, 3)
  if (visible.length === 0) return null

  return (
    <div className="fixed top-20 right-4 z-50 flex flex-col gap-3 w-80 pointer-events-none">
      {visible.map((notif, idx) => {
        const style = PRIORITY_STYLES[notif.priority] || PRIORITY_STYLES.HIGH
        const Icon = style.icon
        const label = EVENT_LABELS[notif.event_type] || notif.event_type

        return (
          <div
            key={notif.id}
            className={`pointer-events-auto rounded-2xl border backdrop-blur-xl shadow-2xl
              ${style.bg} ${style.border}
              animate-slide-in transition-all duration-300`}
            style={{
              animationDelay: `${idx * 80}ms`,
              opacity: 1 - idx * 0.15,
            }}
          >
            {/* Pulse bar for CRITICAL */}
            {style.pulse && (
              <div className="absolute top-0 left-0 right-0 h-0.5 bg-red-500 rounded-t-2xl">
                <div className="h-full bg-red-400 animate-pulse rounded-t-2xl" />
              </div>
            )}

            <div className="flex items-start gap-3 p-3.5">
              {/* Icon */}
              <div className={`w-8 h-8 rounded-xl flex items-center justify-center bg-white/10 flex-shrink-0 mt-0.5`}>
                <Icon className={`w-4 h-4 ${style.iconColor}`} />
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-bold text-white uppercase tracking-wider">{label}</span>
                </div>
                <p className="text-xs text-gray-200 leading-relaxed line-clamp-2">
                  {notif.message}
                </p>
                {notif.zone_code && (
                  <span className="inline-block mt-1.5 text-[10px] px-2 py-0.5 rounded-full bg-white/10 text-gray-300">
                    {notif.zone_code}
                  </span>
                )}
              </div>

              {/* Close */}
              <button
                onClick={() => dismissNotification(notif.id)}
                className="text-gray-400 hover:text-white transition-colors flex-shrink-0"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )
      })}
    </div>
  )
}
