import React, { useEffect, useState } from 'react';
import {
  ResponsiveContainer, LineChart, Line, BarChart, Bar,
  XAxis, YAxis, Tooltip, CartesianGrid, Cell,
} from 'recharts';
import api from '../api';

const AXIS = { stroke: '#5b6783', fontSize: 12 };
const GRID = 'rgba(255,255,255,0.06)';
const tooltipStyle = { background: '#161a2b', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 10, color: '#fff' };

function Card({ title, children, empty }) {
  return (
    <div className="card chart-card">
      <div className="chart-title">{title}</div>
      {empty
        ? <div className="empty">No data yet — answer some quizzes to populate this.</div>
        : <ResponsiveContainer width="100%" height={230}>{children}</ResponsiveContainer>}
    </div>
  );
}

export default function Analytics() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => { api.analytics().then(setData).catch((e) => setError(e.message)); }, []);

  if (error) return <div className="empty">Couldn't load analytics: {error}</div>;
  if (!data) return <div className="loading"><span className="spinner" /> Crunching numbers…</div>;

  const trend = data.accuracy_trend || [];
  const dist = data.mastery_distribution || [];
  const subj = data.subject_readiness || [];
  const calib = (data.confidence_calibration || []).filter((c) => c.attempts > 0);
  const noAttempts = trend.length === 0;

  return (
    <div>
      <header className="page-header">
        <div>
          <h1>Analytics</h1>
          <p className="subtitle">Your learning velocity, mastery spread, and exam-risk calibration.</p>
        </div>
      </header>

      <div className="chart-grid">
        <Card title="Accuracy trend" empty={noAttempts}>
          <LineChart data={trend}>
            <CartesianGrid stroke={GRID} />
            <XAxis dataKey="day" {...AXIS} />
            <YAxis domain={[0, 100]} {...AXIS} unit="%" />
            <Tooltip contentStyle={tooltipStyle} />
            <Line type="monotone" dataKey="accuracy" stroke="#00f0ff" strokeWidth={2.5} dot={{ r: 3 }} />
          </LineChart>
        </Card>

        <Card title="Mastery distribution (levels 1–8)">
          <BarChart data={dist}>
            <CartesianGrid stroke={GRID} />
            <XAxis dataKey="level" {...AXIS} />
            <YAxis allowDecimals={false} {...AXIS} />
            <Tooltip contentStyle={tooltipStyle} />
            <Bar dataKey="count" radius={[6, 6, 0, 0]}>
              {dist.map((e, i) => (
                <Cell key={i} fill={e.level >= 8 ? '#ffd23f' : `rgba(124,58,237,${0.4 + e.level * 0.07})`} />
              ))}
            </Bar>
          </BarChart>
        </Card>

        <Card title="Subject readiness">
          <BarChart data={subj} layout="vertical" margin={{ left: 40 }}>
            <CartesianGrid stroke={GRID} />
            <XAxis type="number" domain={[0, 100]} {...AXIS} unit="%" />
            <YAxis type="category" dataKey="subject" width={150} tick={{ fill: '#93a1bd', fontSize: 10 }} />
            <Tooltip contentStyle={tooltipStyle} />
            <Bar dataKey="readiness" radius={[0, 6, 6, 0]} fill="#00f0ff" />
          </BarChart>
        </Card>

        <Card title="Confidence calibration" empty={calib.length === 0}>
          <BarChart data={calib}>
            <CartesianGrid stroke={GRID} />
            <XAxis dataKey="confidence" {...AXIS} label={{ value: 'confidence', position: 'insideBottom', offset: -2, fill: '#5b6783', fontSize: 11 }} />
            <YAxis domain={[0, 100]} {...AXIS} unit="%" />
            <Tooltip contentStyle={tooltipStyle} />
            <Bar dataKey="accuracy" radius={[6, 6, 0, 0]}>
              {calib.map((e, i) => (
                <Cell key={i} fill={e.confidence >= 4 && e.accuracy < 60 ? '#ff4d5e' : '#2ed573'} />
              ))}
            </Bar>
          </BarChart>
        </Card>
      </div>
      <p className="subtitle" style={{ marginTop: '1rem' }}>
        Calibration tip: bars turn <span style={{ color: 'var(--danger)' }}>red</span> when you're highly confident (4–5) but often wrong — a negative-marking risk.
      </p>
    </div>
  );
}
