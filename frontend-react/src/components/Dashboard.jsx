import React, { useEffect, useState } from 'react';
import api from '../api';
import { useApp } from '../context/AppContext';

function Ring({ progress, size = 120, stroke = 10, children }) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const off = c * (1 - Math.max(0, Math.min(1, progress)));
  return (
    <div className="level-ring" style={{ width: size, height: size }}>
      <svg width={size} height={size}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth={stroke} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="url(#ringGrad)" strokeWidth={stroke}
          strokeDasharray={c} strokeDashoffset={off} strokeLinecap="round"
          transform={`rotate(-90 ${size / 2} ${size / 2})`} style={{ transition: 'stroke-dashoffset 0.6s' }} />
        <defs>
          <linearGradient id="ringGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#7c3aed" />
            <stop offset="100%" stopColor="#00f0ff" />
          </linearGradient>
        </defs>
      </svg>
      <div className="ring-label">{children}</div>
    </div>
  );
}

export default function Dashboard({ navigate }) {
  const { gamification, profile } = useApp();
  const [stats, setStats] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [schedule, setSchedule] = useState(null);
  const [due, setDue] = useState([]);
  const [pastMocks, setPastMocks] = useState([]);

  useEffect(() => {
    api.dashboardStats().then(setStats).catch(() => {});
    api.coachAlerts().then((d) => setAlerts(d.alerts || [])).catch(() => {});
    api.scheduleToday().then(setSchedule).catch(() => {});
    api.revisionDue().then((d) => setDue(d.due || [])).catch(() => {});
    api.getMockAttempts().then(setPastMocks).catch(() => {});
  }, []);

  const g = gamification || {};
  const name = profile?.display_name || 'Aspirant';

  return (
    <div>
      <header className="page-header">
        <div>
          <h1>Welcome back, {name} 👋</h1>
          <p className="subtitle">Here's your mission control for GATE DA.</p>
        </div>
        <button className="btn-primary" onClick={() => navigate('mock')}>⏱️ Start Mock Test</button>
      </header>

      <div className="dash-grid">
        <div className="card hero-card">
          <Ring progress={g.level_progress ?? 0}>
            <b>{g.level ?? 1}</b><small>LEVEL</small>
          </Ring>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: '1.1rem', fontWeight: 650, marginBottom: '0.3rem' }}>{g.xp ?? 0} XP</div>
            <p className="subtitle" style={{ marginBottom: '0.8rem' }}>
              {g.xp_into_level ?? 0} / {g.xp_per_level ?? 500} XP to level {(g.level ?? 1) + 1}
            </p>
            <div style={{ display: 'flex', gap: '1.2rem', flexWrap: 'wrap' }}>
              <div><span className="flame">🔥</span> <b>{g.streak ?? 0}</b> day streak</div>
              <div>🏅 <b>{g.badges_earned ?? 0}</b> badges</div>
              <div>🎯 <b>{g.daily_goal_done ?? 0}/{g.daily_goal ?? 10}</b> today</div>
            </div>
          </div>
        </div>

        <div className="card">
          <h2>Your numbers</h2>
          <div className="stat-grid">
            <div className="stat-card" onClick={() => navigate('quiz', { mode: 'weak' })} style={{ cursor: 'pointer' }}>
              <span className="value good">{stats ? `${stats.readiness_percentage}%` : '—'}</span>
              <span className="label">Readiness (click to practice)</span>
            </div>
            <div className="stat-card">
              <span className="value">{stats ? `${stats.mastered_concepts}/${stats.total_concepts}` : '—'}</span>
              <span className="label">Concepts mastered</span>
            </div>
            <div className="stat-card">
              <span className="value warn">{stats ? `#${stats.projected_air}` : '—'}</span>
              <span className="label">Projected AIR</span>
              {stats?.biggest_lever && (
                <div style={{ marginTop: '0.8rem', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                  Biggest lever: <a style={{ color: 'var(--primary)', cursor: 'pointer', textDecoration: 'underline' }} onClick={() => navigate('topics', { conceptId: stats.biggest_lever.concept_id })}>{stats.biggest_lever.topic}</a>
                </div>
              )}
            </div>
            <div className="stat-card">
              <span className="value">{stats ? stats.total_quizzes : '—'}</span>
              <span className="label">Questions solved</span>
            </div>
          </div>
        </div>
      </div>

      <div className="dash-grid" style={{ marginTop: '1.2rem' }}>
        <div className="card">
          <h2>Coach alerts</h2>
          {alerts.length === 0 && <div className="empty">No alerts right now.</div>}
          {alerts.map((a, i) => (
            <div className={`alert ${a.type}`} key={i}>
              <div>
                <div className="a-title">{a.title}</div>
                <div className="a-msg">{a.message}</div>
              </div>
            </div>
          ))}
          {schedule && (
            <div style={{ marginTop: '1rem' }}>
              <h2>Today's Plan</h2>
              {(schedule.revision_tasks.length === 0 && schedule.learning_tasks.length === 0) && (
                <div className="empty">No tasks scheduled for today.</div>
              )}
              {schedule.revision_tasks.map((rt) => (
                 <div className="list-row" key={'rev-' + rt.concept_id}>
                    <div>
                       <div style={{ fontWeight: 600 }}>{rt.topic}</div>
                       <div className="lr-sub">Revision required</div>
                    </div>
                    <button className="btn-secondary" onClick={() => navigate('quiz', { mode: 'revision', conceptId: rt.concept_id, topic: rt.topic })}>Review →</button>
                 </div>
              ))}
              {schedule.learning_tasks.map((lt) => (
                 <div className="list-row" key={'lrn-' + lt.concept_id}>
                    <div>
                       <div style={{ fontWeight: 600 }}>{lt.topic}</div>
                       <div className="lr-sub">Learn this next</div>
                    </div>
                    <button className="btn-secondary" onClick={() => navigate('topics', { conceptId: lt.concept_id })}>Learn →</button>
                 </div>
              ))}
              {g.daily_goal_done < g.daily_goal && (
                 <div className="list-row" key="goal-tasks">
                    <div>
                       <div style={{ fontWeight: 600 }}>{g.daily_goal - g.daily_goal_done} questions to hit today's goal</div>
                       <div className="lr-sub">Target weak areas</div>
                    </div>
                    <button className="btn-secondary" onClick={() => navigate('quiz', { mode: 'weak' })}>Practice →</button>
                 </div>
              )}
            </div>
          )}
        </div>

        <div className="card">
          <h2>Due for revision {due.length > 0 && <span className="tag gold">{due.length}</span>}</h2>
          {due.length === 0 && <div className="empty">Nothing due — you're all caught up! 🎉</div>}
          {due.slice(0, 5).map((d) => (
            <div className="list-row" key={d.concept_id}>
              <div>
                <div style={{ fontWeight: 600 }}>{d.subtopic || d.topic}</div>
                <div className="lr-sub">{d.subject} · {d.days_since}d since review</div>
              </div>
              <span className="tag accent">Lvl {d.state_level}</span>
            </div>
          ))}
          {due.length > 0 && (
            <button className="btn-secondary" style={{ marginTop: '0.8rem' }} onClick={() => navigate('revision')}>
              Go to revision →
            </button>
          )}
        </div>

        <div className="card">
          <h2>Past Mocks {pastMocks.length > 0 && <span className="tag gold">{pastMocks.length}</span>}</h2>
          {pastMocks.length === 0 && <div className="empty">No past mocks yet. Take one!</div>}
          {pastMocks.slice(0, 5).map((m) => (
            <div className="list-row" key={m.exam_id}>
              <div>
                <div style={{ fontWeight: 600 }}>Mock {new Date(m.taken_at).toLocaleDateString()}</div>
                <div className="lr-sub">Score: {m.score}/{m.max_score} · {m.accuracy}% accuracy</div>
              </div>
              <button className="btn-secondary" onClick={() => navigate('mock_review', { examId: m.exam_id })}>Review →</button>
            </div>
          ))}
        </div>
      </div>

      {g.badges && (
        <div className="card" style={{ marginTop: '1.2rem' }}>
          <h2>Achievements</h2>
          <div className="badge-grid">
            {g.badges.map((b) => (
              <div className={`badge ${b.earned ? 'earned' : ''}`} key={b.id} title={b.description}>
                <span className="b-ico">{b.icon}</span>
                <span className="b-title">{b.title}</span>
                <span className="b-desc">{b.description}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
