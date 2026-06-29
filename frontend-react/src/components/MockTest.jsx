import React, { useState, useEffect, useRef, useCallback } from 'react';
import api from '../api';
import { useApp } from '../context/AppContext';

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

export default function MockTest() {
  const { refresh } = useApp();
  const [phase, setPhase] = useState('intro'); // intro | running | report
  const [exam, setExam] = useState(null);
  const [idx, setIdx] = useState(0);
  const [answers, setAnswers] = useState({});
  const [review, setReview] = useState(new Set());
  const [secondsLeft, setSecondsLeft] = useState(0);
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const timerRef = useRef(null);

  const start = async () => {
    setLoading(true);
    try {
      const e = await api.mockGenerate();
      setExam(e); setIdx(0); setAnswers({}); setReview(new Set());
      setSecondsLeft((e.duration_mins || 180) * 60);
      setPhase('running');
    } catch (err) { alert('Could not start mock: ' + err.message); }
    finally { setLoading(false); }
  };

  const submit = useCallback(async () => {
    if (timerRef.current) clearInterval(timerRef.current);
    setLoading(true);
    try {
      const r = await api.mockGrade(exam.exam_id, answers);
      setReport(r); setPhase('report');
      refresh();
    } catch (err) { alert('Grading failed: ' + err.message); }
    finally { setLoading(false); }
  }, [exam, answers, refresh]);

  useEffect(() => {
    if (phase !== 'running') return;
    timerRef.current = setInterval(() => {
      setSecondsLeft((s) => {
        if (s <= 1) { clearInterval(timerRef.current); submit(); return 0; }
        return s - 1;
      });
    }, 1000);
    return () => clearInterval(timerRef.current);
  }, [phase, submit]);

  // ── intro ──────────────────────────────────────────────────────────────────
  if (phase === 'intro') {
    return (
      <div>
        <header className="page-header"><div><h1>Mock Test</h1><p className="subtitle">Full GATE-pattern paper from the real PYQ bank.</p></div></header>
        <div className="card" style={{ maxWidth: 560 }}>
          <h2>GATE DA — Full Mock</h2>
          <ul style={{ color: 'var(--text-secondary)', lineHeight: 2, listStyle: 'none' }}>
            <li>📝 65 questions drawn from real previous-year papers</li>
            <li>⏱️ 3-hour timer (auto-submits at zero)</li>
            <li>➖ Negative marking on MCQs (GATE rules)</li>
            <li>🏁 Score report with per-subject breakdown</li>
          </ul>
          <button className="btn-primary" style={{ marginTop: '1rem' }} onClick={start} disabled={loading}>
            {loading ? 'Preparing…' : 'Begin mock test'}
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
          <button className="btn-primary" onClick={() => setPhase('intro')}>Take another</button>
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
      </div>
    );
  }

  // ── running ──────────────────────────────────────────────────────────────────
  const q = exam.questions[idx];
  const hasOptions = q.options && Object.keys(q.options).length > 0;
  const answeredCount = Object.keys(answers).length;
  const setAnswer = (val) => setAnswers((a) => ({ ...a, [q.q_id]: val }));
  const toggleReview = () => setReview((r) => { const n = new Set(r); n.has(q.q_id) ? n.delete(q.q_id) : n.add(q.q_id); return n; });

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
          <div className="q-text">{q.question}</div>

          {hasOptions ? (
            <div className="options">
              {Object.entries(q.options).map(([k, v]) => (
                <button key={k} className={`option ${answers[q.q_id] === k ? 'selected' : ''}`} onClick={() => setAnswer(k)}>
                  <span className="opt-key">{k}</span><span>{v}</span>
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
            <button className="btn-secondary" disabled={idx === 0} onClick={() => setIdx((i) => i - 1)}>← Prev</button>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button className="btn-secondary" onClick={toggleReview}>{review.has(q.q_id) ? '✓ Marked' : '⚑ Mark for review'}</button>
              {answers[q.q_id] && <button className="btn-secondary" onClick={() => setAnswers((a) => { const n = { ...a }; delete n[q.q_id]; return n; })}>Clear</button>}
            </div>
            {idx < exam.questions.length - 1
              ? <button className="btn-primary" onClick={() => setIdx((i) => i + 1)}>Next →</button>
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
              return <button key={qq.q_id} className={cls} onClick={() => setIdx(i)}>{i + 1}</button>;
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
