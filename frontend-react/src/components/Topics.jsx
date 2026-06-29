import React, { useEffect, useState } from 'react';
import api from '../api';

function DiffDots({ n }) {
  return (
    <div className="diff-dots" title={`Difficulty ${n}/8`}>
      {Array.from({ length: 8 }, (_, i) => <i key={i} className={i < n ? 'on' : ''} />)}
    </div>
  );
}

export default function Topics({ navigate }) {
  const [data, setData] = useState(null);
  const [active, setActive] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.getConcepts()
      .then((d) => {
        setData(d.subjects);
        if (d.subjects.length) setActive(d.subjects[0].subject);
      })
      .catch((e) => setError(e.message));
  }, []);

  if (error) return <div className="empty">Couldn't load topics: {error}</div>;
  if (!data) return <div className="loading"><span className="spinner" /> Loading syllabus…</div>;

  const current = data.find((s) => s.subject === active);

  return (
    <div>
      <header className="page-header">
        <div>
          <h1>Topic Explorer</h1>
          <p className="subtitle">The full GATE DA syllabus — {data.reduce((a, s) => a + s.total, 0)} concepts across {data.length} subjects.</p>
        </div>
      </header>

      <div className="subject-tabs">
        {data.map((s) => (
          <button key={s.subject} className={`subject-tab ${active === s.subject ? 'active' : ''}`} onClick={() => setActive(s.subject)}>
            {s.subject}<span className="st-count">{s.mastered}/{s.total}</span>
          </button>
        ))}
      </div>

      {current && (
        <>
          <div style={{ marginBottom: '1rem', color: 'var(--text-secondary)' }}>
            Subject readiness: <b style={{ color: 'var(--accent-primary)' }}>{current.readiness}%</b>
          </div>
          <div className="concept-grid">
            {current.concepts.map((c) => (
              <div className={`concept-card card ${c.locked ? 'locked' : ''}`} key={c.concept_id}>
                <div className="cc-head">
                  <div>
                    <div className="cc-topic">{c.topic}</div>
                    <div className="cc-title">{c.subtopic}</div>
                  </div>
                  <DiffDots n={c.difficulty || 5} />
                </div>

                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem', color: 'var(--text-secondary)', marginBottom: '0.3rem' }}>
                    <span>Mastery</span><span>Lvl {c.mastery_level}/8</span>
                  </div>
                  <div className="mastery-bar">
                    <div className={`mastery-fill ${c.mastery_level >= 8 ? 'mastered' : ''}`} style={{ width: `${(c.mastery_level / 8) * 100}%` }} />
                  </div>
                </div>

                {c.locked ? (
                  <div className="lock-badge">🔒 Unlock by mastering prerequisites</div>
                ) : (
                  <div className="concept-actions">
                    <button className="chip" onClick={() => navigate('quiz', { mode: 'topic', conceptId: c.concept_id, topic: c.subtopic })}>✏️ Quiz</button>
                    <button className="chip" onClick={() => navigate('pyqs', { concept_id: c.concept_id })}>📄 PYQs</button>
                    <button className="chip" onClick={() => navigate('tutor', { prefill: `Explain ${c.subtopic} for GATE DA with an example.` })}>🤖 Ask Tutor</button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
