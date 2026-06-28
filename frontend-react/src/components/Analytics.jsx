import React from 'react';

const Analytics = () => {
  return (
    <div>
      <header>
        <div>
          <h1>Analytics</h1>
          <p className="subtitle">Track your learning velocity and accuracy.</p>
        </div>
      </header>

      <div className="analytics-grid">
        <div className="glass" style={{ padding: '2rem', borderRadius: '16px', height: '300px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <h3>Overall Accuracy (Last 30 Days)</h3>
          {/* Mock Graph */}
          <div style={{ display: 'flex', alignItems: 'flex-end', height: '150px', gap: '0.5rem' }}>
            {[30, 45, 40, 60, 55, 70, 75, 82].map((val, i) => (
              <div key={i} style={{ flex: 1, background: 'var(--accent-secondary)', height: `${val}%`, borderRadius: '4px 4px 0 0' }}></div>
            ))}
          </div>
        </div>

        <div className="glass" style={{ padding: '2rem', borderRadius: '16px', height: '300px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <h3>Mastery Distribution</h3>
          {/* Mock Graph */}
          <div style={{ display: 'flex', alignItems: 'flex-end', height: '150px', gap: '0.5rem' }}>
            {[80, 60, 40, 20, 10, 5, 2, 1].map((val, i) => (
              <div key={i} style={{ flex: 1, background: 'var(--accent-primary)', height: `${val}%`, borderRadius: '4px 4px 0 0' }}></div>
            ))}
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            <span>Lvl 1</span><span>Lvl 4</span><span>Lvl 8</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Analytics;
