import React, { useState, useEffect, useCallback } from 'react';
import api from '../api';
import MathText from './MathText';

const PAGE = 10;

export default function Mistakes({ params, navigate }) {
  const [source, setSource] = useState('');
  const [subject, setSubject] = useState('');
  
  const [mistakes, setMistakes] = useState([]);
  const [page, setPage] = useState(0);
  const [expanded, setExpanded] = useState(null);
  const [loading, setLoading] = useState(false);

  const fetchMistakes = useCallback(async (resetPage = true) => {
    setLoading(true);
    const offset = (resetPage ? 0 : page) * PAGE;
    if (resetPage) setPage(0);
    try {
      const data = await api.getMistakes({
        source, subject,
        limit: PAGE, offset,
      });
      setMistakes(data);
    } catch (e) { setMistakes([]); }
    finally { setLoading(false); }
  }, [source, subject, page]);

  useEffect(() => { fetchMistakes(true); }, [source, subject]);
  useEffect(() => { fetchMistakes(false); }, [page]);

  const handleRetest = async (qId) => {
    try {
      await api.scheduleRevision(null, 1, qId);
      alert('Added to revision queue!');
    } catch (e) {
      alert('Failed to schedule revision.');
    }
  };

  return (
    <div>
      <header className="page-header">
        <div>
          <h1>Mistakes & Review</h1>
          <p className="subtitle">Review the questions you answered incorrectly.</p>
        </div>
      </header>

      <div className="pyq-filters">
        <select className="app-select" value={source} onChange={(e) => setSource(e.target.value)}>
          <option value="">All sources</option>
          <option value="quiz">Quizzes</option>
          <option value="mock">Mock Tests</option>
        </select>
        <select className="app-select" value={subject} onChange={(e) => setSubject(e.target.value)}>
          <option value="">All subjects</option>
          <option value="Probability and Statistics">Probability and Statistics</option>
          <option value="Linear Algebra">Linear Algebra</option>
          <option value="Calculus and Optimization">Calculus and Optimization</option>
          <option value="Programming, DS & Algorithms">Programming, DS & Algorithms</option>
          <option value="Database Management and Warehousing">Database Management and Warehousing</option>
          <option value="Machine Learning">Machine Learning</option>
          <option value="Artificial Intelligence">Artificial Intelligence</option>
        </select>
      </div>

      {loading && <div className="loading"><span className="spinner" /> Loading…</div>}
      {!loading && mistakes.length === 0 && (
        <div className="empty">
          <p>No mistakes found for these filters! Great job!</p>
          <button className="btn-primary" onClick={() => navigate('quiz')} style={{ marginTop: '1rem' }}>Take a Quiz</button>
        </div>
      )}

      <div className="pyq-list">
        {mistakes.map((m) => {
          const { attempt, question: p } = m;
          const open = expanded === attempt.item_id;
          return (
            <div className="pyq-card card" key={attempt.item_id}>
              <div className="pyq-meta">
                <span className="tag" style={{ textTransform: 'capitalize' }}>{attempt.source}</span>
                <span className="tag accent">{p.question_type || 'MCQ'}</span>
                {p.subject && <span className="tag">{p.subject}</span>}
                <span className="tag" style={{ color: 'var(--text-dim)' }}>{new Date(attempt.timestamp).toLocaleDateString()}</span>
              </div>
              <div className="pyq-q">
                <div className="q-body" onClick={() => setExpanded(open ? null : attempt.item_id)} style={{ cursor: 'pointer' }}>
                  <MathText>{p.question_text}</MathText>
                </div>
              </div>

              {open && (
                <div className="pyq-detail">
                  {p.options && Object.keys(p.options).length > 0 && (
                    <div className="pyq-options">
                      {Object.entries(p.options).map(([k, v]) => {
                        let className = "pyq-opt";
                        if (attempt.correct_answer && String(attempt.correct_answer).toUpperCase() === k) {
                            className += " ans";
                        } else if (attempt.user_answer && String(attempt.user_answer).toUpperCase() === k) {
                            className += " wrong";
                        }
                        return (
                          <div key={k} className={className} style={className.includes('wrong') ? {borderColor: 'var(--danger)', background: 'rgba(239,68,68,0.1)'} : {}}>
                            <b>{k})</b> <MathText>{v}</MathText>
                          </div>
                        )
                      })}
                    </div>
                  )}
                  
                  <div style={{ margin: '1rem 0', padding: '0.8rem', background: 'var(--bg-inset)', borderRadius: '8px' }}>
                    <p style={{ margin: 0, marginBottom: '0.4rem' }}><b>Your Answer:</b> <span style={{ color: 'var(--danger)' }}>{attempt.user_answer || '(Blank)'}</span></p>
                    <p style={{ margin: 0 }}><b>Correct Answer:</b> <span style={{ color: 'var(--success)' }}>{attempt.correct_answer || p.answer}</span></p>
                  </div>

                  {p.solution ? (
                    <div className="solution"><MathText>{p.solution}</MathText></div>
                  ) : (
                    <p className="subtitle">No worked solution on file for this question.</p>
                  )}
                  
                  <div className="action-toolbar" style={{ marginTop: '0.8rem', gap: '0.5rem' }}>
                    <button className="chip" onClick={() => navigate('tutor', { prefill: `Explain this GATE question that I got wrong:\n\n${p.question_text}` })}>🤖 Ask tutor</button>
                    <button className="chip" onClick={() => handleRetest(p.id)}>🔁 Re-test later</button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {!loading && mistakes.length === PAGE && (
        <div className="pager">
          <button className="btn-secondary" disabled={page === 0} onClick={() => setPage((p) => Math.max(0, p - 1))}>← Prev</button>
          <span>Page {page + 1}</span>
          <button className="btn-secondary" onClick={() => setPage((p) => p + 1)}>Next →</button>
        </div>
      )}
    </div>
  );
}
