import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom'
import Dashboard   from './pages/Dashboard'
import PatchReview from './pages/PatchReview'
import EvalVault   from './pages/EvalVault'
import LiveFeed    from './components/LiveFeed'

const qc = new QueryClient()

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <div className="min-h-screen bg-gray-950 text-gray-100">
          <nav className="border-b border-gray-800 px-6 py-3 flex items-center gap-8 bg-gray-900">
            <span className="font-bold text-teal-400 text-lg">🛡️ TraceGuard AI</span>
            <Link to="/"       className="text-sm text-gray-400 hover:text-white transition">Dashboard</Link>
            <Link to="/patches" className="text-sm text-gray-400 hover:text-white transition">Patches</Link>
            <Link to="/evals"   className="text-sm text-gray-400 hover:text-white transition">Eval Vault</Link>
            <div className="ml-auto"><LiveFeed /></div>
          </nav>
          <main className="p-6">
            <Routes>
              <Route path="/"        element={<Dashboard />} />
              <Route path="/patches" element={<PatchReview />} />
              <Route path="/evals"   element={<EvalVault />} />
            </Routes>
          </main>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  )
}