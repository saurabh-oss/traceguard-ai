import axios from 'axios'
const _base = import.meta.env.VITE_API_URL ?? ''
const _key  = import.meta.env.VITE_API_KEY ?? ''
export const api = axios.create({
  baseURL: _base,
  headers: _key ? { 'X-API-Key': _key } : {},
})
export const wsUrl = _base
  ? _base.replace(/^http/, 'ws') + '/ws'
  : `ws://${location.host}/ws`
export const getFailures  = () => api.get('/api/failures').then(r => r.data)
export const getPatches   = () => api.get('/api/patches').then(r => r.data)
export const getEvals     = () => api.get('/api/evals').then(r => r.data)
export const approvePatch = (id: string) => api.post(`/api/patches/${id}/approve`)
export const rejectPatch  = (id: string, notes: string) =>
  api.post(`/api/patches/${id}/reject`, { notes })
export const simulateFailure = (hint: string) =>
  api.post('/api/webhook/simulate', { failure_hint: hint })
export const getStats = () => api.get('/api/stats').then(r => r.data)