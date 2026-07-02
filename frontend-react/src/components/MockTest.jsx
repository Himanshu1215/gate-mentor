import React, { useState, useEffect, useRef, useCallback } from 'react';
import api from '../api';
import { useApp } from '../context/AppContext';
import MathText from './MathText';

function fmt(s) {
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
  const pad = (n) => String(n).padStart(2, '0');
  return `${pad(h)}:${pad(m)}:${pad(sec)}`;
}

function Ring({ progress, size = 160, stroke = 12, children }) {
  const r = (size - stroke) / 2, c = 2 * Math.PI * r;
  const off = c * (1 - Math.max(0, Math.min(1, progress)));
  return (
    <div className="score-ring" style={{ width: size, height: size }}>
      <svg width={size} height={size}>
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth={stroke} />
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="url(#mg)" strokeWidth={stroke}
          strokeDasharray={c} strokeDashoffset={off} strokeLinecap="round" transform={`rotate(-90 ${size/2} ${size/2})`} />
        <defs><linearGradient id="mg" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stopColor="#7c3aed"/><stop offset="100%" stopColor="#00f0ff"/></linearGradient></defs>
      </svg>
      <div className="sr-label">{children}</div>
    </div>
  );
}

export default function MockTest({ navigate }) {
  const { refresh, mockState, setMockState } = useApp();
  
  // Local state for UI only
  const [loading, setLoading] = useState(false);
  const [reflection, setReflection] = useState('');
  const [reflectionSubmitted, setReflectionSubmitted] = useState(false);
  const [sessionId, setSessionId] = useState('');
  const timerRef = useRef(null);

  // Sync variables from mockState or defaults
  const phase = mockState?.phase || 'intro';
  const exam = mockState?.exam || null;
  const idx = mockState?.idx || 0;
  const answers = mockState?.answers || {};
  const review = new Set(mockState?.review || []);
  const secondsLeft = mockState?.secondsLeft || 0;
  const report = mockState?.report || null;

  const updateState = (updates) => {
    setMockState(prev => ({ ...prev, ...updates }));
  };

  const start = async () => {
    setLoading(true);
    try {
      const e = await api.mockGenerate();
      updateState({
        exam: e, idx: 0, answers: {}, review: [],
        secondsLeft: (e.duration_mins || 180) * 60,
        phase: 'running', report: null
      });
      setReflection(''); setReflectionSubmitted(false);
      try {
        const { session_id } = await api.startSession(`Mock Test: ${e.exam_id}`);
        setSessionId(session_id);
      } catch (err) {}
    } catch (err) { alert('Could not start mock: ' + err.message); }
    finally { setLoading(false); }
  };

  const submit = useCallback(async () => {
    if (timerRef.current) clearInterval(timerRef.current);
    setLoading(true);
    try {
      const r = await api.mockGrade(exam.exam_id, answers);
      updateState({ report: r, phase: 'report' });
      refresh();
    } catch (err) { alert('Grading failed: ' + err.message); }
    finally { setLoading(false); }
  }, [exam, answers, refresh, setMockState]);

  useEffect(() => {
    if (phase !== 'running') return;
    timerRef.current = setInterval(() => {
      let isDone = false;
      setMockState(prev => {
        if (!prev || prev.phase !== 'running') return prev;
        const s = prev.secondsLeft;
        if (s <= 1) { isDone = true; return { ...prev, secondsLeft: 0 }; }
        return { ...prev, secondsLeft: s - 1 };
      });
      if (isDone) {
        clearInterval(timerRef.current);
        submit();
      }
    }, 1000);
    return () => clearInterval(timerRef.current);
  }, [phase, submit, setMockState]);

  // ── intro ──────────────────────────────────────────────────────────────────
  if (phase === 'intro') {
    return (
      <div>
        <header className="page-header"><div><h1>Mock Test</h1><p className="subtitle">Full GATE-pattern paper from the real PYQ bank.</p></div></header>
        {mockState?.phase === 'running' && (
          <div className="card" style={{ maxWidth: 560, marginBottom: '1rem', borderLeft: '4px solid var(--primary)' }}>
            <h2>Mock in Progress</h2>
            <p style={{ color: 'var(--text-secondary)' }}>You have a mock exam currently running ({fmt(secondsLeft)} remaining).</p>
            <button className="btn-primary" style={{ marginTop: '1rem' }} onClick={() => updateState({ phase: 'running' })}>Resume mock</button>
            <button className="btn-secondary" style={{ marginTop: '1rem', marginLeft: '1rem' }} onClick={() => setMockState(null)}>Abandon mock</button>
          </div>
        )}
        <div className="card" style={{ maxWidth: 560 }}>
          <h2>GATE DA — Full Mock</h2>
          <ul style={{ color: 'var(--text-secondary)', lineHeight: 2, listStyle: 'none' }}>
            <li>📝 65 questions drawn from real previous-year papers</li>
            <li>⏱️ 3-hour timer (auto-submits at zero)</li>
            <li>➖ Negative marking on MCQs (GATE rules)</li>
            <li>🏁 Score report with per-subject breakdown</li>
          </ul>
          <button className="btn-primary" style={{ marginTop: '1rem' }} onClick={start} disabled={loading || mockState?.phase === 'running'}>
            {loading ? 'Preparing…' : 'Begin new mock test'}
          </button>
        </div>
      </div>
    );
  }

  // ── report ──────────────────────────────────────────────────────────────────
  if (phase === 'report' && report) {
    const pct = report.max_score ? Math.max(0, report.total_score) / report.max_score : 0;
    return (
      <div>
        <header className="page-header"><div><h1>Mock Result</h1><p className="subtitle">Here's how you did.</p></div>
          <button className="btn-primary" onClick={() => setMockState(null)}>Take another</button>
        </header>
        <div className="quiz-summary">
          <Ring progress={pct}><div className="sr-label"><b>{report.total_score}</b><small>/ {report.max_score}</small></div></Ring>
        </div>
        <div className="report-grid">
          <div className="stat-card card"><span className="value good">{report.correct_answers}</span><span className="label">Correct</span></div>
          <div className="stat-card card"><span className="value" style={{ color: 'var(--danger)' }}>{report.incorrect_answers}</span><span className="label">Incorrect</span></div>
          <div className="stat-card card"><span className="value">{report.unattempted}</span><span className="label">Unattempted</span></div>
          <div className="stat-card card"><span className="value">{report.accuracy}%</span><span className="label">Accuracy</span></div>
        </div>
        <div className="card">
          <h2>Per-subject breakdown</h2>
          {Object.entries(report.per_subject || {}).map(([s, v]) => {
            const totalQ = v.correct + v.incorrect + v.unattempted;
            const pctS = totalQ ? (v.correct / totalQ) * 100 : 0;
            return (
              <div className="subject-bar" key={s}>
                <span className="sb-name">{s}</span>
                <div className="sb-track"><div className="sb-fill" style={{ width: `${pctS}%` }} /></div>
                <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', width: 90, textAlign: 'right' }}>{v.correct}/{totalQ} · {v.score}m</span>
              </div>
            );
          })}
        </div>

        {!reflectionSubmitted ? (
          <div style={{ width: '100%', maxWidth: '600px', margin: '2rem auto', textAlign: 'left', padding: '1rem', background: 'var(--bg-inset)', borderRadius: '8px' }}>
             <h3 style={{ marginTop: 0, fontSize: '1rem' }}>Session Reflection</h3>
             <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)' }}>What tripped you up today? Write a quick reflection to close the session.</p>
             <textarea className="app-input" style={{ width: '100%', minHeight: '60px' }} value={reflection} onChange={e => setReflection(e.target.value)} placeholder="E.g. Time management was poor in the maths section..." />
             <button className="btn-primary" style={{ marginTop: '0.8rem' }} onClick={() => { api.endSession(sessionId, reflection); setReflectionSubmitted(true); }}>Save reflection</button>
          </div>
        ) : (
          <div style={{ margin: '2rem auto', color: 'var(--success)', textAlign: 'center' }}>✅ Reflection saved. Session closed.</div>
        )}
      </div>
    );
  }

  // ── running ──────────────────────────────────────────────────────────────────
  const q = exam.questions[idx];
  const hasOptions = q.options && Object.keys(q.options).length > 0;
  const answeredCount = Object.keys(answers).length;
  const setAnswer = (val) => updateState({ answers: { ...answers, [q.q_id]: val } });
  const toggleReview = () => {
    const n = new Set(review);
    n.has(q.q_id) ? n.delete(q.q_id) : n.add(q.q_id);
    updateState({ review: Array.from(n) });
  };

  return (
    <div>
      <header className="page-header">
        <div><h1>Mock Test</h1><p className="subtitle">{answeredCount}/{exam.questions.length} answered</p></div>
        <div className={`mock-timer ${secondsLeft < 300 ? 'danger' : ''}`}>⏱️ {fmt(secondsLeft)}</div>
      </header>

      <div className="mock-shell">
        <div className="card">
          <div className="pyq-meta">
            <span className="tag">Q{idx + 1}</span>
            <span className="tag accent">{q.type}</span>
            {q.marks_if_correct && <span className="tag gold">{q.marks_if_correct}m</span>}
            {q.negative_marks ? <span className="tag" style={{ color: 'var(--danger)' }}>{q.negative_marks}</span> : null}
            {q.subject && <span className="tag">{q.subject}</span>}
          </div>
          <div className="q-text"><MathText>{q.question}</MathText></div>

          {hasOptions ? (
            <div className="options">
              {Object.entries(q.options).map(([k, v]) => (
                <button key={k} className={`option ${answers[q.q_id] === k ? 'selected' : ''}`} onClick={() => setAnswer(k)}>
                  <span className="opt-key">{k}</span><span><MathText>{v}</MathText></span>
                </button>
              ))}
            </div>
          ) : (
            <div className="field">
              <label>Your answer (numerical)</label>
              <input value={answers[q.q_id] || ''} onChange={(e) => setAnswer(e.target.value)} placeholder="Type a number" />
            </div>
          )}

          <div className="mock-nav">
            <button className="btn-secondary" disabled={idx === 0} onClick={() => updateState({ idx: idx - 1 })}>← Prev</button>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button className="btn-secondary" onClick={toggleReview}>{review.has(q.q_id) ? '✓ Marked' : '⚑ Mark for review'}</button>
              {answers[q.q_id] && <button className="btn-secondary" onClick={() => { const n = { ...answers }; delete n[q.q_id]; updateState({ answers: n }); }}>Clear</button>}
            </div>
            {idx < exam.questions.length - 1
              ? <button className="btn-primary" onClick={() => updateState({ idx: idx + 1 })}>Next →</button>
              : <button className="btn-primary" onClick={submit} disabled={loading}>Submit test</button>}
          </div>
        </div>

        <div className="card">
          <h2 style={{ fontSize: '1rem' }}>Questions</h2>
          <div className="mock-palette">
            {exam.questions.map((qq, i) => {
              let cls = 'palette-cell';
              if (review.has(qq.q_id)) cls += ' review';
              else if (answers[qq.q_id]) cls += ' answered';
              if (i === idx) cls += ' current';
              return <button key={qq.q_id} className={cls} onClick={() => updateState({ idx: i })}>{i + 1}</button>;
            })}
          </div>
          <button className="btn-primary" style={{ width: '100%', marginTop: '1rem' }} onClick={submit} disabled={loading}>
            {loading ? 'Grading…' : 'Submit test'}
          </button>
        </div>
      </div>
    </div>
  );
}
