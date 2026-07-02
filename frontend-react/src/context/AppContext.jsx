import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import api from '../api';

const AppContext = createContext(null);

export function AppProvider({ children }) {
  const [profile, setProfile] = useState(null);
  const [gamification, setGamification] = useState(null);
  const [loading, setLoading] = useState(true);

  const [mockState, setMockStateRaw] = useState(() => {
    try { return JSON.parse(localStorage.getItem('gate_mock_inprogress')); } catch(e) { return null; }
  });
  const setMockState = useCallback((s) => {
    setMockStateRaw(s);
    if (s) localStorage.setItem('gate_mock_inprogress', JSON.stringify(s));
    else localStorage.removeItem('gate_mock_inprogress');
  }, []);

  const [quizState, setQuizStateRaw] = useState(() => {
    try { return JSON.parse(localStorage.getItem('gate_quiz_inprogress')); } catch(e) { return null; }
  });
  const setQuizState = useCallback((s) => {
    setQuizStateRaw(s);
    if (s) localStorage.setItem('gate_quiz_inprogress', JSON.stringify(s));
    else localStorage.removeItem('gate_quiz_inprogress');
  }, []);

  const refreshGamification = useCallback(async () => {
    try {
      setGamification(await api.gamification());
    } catch (e) {
      console.warn('gamification load failed', e);
    }
  }, []);

  const refreshProfile = useCallback(async () => {
    try {
      setProfile(await api.getProfile());
    } catch (e) {
      console.warn('profile load failed', e);
    }
  }, []);

  // Call after any quiz/mock submit so streak/XP/level update live.
  const refresh = useCallback(async () => {
    await Promise.all([refreshGamification(), refreshProfile()]);
  }, [refreshGamification, refreshProfile]);

  const saveProfile = useCallback(async (payload) => {
    const updated = await api.putProfile(payload);
    setProfile({ ...updated, onboarded: true });
    return updated;
  }, []);

  useEffect(() => {
    (async () => {
      await refresh();
      setLoading(false);
    })();
  }, [refresh]);

  const value = { profile, gamification, loading, refresh, refreshGamification, saveProfile, mockState, setMockState, quizState, setQuizState };
  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be used within AppProvider');
  return ctx;
}

// Helper: days until exam from an ISO date string.
export function daysUntil(isoDate) {
  if (!isoDate) return null;
  const exam = new Date(isoDate);
  if (isNaN(exam)) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  exam.setHours(0, 0, 0, 0);
  return Math.round((exam - today) / (1000 * 60 * 60 * 24));
}
