import { useEffect, useRef, useState } from 'react'
import { wsUrl } from '../lib/api'

const PING_INTERVAL = 25_000

export default function LiveFeed() {
  const [events, setEvents]       = useState<string[]>([])
  const [status, setStatus]       = useState<'connecting' | 'live' | 'reconnecting'>('connecting')
  const [attempt, setAttempt]     = useState(0)
  const retryDelay                = useRef(1000)
  const timer                     = useRef<ReturnType<typeof setTimeout> | null>(null)
  const ping                      = useRef<ReturnType<typeof setInterval> | null>(null)
  const manualRetry               = useRef<() => void>(() => {})

  useEffect(() => {
    let ws: WebSocket
    let cancelled = false

    function connect() {
      if (cancelled) return
      setStatus('connecting')
      ws = new WebSocket(wsUrl)

      ws.onopen = () => {
        if (cancelled) { ws.close(); return }
        setStatus('live')
        retryDelay.current = 1000
        ping.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) ws.send('ping')
        }, PING_INTERVAL)
      }

      ws.onmessage = (e) => {
        if (e.data === 'pong') return
        try {
          const d = JSON.parse(e.data)
          setEvents(prev => [
            `${d.event}: ${d.failure_type || d.patch_id || d.eval_id || ''}`,
            ...prev.slice(0, 9),
          ])
        } catch { /* ignore malformed frames */ }
      }

      ws.onerror = () => {
        // onerror always fires before onclose — log and let onclose handle retry
        console.warn('[TraceGuard] WebSocket error — URL:', wsUrl)
      }

      ws.onclose = (e) => {
        if (ping.current) { clearInterval(ping.current); ping.current = null }
        if (cancelled) return
        console.warn(`[TraceGuard] WebSocket closed: code=${e.code} reason="${e.reason}"`)
        setStatus('reconnecting')
        setAttempt(n => n + 1)
        timer.current = setTimeout(() => {
          retryDelay.current = Math.min(retryDelay.current * 2, 30_000)
          connect()
        }, retryDelay.current)
      }
    }

    manualRetry.current = () => {
      if (timer.current) clearTimeout(timer.current)
      retryDelay.current = 1000
      connect()
    }

    connect()

    return () => {
      cancelled = true
      if (timer.current) clearTimeout(timer.current)
      if (ping.current)  clearInterval(ping.current)
      ws?.close()
    }
  }, [])

  const dot =
    status === 'live'         ? 'bg-green-400 animate-pulse' :
    status === 'reconnecting' ? 'bg-yellow-400 animate-pulse' :
                                'bg-gray-500 animate-pulse'

  const label =
    status === 'live'         ? 'Live' :
    status === 'reconnecting' ? `Reconnecting… (${attempt})` :
                                'Connecting…'

  return (
    <div className="flex items-center gap-2">
      <span className={`w-2 h-2 rounded-full ${dot}`} />
      <span className="text-xs text-gray-500">{label}</span>
      {status === 'reconnecting' && attempt > 3 && (
        <button
          onClick={() => manualRetry.current()}
          className="text-xs text-teal-400 hover:text-teal-300 underline ml-1"
        >
          Retry now
        </button>
      )}
      {status === 'live' && events[0] && (
        <span className="text-xs text-teal-300 ml-2 truncate max-w-[200px]">{events[0]}</span>
      )}
    </div>
  )
}
