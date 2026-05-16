import { useEffect, useRef, useState } from 'react'
import { wsUrl } from '../lib/api'

const MAX_RETRIES    = 10
const PING_INTERVAL  = 25_000   // keep Railway's idle connection alive

export default function LiveFeed() {
  const [events, setEvents]       = useState<string[]>([])
  const [status, setStatus]       = useState<'connecting' | 'live' | 'reconnecting' | 'failed'>('connecting')
  const retryDelay                = useRef(1000)
  const retryCount                = useRef(0)
  const timer                     = useRef<ReturnType<typeof setTimeout> | null>(null)
  const ping                      = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    let ws: WebSocket
    let cancelled = false

    function connect() {
      if (cancelled) return
      ws = new WebSocket(wsUrl)

      ws.onopen = () => {
        if (cancelled) { ws.close(); return }
        setStatus('live')
        retryDelay.current = 1000
        retryCount.current = 0
        // heartbeat — send a ping frame every 25 s so Railway doesn't idle-close us
        ping.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) ws.send('ping')
        }, PING_INTERVAL)
      }

      ws.onmessage = (e) => {
        if (e.data === 'pong') return   // ignore server pong if backend ever sends one
        try {
          const d = JSON.parse(e.data)
          setEvents(prev => [
            `${d.event}: ${d.failure_type || d.patch_id || d.eval_id || ''}`,
            ...prev.slice(0, 9),
          ])
        } catch { /* ignore malformed frames */ }
      }

      ws.onerror = () => ws.close()

      ws.onclose = () => {
        if (ping.current) { clearInterval(ping.current); ping.current = null }
        if (cancelled) return
        retryCount.current += 1
        if (retryCount.current >= MAX_RETRIES) {
          setStatus('failed')
          return
        }
        setStatus('reconnecting')
        timer.current = setTimeout(() => {
          retryDelay.current = Math.min(retryDelay.current * 2, 30_000)
          connect()
        }, retryDelay.current)
      }
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
    status === 'failed'       ? 'bg-gray-600' :
                                'bg-yellow-400 animate-pulse'

  const label =
    status === 'live'         ? 'Live' :
    status === 'reconnecting' ? 'Reconnecting…' :
    status === 'failed'       ? 'No connection' :
                                'Connecting…'

  return (
    <div className="flex items-center gap-2">
      <span className={`w-2 h-2 rounded-full ${dot}`} />
      <span className="text-xs text-gray-500">{label}</span>
      {status === 'live' && events[0] && (
        <span className="text-xs text-teal-300 ml-2 truncate max-w-[200px]">{events[0]}</span>
      )}
    </div>
  )
}
