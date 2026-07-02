import React, { useState, useEffect } from 'react';
import api from '../api';
import MathText from './MathText';

export default function MockReview({ params, navigate }) {
  const [review, setReview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(null);

  useEffect(() => {
    if (!params?.examId) return;
    setLoading(true);
    api.getMockReview(params.examId)
      .then(setReview)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [params?.examId]);

  const handleRetest = async (qId) => {
    try {
      await api.scheduleRevision(null, 1, qId);
      alert('Added to revision queue!');
    } catch (e) {
      alert('Failed to schedule revision.');
    }
  };

  if (loading) return <div className="loading"><span className="spinner"/> Loading review…</div>;
  if (!review) return <div>No review found.</div>;

  return (
    <div>
      <header className="page-header">
        <div><h1>Mock Review</h1><p className="subtitle">Exam ID: {params.examId}</p></div>
        <button className="btn-secondary" onClick={() => navigate('dashboard')}>← Dashboard</button>
      </header>
      <div className="pyq-list">
        {review.map((m) => {
          const { attempt, question: p } = m;
          const open = expanded === attempt.item_id;
          return (
            <div className="pyq-card card" key={attempt.item_id}>
              <div className="pyq-meta">
                <span className="tag accent">{p.question_type || 'MCQ'}</span>
                {p.subject && <span className="tag">{p.subject}</span>}
                <span className={`tag ${attempt.is_correct ? 'success' : 'danger'}`}>
                  {attempt.is_correct ? 'Correct' : attempt.user_answer ? 'Incorrect' : 'Unattempted'}
                </span>
                <span className="tag gold">{attempt.marks_awarded > 0 ? '+' : ''}{attempt.marks_awarded}m</span>
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
                    <p style={{ margin: 0, marginBottom: '0.4rem' }}><b>Your Answer:</b> <span style={{ color: attempt.is_correct ? 'var(--success)' : 'var(--danger)' }}>{attempt.user_answer || '(Blank)'}</span></p>
                    <p style={{ margin: 0 }}><b>Correct Answer:</b> <span style={{ color: 'var(--success)' }}>{attempt.correct_answer || p.answer}</span></p>
                  </div>

                  {p.solution ? (
                    <div className="solution"><MathText>{p.solution}</MathText></div>
                  ) : (
                    <p className="subtitle">No worked solution on file for this question.</p>
                  )}
                  
                  <div className="action-toolbar" style={{ marginTop: '0.8rem', gap: '0.5rem' }}>
                    <button className="chip" onClick={() => navigate('tutor', { prefill: `Explain this GATE question:\n\n${p.question_text}` })}>🤖 Ask tutor</button>
                    {!attempt.is_correct && <button className="chip" onClick={() => handleRetest(p.id)}>🔁 Re-test later</button>}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
