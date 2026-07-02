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
  getChatSessions: () => request('/api/chat/sessions'),
  getChatHistory: (sessionId) => request(`/api/chat/history/${sessionId}`),

  // concepts / topics
  getConcepts: () => request('/api/concepts'),
  getConcept: (conceptId) => request(`/api/concepts/${conceptId}`),
  getConceptNotes: (conceptId) => request(`/api/concepts/${conceptId}/notes`),
  saveConceptNotes: (conceptId, content) =>
    request(`/api/concepts/${conceptId}/notes`, { method: 'PUT', body: { content } }),
  getStudyNotes: (conceptId) => request(`/api/concepts/${conceptId}/study-notes`),
  getConceptFiles: (conceptId) => request(`/api/concepts/${conceptId}/files`),
  uploadConceptFile: async (conceptId, file) => {
    const form = new FormData();
    form.append('concept_id', conceptId);
    form.append('file', file);
    const res = await fetch('/api/upload', {
      method: 'POST',
      headers: { Authorization: AUTH },
      body: form,
    });
    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        const j = await res.json();
        detail = j.detail || detail;
      } catch (_) { /* ignore */ }
      throw new Error(detail);
    }
    return res.json();
  },

  // pyqs
  getPyqs: (params) => request('/api/pyqs', { params }),
  getPyqFilters: () => request('/api/pyqs/filters'),
  getPyq: (id) => request(`/api/pyqs/${id}`),

  // quiz
  quizNext: (params) => request('/api/quiz/next', { params }),
  submitQuiz: (payload) => request('/api/quiz/submit', { method: 'POST', body: payload }),

  // mistakes & mock review
  getMistakes: (params) => request('/api/mistakes', { params }),
  getMockAttempts: () => request('/api/mock/attempts'),
  getMockReview: (examId) => request(`/api/mock/attempts/${examId}/review`),

  // revision
  revisionDue: () => request('/api/revision/due'),
  scheduleRevision: (conceptId, dueInDays = 1, questionId = null) =>
    request('/api/revision/schedule', {
      method: 'POST',
      body: { concept_id: conceptId || "", due_in_days: dueInDays, question_id: questionId },
    }),

  // mock
  mockGenerate: () => request('/api/mock/generate'),
  mockGrade: (examId, answers) =>
    request('/api/mock/grade', { method: 'POST', body: { exam_id: examId, answers } }),

  // dashboard / coach / gamification / profile / analytics
  startSession: (goals) => request('/api/session/start', { method: 'POST', body: { goals } }),
  endSession: (sessionId, reflection) => request('/api/session/end', { method: 'POST', body: { session_id: sessionId, reflection } }),
  dashboardStats: () => request('/api/dashboard/stats'),
  scheduleToday: () => request('/api/schedule/today'),
  curriculumNext: () => request('/api/curriculum/next'),
  coachAlerts: () => request('/api/coach/alerts'),
  gamification: () => request('/api/gamification'),
  getProfile: () => request('/api/profile'),
  putProfile: (payload) => request('/api/profile', { method: 'PUT', body: payload }),
  analytics: () => request('/api/analytics/overview'),
};

export default api;
