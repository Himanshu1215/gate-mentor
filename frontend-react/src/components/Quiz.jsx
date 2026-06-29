import React, { useState, useEffect, useCallback } from 'react';
import api from '../api';
import { useApp } from '../context/AppContext';

const MODES = [
  { id: 'topic', ico: '🎯', title: 'Topic Quiz', desc: 'Focus on one concept you choose.' },
  { id: 'mixed', ico: '🎲', title: 'Mixed Quiz', desc: 'Random questions across all subjects.' },
  { id: 'weak', ico: '📉', title: 'Weak Topics', desc: 'Target your lowest-mastery concepts.' },
  { id: 'revision', ico: '🔁', title: 'Revision Quiz', desc: 'Concepts you haven’t reviewed lately.' },
];

const QUIZ_LENGTH = 10;

function compareAnswer(user, correct) {
  if (user == null || correct == null) return false;
  const u = String(user).trim().toUpperCase();
  const c = String(correct).trim().toUpperCase();
  if (u === c) return true;
  const uf = parseFloat(u), cf = parseFloat(c);
  if (!isNaN(uf) && !isNaN(cf)) return Math.abs(uf - cf) < 0.011;
  return false;
}

function Ring({ progress, size = 160, stroke = 12, children }) {
  const r = (size - stroke) / 2, c = 2 * Math.PI * r;
  const off = c * (1 - Math.max(0, Math.min(1, progress)));
  return (
    <div className="score-ring" style={{ width: size, height: size }}>
      <svg width={size} height={size}>
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth={stroke} />
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="url(#qg)" strokeWidth={stroke}
          strokeDasharray={c} strokeDashoffset={off} strokeLinecap="round" transform={`rotate(-90 ${size/2} ${size/2})`} />
        <defs><linearGradient id="qg" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stopColor="#2ed573"/><stop offset="100%" stopColor="#00f0ff"/></linearGradient></defs>
      </svg>
      <div className="sr-label">{children}</div>
    </div>
  );
}

export default function Quiz({ params, navigate }) {
  const { refreshGamification } = useApp();
  const [phase, setPhase] = useState('select'); // select | active | summary
  const [mode, setMode] = useState(null);
  const [conceptId, setConceptId] = useState(null);
  const [topicLabel, setTopicLabel] = useState('');
  const [sessionId] = useState(() => 'q-' + Math.random().toString(36).slice(2, 9));

  const [q, setQ] = useState(null);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState('');
  const [natInput, setNatInput] = useState('');
  const [confidence, setConfidence] = useState(3);
  const [answered, setAnswered] = useState(false);
  const [isCorrect, setIsCorrect] = useState(false);

  const [count, setCount] = useState(0);
  const [correct, setCorrect] = useState(0);
  const [askedIds, setAskedIds] = useState([]);
  const [error, setError] = useState(null);

  const fetchQuestion = useCallback(async (m, cid, exclude) => {
    setLoading(true); setError(null);
    try {
      const data = await api.quizNext({ mode: m, concept_id: cid, exclude: exclude.join(',') });
      setQ(data);
      setSelected(''); setNatInput(''); setConfidence(3); setAnswered(false); setIsCorrect(false);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  const start = useCallback((m, cid = null, label = '') => {
    setMode(m); setConceptId(cid); setTopicLabel(label);
    setPhase('active'); setCount(0); setCorrect(0); setAskedIds([]);
    fetchQuestion(m, cid, []);
  }, [fetchQuestion]);

  // Deep-link from Topics / Dashboard ("Quiz this concept")
  useEffect(() => {
    if (params?.mode === 'topic' && params?.conceptId) {
      start('topic', params.conceptId, params.topic || '');
    }
  }, [params, start]);

  const submit = async () => {
    if (answered) return;
    const userAns = q.options && Object.keys(q.options).length ? selected : natInput;
    if (!userAns) return;
    const ok = compareAnswer(userAns, q.answer);
    setIsCorrect(ok); setAnswered(true);
    setCount((c) => c + 1);
    if (ok) setCorrect((c) => c + 1);
    setAskedIds((ids) => [...ids, q.pyq_id]);
    try {
      await api.submitQuiz({
        session_id: sessionId,
        concept_id: q.track_concept_id || q.concept_id || 'GENERAL',
        is_correct: ok,
        confidence,
      });
      refreshGamification();
    } catch (e) { /* non-fatal */ }
  };

  const next = () => {
    if (count >= QUIZ_LENGTH) { setPhase('summary'); return; }
    fetchQuestion(mode, conceptId, askedIds);
  };

  // ── Render: selection ────────────────────────────────────────────────────
  if (phase === 'select') {
    return (
      <div>
        <header className="page-header">
          <div><h1>Quiz Center</h1><p className="subtitle">Practice with real GATE questions. Build mastery, earn XP.</p></div>
        </header>
        <div className="quiz-modes">
          {MODES.map((m) => (
            <button className="mode-card card" key={m.id}
              onClick={() => m.id === 'topic' ? navigate('topics') : start(m.id)}>
              <span className="mc-ico">{m.ico}</span>
              <span className="mc-title">{m.title}</span>
              <span className="mc-desc">{m.id === 'topic' ? 'Pick a concept from Topics →' : m.desc}</span>
            </button>
          ))}
        </div>
      </div>
    );
  }

  // ── Render: summary ────────────────────────────────────────────────────────
  if (phase === 'summary') {
    const acc = count ? correct / count : 0;
    return (
      <div className="quiz-summary">
        <h1>Quiz complete! 🎉</h1>
        <Ring progress={acc}><div className="sr-label"><b>{Math.round(acc * 100)}%</b><small>accuracy</small></div></Ring>
        <p style={{ fontSize: '1.1rem' }}>You got <b style={{ color: 'var(--success)' }}>{correct}</b> of <b>{count}</b> correct.</p>
        <div style={{ display: 'flex', gap: '0.6rem', justifyContent: 'center', marginTop: '1.4rem' }}>
          <button className="btn-secondary" onClick={() => setPhase('select')}>Back to modes</button>
          <button className="btn-primary" onClick={() => start(mode, conceptId, topicLabel)}>Practice again</button>
        </div>
      </div>
    );
  }

  // ── Render: active question ─────────────────────────────────────────────────
  const hasOptions = q && q.options && Object.keys(q.options).length > 0;
  return (
    <div className="quiz-arena">
      <div className="q-progress">
        <span>{topicLabel ? `${topicLabel} · ` : ''}Question {count + (answered ? 0 : 1)} / {QUIZ_LENGTH}</span>
        <span className="score">{correct} correct</span>
      </div>

      {loading && <div className="loading"><span className="spinner" /> Loading question…</div>}
      {error && <div className="empty">Couldn't load a question: {error}<br /><button className="btn-secondary" style={{ marginTop: '1rem' }} onClick={() => setPhase('select')}>Back</button></div>}

      {q && !loading && (
        <div className="card">
          <div className="pyq-meta">
            {q.exam && <span className="tag">{q.exam} {q.year}</span>}
            <span className="tag accent">{q.question_type || 'MCQ'}</span>
            {q.marks && <span className="tag gold">{q.marks} mark{q.marks > 1 ? 's' : ''}</span>}
            {q.subject && <span className="tag">{q.subject}</span>}
          </div>

          <div className="q-text">{q.question_text}</div>

          {hasOptions ? (
            <div className="options">
              {Object.entries(q.options).map(([k, v]) => {
                let cls = 'option';
                if (answered) {
                  if (compareAnswer(k, q.answer)) cls += ' correct';
                  else if (k === selected) cls += ' wrong';
                } else if (k === selected) cls += ' selected';
                return (
                  <button key={k} className={cls} disabled={answered} onClick={() => setSelected(k)}>
                    <span className="opt-key">{k}</span><span>{v}</span>
                  </button>
                );
              })}
            </div>
          ) : (
            <div className="field">
              <label>Your answer (numerical)</label>
              <input value={natInput} disabled={answered} onChange={(e) => setNatInput(e.target.value)}
                placeholder="Type a number" onKeyDown={(e) => e.key === 'Enter' && submit()} />
            </div>
          )}

          {!answered && (
            <div className="confidence">
              <div className="conf-label">How confident are you?</div>
              <div className="conf-btns">
                {[1, 2, 3, 4, 5].map((n) => (
                  <button key={n} className={`conf-btn ${confidence === n ? 'active' : ''}`} onClick={() => setConfidence(n)}>{n}</button>
                ))}
              </div>
            </div>
          )}

          {answered && (
            <div className={`quiz-feedback ${isCorrect ? 'correct' : 'wrong'}`}>
              <div className="fb-title">{isCorrect ? '✅ Correct!' : `❌ Incorrect — answer is ${q.answer}`}</div>
              {q.solution && <div className="fb-sol">{q.solution}</div>}
            </div>
          )}

          <div className="quiz-actions">
            <button className="btn-secondary" onClick={() => setPhase('summary')}>End quiz</button>
            {!answered
              ? <button className="btn-primary" onClick={submit} disabled={hasOptions ? !selected : !natInput}>Submit</button>
              : <button className="btn-primary" onClick={next}>{count >= QUIZ_LENGTH ? 'See results' : 'Next question →'}</button>}
          </div>
        </div>
      )}
    </div>
  );
}
