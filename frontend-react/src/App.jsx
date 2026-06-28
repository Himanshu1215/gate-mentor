import React, { useState } from 'react';
import Dashboard from './components/Dashboard';
import AITutor from './components/AITutor';
import Topics from './components/Topics';
import Quiz from './components/Quiz';
import PYQs from './components/PYQs';
import Revision from './components/Revision';
import Analytics from './components/Analytics';

function App() {
  const [activeView, setActiveView] = useState('dashboard');

  const navItems = [
    { id: 'dashboard', label: 'Dashboard' },
    { id: 'tutor', label: 'AI Tutor' },
    { id: 'topics', label: 'Topics' },
    { id: 'quiz', label: 'Quiz Center' },
    { id: 'pyqs', label: 'PYQ Explorer' },
    { id: 'revision', label: 'Revision' },
    { id: 'analytics', label: 'Analytics' },
  ];

  const renderView = () => {
    switch (activeView) {
      case 'dashboard': return <Dashboard />;
      case 'tutor': return <AITutor />;
      case 'topics': return <Topics />;
      case 'quiz': return <Quiz />;
      case 'pyqs': return <PYQs />;
      case 'revision': return <Revision />;
      case 'analytics': return <Analytics />;
      default: return <Dashboard />;
    }
  };

  return (
    <>
      <aside className="sidebar glass">
        <div className="logo">GATE DA <span>Mentor</span></div>
        <nav>
          {navItems.map(item => (
            <button 
              key={item.id}
              className={`nav-btn ${activeView === item.id ? 'active' : ''}`}
              onClick={() => setActiveView(item.id)}
            >
              {item.label}
            </button>
          ))}
        </nav>
      </aside>

      <main className="main-content">
        <div className="view-container">
            {renderView()}
        </div>
      </main>
    </>
  );
}

export default App;
