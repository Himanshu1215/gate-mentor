// Central API client. All components call this — never raw fetch.
// Base path is /api (Nginx proxies to FastAPI in prod; Vite proxies in dev).
// Backend accepts any non-empty Authorization header.

const AUTH = 'Bearer gate-mentor-app';

async function request(path, { method = 'GET', body, params } = {}) {
  let url = path;
  if (params) {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') qs.append(k, v);
    });
    const s = qs.toString();
    if (s) url += `?${s}`;
  }

  const opts = {
    method,
    headers: { Authorization: AUTH },
  };
  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }

  const res = await fetch(url, opts);
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const j = await res.json();
      detail = j.detail || detail;
    } catch (_) { /* ignore */ }
    const err = new Error(detail);
    err.status = res.status;
    throw err;
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  // chat / tutor
  chat: (query, sessionId, persona) =>
    request('/api/chat', { method: 'POST', body: { session_id: sessionId, query, persona } }),

  // concepts / topics
  getConcepts: () => request('/api/concepts'),

  // pyqs
  getPyqs: (params) => request('/api/pyqs', { params }),
  getPyqFilters: () => request('/api/pyqs/filters'),
  getPyq: (id) => request(`/api/pyqs/${id}`),

  // quiz
  quizNext: (params) => request('/api/quiz/next', { params }),
  submitQuiz: (payload) => request('/api/quiz/submit', { method: 'POST', body: payload }),

  // revision
  revisionDue: () => request('/api/revision/due'),

  // mock
  mockGenerate: () => request('/api/mock/generate'),
  mockGrade: (examId, answers) =>
    request('/api/mock/grade', { method: 'POST', body: { exam_id: examId, answers } }),

  // dashboard / coach / gamification / profile / analytics
  dashboardStats: () => request('/api/dashboard/stats'),
  curriculumNext: () => request('/api/curriculum/next'),
  coachAlerts: () => request('/api/coach/alerts'),
  gamification: () => request('/api/gamification'),
  getProfile: () => request('/api/profile'),
  putProfile: (payload) => request('/api/profile', { method: 'PUT', body: payload }),
  analytics: () => request('/api/analytics/overview'),
};

export default api;
