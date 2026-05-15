import axios from 'axios'
export const api = axios.create({ baseURL: '' })
export const getFailures  = () => api.get('/api/failures').then(r => r.data)
export const getPatches   = () => api.get('/api/patches').then(r => r.data)
export const getEvals     = () => api.get('/api/evals').then(r => r.data)
export const approvePatch = (id: string) => api.post(`/api/patches/${id}/approve`)
export const rejectPatch  = (id: string, notes: string) =>
  api.post(`/api/patches/${id}/reject`, { notes })
export const simulateFailure = (hint: string) =>
  api.post('/api/webhook/simulate', { failure_hint: hint })