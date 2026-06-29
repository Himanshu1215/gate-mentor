import React, { useState } from 'react';
import { useApp } from '../context/AppContext';

export default function Onboarding() {
  const { saveProfile, refresh } = useApp();
  const [name, setName] = useState('');
  const [targetAir, setTargetAir] = useState(500);
  const [examDate, setExamDate] = useState('2027-02-07'); // next GATE (first Sat of Feb)
  const [dailyGoal, setDailyGoal] = useState(10);
  const [saving, setSaving] = useState(false);

  const submit = async () => {
    setSaving(true);
    try {
      await saveProfile({
        display_name: name || 'Aspirant',
        target_air: Number(targetAir),
        exam_date: examDate,
        daily_goal: Number(dailyGoal),
      });
      await refresh();
    } catch (e) {
      alert('Could not save profile: ' + e.message);
      setSaving(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal glass">
        <h1>Welcome to GATE Mentor 🚀</h1>
        <p className="subtitle">Let's set your goal so we can track your journey.</p>

        <div className="field">
          <label>Your name</label>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Himanshu" />
        </div>
        <div className="field">
          <label>Target AIR (rank)</label>
          <input type="number" min="1" value={targetAir} onChange={(e) => setTargetAir(e.target.value)} />
        </div>
        <div className="field">
          <label>Exam date</label>
          <input type="date" value={examDate} onChange={(e) => setExamDate(e.target.value)} />
        </div>
        <div className="field">
          <label>Daily goal (questions per day)</label>
          <input type="number" min="1" max="100" value={dailyGoal} onChange={(e) => setDailyGoal(e.target.value)} />
        </div>

        <button className="btn-primary" style={{ width: '100%', marginTop: '1.5rem' }} onClick={submit} disabled={saving}>
          {saving ? 'Saving…' : 'Start preparing'}
        </button>
      </div>
    </div>
  );
}
