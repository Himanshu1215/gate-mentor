import React, { useState, useEffect, useCallback } from 'react';
import api from '../api';
import { useApp } from '../context/AppContext';
import MathText from './MathText';

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
  const { refreshGamification, quizState, setQuizState } = useApp();

  const updateState = (updates) => {
    setQuizState(prev => ({ ...prev, ...updates }));
  };

  const phase = quizState?.phase || 'select'; // select | active | summary
  const mode = quizState?.mode || null;
  const conceptId = quizState?.conceptId || null;
  const topicLabel = quizState?.topicLabel || '';
  const sessionId = quizState?.sessionId || '';

  const q = quizState?.q || null;
  const loading = quizState?.loading || false;
  const selected = quizState?.selected || '';
  const natInput = quizState?.natInput || '';
  const confidence = quizState?.confidence || 3;
  const answered = quizState?.answered || false;
  const isCorrect = quizState?.isCorrect || false;

  const count = quizState?.count || 0;
  const correct = quizState?.correct || 0;
  const askedIds = quizState?.askedIds || [];
  const missedQuestions = quizState?.missedQuestions || [];
  const overconfidentCount = quizState?.overconfidentCount || 0;
  const reflection = quizState?.reflection || '';
  const reflectionSubmitted = quizState?.reflectionSubmitted || false;
  const qStartTime = quizState?.qStartTime || Date.now();
  const error = quizState?.error || null;

  const fetchQuestion = useCallback(async (m, cid, exclude) => {
    updateState({ loading: true, error: null });
    try {
      const data = await api.quizNext({ mode: m, concept_id: cid, exclude: exclude.join(',') });
      updateState({
        q: data, qStartTime: Date.now(),
        selected: '', natInput: '', confidence: 3, answered: false, isCorrect: false,
        loading: false
      });
    } catch (e) {
      updateState({ error: e.message, loading: false });
    }
  }, [setQuizState]);

  const start = useCallback(async (m, cid = null, label = '') => {
    updateState({
      mode: m, conceptId: cid, topicLabel: label,
      phase: 'active', count: 0, correct: 0, askedIds: [], missedQuestions: [],
      overconfidentCount: 0, reflection: '', reflectionSubmitted: false
    });
    try {
      const { session_id } = await api.startSession(`Quiz mode: ${m}`);
      updateState({ sessionId: session_id });
    } catch (e) {}
    fetchQuestion(m, cid, []);
  }, [fetchQuestion, setQuizState]);

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
    
    let newMissed = missedQuestions;
    let newOver = overconfidentCount;
    if (!ok) {
      newMissed = [...missedQuestions, { ...q, userAns }];
      if (confidence >= 4) newOver++;
    }
    
    updateState({
      missedQuestions: newMissed,
      overconfidentCount: newOver,
      isCorrect: ok,
      answered: true,
      count: count + 1,
      correct: ok ? correct + 1 : correct,
      askedIds: [...askedIds, q.pyq_id]
    });
    
    const tSec = (Date.now() - qStartTime) / 1000;
    
    try {
      await api.submitQuiz({
        session_id: sessionId,
        concept_id: q.track_concept_id || q.concept_id || 'GENERAL',
        is_correct: ok,
        confidence,
        question_id: q.pyq_id,
        user_answer: userAns,
        correct_answer: String(q.answer),
        time_taken_sec: tSec,
      });
      refreshGamification();
    } catch (e) { /* non-fatal */ }
  };

  const next = () => {
    if (count >= QUIZ_LENGTH) { updateState({ phase: 'summary' }); return; }
    fetchQuestion(mode, conceptId, askedIds);
  };

  // ── Render: selection ────────────────────────────────────────────────────
  if (phase === 'select') {
    return (
      <div>
        <header className="page-header">
          <div><h1>Quiz Center</h1><p className="subtitle">Practice with real GATE questions. Build mastery, earn XP.</p></div>
        </header>
        {quizState?.phase === 'active' && (
          <div className="card" style={{ maxWidth: 560, marginBottom: '1rem', borderLeft: '4px solid var(--primary)' }}>
            <h2>Quiz in Progress</h2>
            <p style={{ color: 'var(--text-secondary)' }}>You have a quiz currently running.</p>
            <button className="btn-primary" style={{ marginTop: '1rem' }} onClick={() => updateState({ phase: 'active' })}>Resume quiz</button>
            <button className="btn-secondary" style={{ marginTop: '1rem', marginLeft: '1rem' }} onClick={() => setQuizState(null)}>Abandon quiz</button>
          </div>
        )}
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
        {overconfidentCount > 0 && <p style={{ color: 'var(--danger)', fontSize: '0.9rem', marginTop: '-0.5rem', marginBottom: '1rem' }}>⚠ Overconfident on {overconfidentCount} question(s).</p>}
        
        {!reflectionSubmitted ? (
          <div style={{ width: '100%', maxWidth: '600px', margin: '2rem auto', textAlign: 'left', padding: '1rem', background: 'var(--bg-inset)', borderRadius: '8px' }}>
             <h3 style={{ marginTop: 0, fontSize: '1rem' }}>Session Reflection</h3>
             <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)' }}>What tripped you up today? Write a quick reflection to close the session.</p>
             <textarea className="app-input" style={{ width: '100%', minHeight: '60px' }} value={reflection} onChange={e => updateState({ reflection: e.target.value })} placeholder="E.g. Kept messing up sign errors in linear algebra..." />
             <button className="btn-primary" style={{ marginTop: '0.8rem' }} onClick={() => { api.endSession(sessionId, reflection); updateState({ reflectionSubmitted: true }); }}>Save reflection</button>
          </div>
        ) : (
          <div style={{ margin: '2rem auto', color: 'var(--success)' }}>✅ Reflection saved. Session closed.</div>
        )}

        {missedQuestions.length > 0 && (
          <div style={{ width: '100%', maxWidth: '600px', margin: '2rem auto', textAlign: 'left' }}>
            <h2 style={{ fontSize: '1.2rem', marginBottom: '1rem' }}>Questions you missed</h2>
            <div className="pyq-list">
              {missedQuestions.map((m, i) => (
                 <div className="pyq-card card" key={m.pyq_id}>
                    <div className="q-text"><MathText>{m.question_text}</MathText></div>
                    <div style={{ marginTop: '1rem', padding: '0.8rem', background: 'var(--bg-inset)', borderRadius: '8px' }}>
                      <p style={{ margin: 0, marginBottom: '0.4rem' }}><b>Your Answer:</b> <span style={{ color: 'var(--danger)' }}>{m.userAns || '(Blank)'}</span></p>
                      <p style={{ margin: 0 }}><b>Correct Answer:</b> <span style={{ color: 'var(--success)' }}>{m.answer}</span></p>
                    </div>
                    {m.solution && <div className="solution" style={{ marginTop: '0.8rem' }}><MathText>{m.solution}</MathText></div>}
                 </div>
              ))}
            </div>
          </div>
        )}

        <div style={{ display: 'flex', gap: '0.6rem', justifyContent: 'center', marginTop: '1.4rem' }}>
          <button className="btn-secondary" onClick={() => setQuizState(null)}>Back to modes</button>
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
      {error && <div className="empty">Couldn't load a question: {error}<br /><button className="btn-secondary" style={{ marginTop: '1rem' }} onClick={() => setQuizState(null)}>Back</button></div>}

      {q && !loading && (
        <div className="card">
          <div className="pyq-meta">
            {q.exam && <span className="tag">{q.exam} {q.year}</span>}
            <span className="tag accent">{q.question_type || 'MCQ'}</span>
            {q.marks && <span className="tag gold">{q.marks} mark{q.marks > 1 ? 's' : ''}</span>}
            {q.subject && <span className="tag">{q.subject}</span>}
            {q.answer && (q.answer_verified
              ? <span className="tag" style={{ color: 'var(--success)' }}>✓ verified</span>
              : <span className="tag" style={{ color: 'var(--warning)' }} title="Answer not yet human/LLM-verified">⚠ unverified</span>)}
          </div>

          <div className="q-text"><MathText>{q.question_text}</MathText></div>

          {hasOptions ? (
            <div className="options">
              {Object.entries(q.options).map(([k, v]) => {
                let cls = 'option';
                if (answered) {
                  if (compareAnswer(k, q.answer)) cls += ' correct';
                  else if (k === selected) cls += ' wrong';
                } else if (k === selected) cls += ' selected';
                return (
                  <button key={k} className={cls} disabled={answered} onClick={() => updateState({ selected: k })}>
                    <span className="opt-key">{k}</span><span><MathText>{v}</MathText></span>
                  </button>
                );
              })}
            </div>
          ) : (
            <div className="field">
              <label>Your answer (numerical)</label>
              <input value={natInput} disabled={answered} onChange={(e) => updateState({ natInput: e.target.value })}
                placeholder="Type a number" onKeyDown={(e) => e.key === 'Enter' && submit()} />
            </div>
          )}

          {!answered && (
            <div className="confidence">
              <div className="conf-label">How confident are you?</div>
              <div className="conf-btns">
                {[1, 2, 3, 4, 5].map((n) => (
                  <button key={n} className={`conf-btn ${confidence === n ? 'active' : ''}`} onClick={() => updateState({ confidence: n })}>{n}</button>
                ))}
              </div>
            </div>
          )}

          {answered && (
            <div className={`quiz-feedback ${isCorrect ? 'correct' : 'wrong'}`}>
              <div className="fb-title">{isCorrect ? '✅ Correct!' : `❌ Incorrect — answer is ${q.answer}`}</div>
              {confidence >= 4 && !isCorrect && (
                <div style={{ background: 'var(--danger-alpha)', color: 'var(--danger)', padding: '0.5rem', borderRadius: '4px', marginTop: '0.5rem', fontSize: '0.9rem' }}>
                  ⚠ Overconfident — under GATE negative marking this costs you marks. Slow down.
                </div>
              )}
              {confidence <= 2 && isCorrect && (
                <div style={{ background: 'var(--success-alpha)', color: 'var(--success)', padding: '0.5rem', borderRadius: '4px', marginTop: '0.5rem', fontSize: '0.9rem' }}>
                  ✅ You knew this — trust your instincts.
                </div>
              )}
              {q.solution && <div className="fb-sol"><MathText>{q.solution}</MathText></div>}
            </div>
          )}

          <div className="quiz-actions">
            <button className="btn-secondary" onClick={() => updateState({ phase: 'summary' })}>End quiz</button>
            {!answered
              ? <button className="btn-primary" onClick={submit} disabled={hasOptions ? !selected : !natInput}>Submit</button>
              : <button className="btn-primary" onClick={next}>{count >= QUIZ_LENGTH ? 'See results' : 'Next question →'}</button>}
          </div>
        </div>
      )}
    </div>
  );
}
