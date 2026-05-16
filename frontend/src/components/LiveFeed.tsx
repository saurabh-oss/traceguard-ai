import { useEffect, useRef, useState } from 'react'
import { wsUrl } from '../lib/api'

export default function LiveFeed() {
  const [events, setEvents]       = useState<string[]>([])
  const [connected, setConnected] = useState(false)
  const retryDelay                = useRef(1000)
  const timer                     = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    let ws: WebSocket
    let cancelled = false

    function connect() {
      if (cancelled) return
      ws = new WebSocket(wsUrl)

      ws.onopen = () => {
        if (cancelled) { ws.close(); return }
        setConnected(true)
        retryDelay.current = 1000        // reset backoff on success
      }

      ws.onmessage = (e) => {
        try {
          const d = JSON.parse(e.data)
          setEvents(prev => [
            `${d.event}: ${d.failure_type || d.patch_id || d.eval_id || ''}`,
            ...prev.slice(0, 9),
          ])
        } catch { /* ignore malformed frames */ }
      }

      ws.onerror = () => ws.close()     // let onclose handle retry

      ws.onclose = () => {
        if (cancelled) return
        setConnected(false)
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
      ws?.close()
    }
  }, [])

  return (
    <div className="flex items-center gap-2">
      <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-400 animate-pulse' : 'bg-red-400'}`} />
      <span className="text-xs text-gray-500">{connected ? 'Live' : 'Reconnecting…'}</span>
      {events[0] && <span className="text-xs text-teal-300 ml-2">{events[0]}</span>}
    </div>
  )
}
