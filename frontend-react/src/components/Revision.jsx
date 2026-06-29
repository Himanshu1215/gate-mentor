import React, { useEffect, useState } from 'react';
import api from '../api';

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

export default function Revision({ navigate }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.revisionDue().then(setData).catch((e) => setError(e.message));
  }, []);

  // Build a simple 7-day strip around today; mark days that have upcoming reviews.
  const today = new Date();
  const week = Array.from({ length: 7 }, (_, i) => {
    const d = new Date(today);
    d.setDate(today.getDate() + i);
    return d;
  });
  const dueInDays = new Set((data?.upcoming || []).map((u) => u.due_in_days));

  return (
    <div>
      <header className="page-header">
        <div>
          <h1>Revision</h1>
          <p className="subtitle">Spaced repetition driven by your mastery decay — review before you forget.</p>
        </div>
        {data?.due_count > 0 && (
          <button className="btn-primary" onClick={() => navigate('quiz', { mode: 'revision' })}>🔁 Revise now ({data.due_count})</button>
        )}
      </header>

      <div className="week-strip">
        {week.map((d, i) => (
          <div className={`day-cell ${i === 0 ? 'today' : ''}`} key={i}>
            <div className="dc-day">{WEEKDAYS[d.getDay()]}</div>
            <div className="dc-num">{d.getDate()}</div>
            {(i === 0 && data?.due_count > 0) || dueInDays.has(i) ? <div className="dc-dot" /> : null}
          </div>
        ))}
      </div>

      {error && <div className="empty">Couldn't load revision: {error}</div>}
      {!error && !data && <div className="loading"><span className="spinner" /> Loading schedule…</div>}

      {data && (
        <>
          <h2>Due today {data.due.length > 0 && <span className="tag gold">{data.due.length}</span>}</h2>
          {data.due.length === 0 && (
            <div className="empty">🎉 Nothing overdue. Keep practising in the Quiz Center to build your revision queue.</div>
          )}
          <div className="rev-list">
            {data.due.map((d) => (
              <div className="rev-card card" key={d.concept_id}>
                <div>
                  <div style={{ fontWeight: 650 }}>{d.subtopic || d.topic}</div>
                  <div className="rc-meta">{d.subject} · Mastery Lvl {d.state_level} · <span className="overdue">{d.days_since}d since review</span></div>
                </div>
                <button className="btn-secondary" onClick={() => navigate('quiz', { mode: 'topic', conceptId: d.concept_id, topic: d.subtopic })}>Revise →</button>
              </div>
            ))}
          </div>

          {data.upcoming?.length > 0 && (
            <>
              <h2 style={{ marginTop: '1.6rem' }}>Coming up</h2>
              <div className="rev-list">
                {data.upcoming.map((u) => (
                  <div className="rev-card card" key={u.concept_id}>
                    <div>
                      <div style={{ fontWeight: 650 }}>{u.subtopic || u.topic}</div>
                      <div className="rc-meta">{u.subject} · due in {u.due_in_days} day{u.due_in_days === 1 ? '' : 's'}</div>
                    </div>
                    <span className="tag accent">Lvl {u.state_level}</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
