import { useEffect, useState } from 'react'
import { wsUrl } from '../lib/api'

export default function LiveFeed() {
  const [events, setEvents] = useState<string[]>([])
  const [connected, setConnected] = useState(false)

  useEffect(() => {
    const ws = new WebSocket(wsUrl)
    ws.onopen  = () => setConnected(true)
    ws.onclose = () => setConnected(false)
    ws.onmessage = (e) => {
      const d = JSON.parse(e.data)
      setEvents(prev => [`${d.event}: ${d.failure_type || d.patch_id || d.eval_id || ''}`, ...prev.slice(0, 9)])
    }
    return () => ws.close()
  }, [])

  return (
    <div className="flex items-center gap-2">
      <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-400' : 'bg-red-400'}`} />
      <span className="text-xs text-gray-500">{connected ? 'Live' : 'Disconnected'}</span>
      {events[0] && <span className="text-xs text-teal-300 ml-2">{events[0]}</span>}
    </div>
  )
}