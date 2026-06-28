import React, { useState } from 'react';

const missionTasks = [
  {
    title: 'Revise Bayes Rule (15 min)',
    detail: 'Mastery decaying from Level 4 to Level 3.'
  },
  {
    title: 'Learn Logistic Regression',
    detail: 'Next concept in the syllabus DAG.'
  },
  {
    title: 'Solve 12 PYQs (Mixed)',
    detail: 'Focus on Machine Learning topics.'
  }
];

const Dashboard = () => {
  const [sessionActive, setSessionActive] = useState(false);

  return (
    <div>
      <header>
        <div>
          <h1>Dashboard</h1>
          <p className="subtitle">Welcome back. Here is your daily overview.</p>
        </div>
        <button
          className="btn-primary"
          type="button"
          onClick={() => setSessionActive(true)}
          style={{ background: sessionActive ? 'var(--success)' : '' }}
        >
          {sessionActive ? 'Session Active' : 'Start Study Session'}
        </button>
      </header>

      <div className="stats-grid">
        <div className="stat-card glass">
          <h3>Target AIR</h3>
          <div className="stat-value">540</div>
          <div className="stat-subtext" style={{ color: 'var(--success)' }}>On Track</div>
        </div>
        <div className="stat-card glass">
          <h3>Projected Score</h3>
          <div className="stat-value">62.5</div>
          <div className="stat-subtext">+2.1 since last week</div>
        </div>
        <div className="stat-card glass">
          <h3>Hours Studied</h3>
          <div className="stat-value">142h</div>
          <div className="stat-subtext">Top 15% of users</div>
        </div>
        <div className="stat-card glass">
          <h3>Study Streak</h3>
          <div className="stat-value">12 days</div>
          <div className="stat-subtext">Keep it up!</div>
        </div>
      </div>

      <div className="dashboard-layout">
        <div className="dashboard-main">
          <section className="glass dashboard-section">
            <h2>Today's Mission</h2>
            {!sessionActive ? (
              <div className="muted-text">Click "Start Study Session" to unlock today's optimal path.</div>
            ) : (
              <div className="mission-list">
                {missionTasks.map(task => (
                  <label key={task.title} className="mission-item">
                    <input type="checkbox" />
                    <span>
                      <strong>{task.title}</strong>
                      <small>{task.detail}</small>
                    </span>
                  </label>
                ))}
              </div>
            )}
          </section>

          <section className="alerts-section">
            <h2>AI Coach Alerts</h2>
            <div className="alerts-container glass">
              <div className="alert-item warning">
                <h4>High Risk: Negative Marking</h4>
                <p>Your confidence calibration is skewed. You are attempting hard questions you do not know, leading to -0.66 penalties.</p>
              </div>
              <div className="alert-item success">
                <h4>Excellent Work</h4>
                <p>You have mastered Vector Spaces. It has been pushed to your long-term revision cycle.</p>
              </div>
            </div>
          </section>
        </div>

        <aside className="dashboard-side">
          <section className="glass dashboard-section">
            <h2>Revision Due (5 Topics)</h2>
            <ul className="topic-list">
              <li className="danger-text">Conditional Probability</li>
              <li className="danger-text">Matrix Determinants</li>
              <li>Eigenvalues</li>
              <li>Gradient Descent</li>
              <li>SQL Joins</li>
            </ul>
          </section>

          <section className="glass dashboard-section">
            <h2>Weakest Topics</h2>
            <div className="weak-topic-list">
              <div>
                <div className="progress-label"><span>Decision Trees</span><span>32%</span></div>
                <div className="progress-track"><div className="progress-fill danger-fill" style={{ width: '32%' }} /></div>
              </div>
              <div>
                <div className="progress-label"><span>Relational Algebra</span><span>45%</span></div>
                <div className="progress-track"><div className="progress-fill warning-fill" style={{ width: '45%' }} /></div>
              </div>
            </div>
          </section>
        </aside>
      </div>
    </div>
  );
};

export default Dashboard;
