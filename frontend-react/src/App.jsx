import React, { useState } from 'react';
import Dashboard from './components/Dashboard';
import AITutor from './components/AITutor';
import Topics from './components/Topics';
import Quiz from './components/Quiz';
import PYQs from './components/PYQs';
import Revision from './components/Revision';
import Mistakes from './components/Mistakes';
import MockReview from './components/MockReview';
import Analytics from './components/Analytics';
import MockTest from './components/MockTest';
import Onboarding from './components/Onboarding';
import { useApp, daysUntil } from './context/AppContext';

const NAV = [
  { id: 'dashboard', label: 'Dashboard', ico: '🏠' },
  { id: 'tutor', label: 'AI Tutor', ico: '🤖' },
  { id: 'topics', label: 'Syllabus', ico: '📚' },
  { id: 'quiz', label: 'Quiz Center', ico: '✏️' },
  { id: 'mock', label: 'Mock Test', ico: '⏱️' },
  { id: 'pyqs', label: 'PYQ Explorer', ico: '📄' },
  { id: 'revision', label: 'Revision', ico: '🔁' },
  { id: 'mistakes', label: 'Mistakes', ico: '❌' },
  { id: 'analytics', label: 'Analytics', ico: '📊' },
];

function TopBar() {
  const { gamification, profile } = useApp();
  const g = gamification || {};
  const left = daysUntil(profile?.exam_date);
  return (
    <div className="topbar">
      <div className="topbar-stat" title="Daily streak">
        <span className="flame">🔥</span>{g.streak ?? 0}<small style={{ color: 'var(--text-dim)', fontWeight: 500 }}>day{g.streak === 1 ? '' : 's'}</small>
      </div>
      {left !== null && (
        <div className="topbar-stat countdown" title="Days until exam">
          ⏳ {left >= 0 ? left : 0} <small>days to GATE</small>
        </div>
      )}
      <div className="topbar-spacer" />
      <div className="topbar-stat" title="Daily goal">
        🎯 {g.daily_goal_done ?? 0}/{g.daily_goal ?? 10}
      </div>
      <div className="level-pill" title={`${g.xp ?? 0} XP`}>
        <span className="lvl-num">LVL {g.level ?? 1}</span>
        <div className="xp-bar"><div className="xp-fill" style={{ width: `${Math.round((g.level_progress ?? 0) * 100)}%` }} /></div>
      </div>
    </div>
  );
}

export default function App() {
  const { profile, loading } = useApp();
  const [activeView, setActiveView] = useState('dashboard');
  const [params, setParams] = useState({});

  const navigate = (view, payload = {}) => {
    setParams(payload);
    setActiveView(view);
  };

  const renderView = () => {
    switch (activeView) {
      case 'dashboard': return <Dashboard navigate={navigate} />;
      case 'tutor': return <AITutor params={params} />;
      case 'topics': return <Topics navigate={navigate} />;
      case 'quiz': return <Quiz params={params} navigate={navigate} />;
      case 'mock': return <MockTest navigate={navigate} />;
      case 'mock_review': return <MockReview navigate={navigate} params={params} />;
      case 'pyqs': return <PYQs params={params} navigate={navigate} />;
      case 'revision': return <Revision navigate={navigate} />;
      case 'mistakes': return <Mistakes navigate={navigate} params={params} />;
      case 'analytics': return <Analytics />;
      default: return <Dashboard navigate={navigate} />;
    }
  };

  const showOnboarding = !loading && profile && !profile.onboarded;

  return (
    <>
      {showOnboarding && <Onboarding />}

      <aside className="sidebar glass">
        <div className="logo">GATE DA <span>Mentor</span></div>
        <nav>
          {NAV.map((item) => (
            <button
              key={item.id}
              className={`nav-btn ${activeView === item.id ? 'active' : ''}`}
              onClick={() => navigate(item.id)}
            >
              <span className="nav-ico">{item.ico}</span>
              <span>{item.label}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-foot">Powered by Phi-4-mini · RAG</div>
      </aside>

      <main className="main-content">
        <TopBar />
        <div className="scroll-area">
          <div className="view-container" key={activeView}>
            {renderView()}
          </div>
        </div>
      </main>
    </>
  );
}

