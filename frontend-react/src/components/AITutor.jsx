import React, { useState, useRef, useEffect } from 'react';
import api from '../api';
import MathText from './MathText';

const DEFAULT_SESSION = 'tutor-' + Math.random().toString(36).slice(2, 9);
const PERSONAS = ['Professor', 'Friendly Mentor', 'IIT Lecturer', 'Beginner Friendly'];

export default function AITutor({ params }) {
  const [sessions, setSessions] = useState([]);
  const [activeSession, setActiveSession] = useState(DEFAULT_SESSION);
  const [messages, setMessages] = useState([
    { role: 'ai', content: "Hello! I'm your AI Mentor, grounded in your GATE DA knowledge base. Ask me anything — or tap a shortcut below." },
  ]);
  const [input, setInput] = useState('');
  const [persona, setPersona] = useState('Professor');
  const [loading, setLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const bottomRef = useRef(null);
  const prefilledRef = useRef(false);
  const conceptId = params?.conceptId || null;

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages, loading]);

  useEffect(() => {
    api.getChatSessions().then(data => setSessions(data.sessions || [])).catch(console.error);
  }, []);

  const loadSession = async (sessionId) => {
    setActiveSession(sessionId);
    setSidebarOpen(false);
    try {
      const data = await api.getChatHistory(sessionId);
      if (data.messages && data.messages.length > 0) {
        setMessages(data.messages.map(m => ({
          role: m.role === 'assistant' ? 'ai' : 'user',
          content: m.content
        })));
      }
    } catch (e) {
      console.error(e);
    }
  };

  const newChat = () => {
    setActiveSession('tutor-' + Math.random().toString(36).slice(2, 9));
    setMessages([{ role: 'ai', content: "Hello! I'm your AI Mentor, grounded in your GATE DA knowledge base. Ask me anything — or tap a shortcut below." }]);
    setSidebarOpen(false);
  };

  const send = async (text) => {
    const trimmed = (text ?? '').trim();
    if (!trimmed || loading) return;
    setMessages((m) => [...m, { role: 'user', content: trimmed }]);
    setInput('');
    setLoading(true);
    try {
      const data = await api.chat(trimmed, activeSession, persona, conceptId);
      setMessages((m) => [...m, { role: 'ai', content: data.reply, citations: data.citations }]);
      api.getChatSessions().then(data => setSessions(data.sessions || [])).catch(console.error);
    } catch (e) {
      setMessages((m) => [...m, { role: 'ai', content: `Sorry, I couldn't reach the tutor. (${e.message})` }]);
    } finally {
      setLoading(false);
    }
  };

  // Deep-link prefill from Topics / PYQs ("Ask tutor about this")
  useEffect(() => {
    if (params?.prefill && !prefilledRef.current) {
      prefilledRef.current = true;
      send(params.prefill);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params]);

  return (
    <div className="ai-tutor-view">
      <header className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <button className="btn-secondary" onClick={() => setSidebarOpen(!sidebarOpen)} style={{ padding: '0.25rem 0.5rem', display: 'block' }}>☰ History</button>
            AI Tutor
          </h1>
          <p className="subtitle">Your personal mentor, grounded in the GATE DA syllabus via RAG.</p>
        </div>
        <div className="select-row">
          <select className="app-select" value={persona} onChange={(e) => setPersona(e.target.value)} aria-label="Tutor persona">
            {PERSONAS.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>
      </header>

      <div style={{ display: 'flex', gap: '1.5rem', flex: 1, overflow: 'hidden' }}>
        {sidebarOpen && (
          <div className="glass" style={{ width: '300px', flexShrink: 0, display: 'flex', flexDirection: 'column', borderRadius: 'var(--radius)', overflow: 'hidden' }}>
            <div style={{ padding: '1rem', borderBottom: '1px solid var(--border)' }}>
              <button className="btn-primary" style={{ width: '100%' }} onClick={newChat}>+ New Chat</button>
            </div>
            <div style={{ flex: 1, overflowY: 'auto' }}>
              {sessions.map(s => (
                <div 
                  key={s.session_id} 
                  onClick={() => loadSession(s.session_id)}
                  style={{ 
                    padding: '1rem', 
                    cursor: 'pointer', 
                    borderBottom: '1px solid var(--border)',
                    background: activeSession === s.session_id ? 'var(--card-hover)' : 'transparent'
                  }}
                >
                  <div style={{ fontWeight: 500, fontSize: '0.9rem', marginBottom: '0.25rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{s.title || 'Chat'}</div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{new Date(s.updated_at).toLocaleString()}</div>
                </div>
              ))}
              {sessions.length === 0 && <div style={{ padding: '1rem', color: 'var(--text-muted)', fontSize: '0.9rem' }}>No past sessions.</div>}
            </div>
          </div>
        )}

        <div className="glass chat-panel" style={{ borderRadius: 'var(--radius)', flex: 1 }}>
        <div className="messages">
          {messages.map((m, i) => (
            <div key={i} className={`message ${m.role}-message`}>
              <div className="bubble">
                <MathText>{m.content}</MathText>
                {m.citations?.length > 0 && (
                  <div className="citations">Sources: {m.citations.join(', ')}</div>
                )}
              </div>
            </div>
          ))}
          {loading && <div className="message ai-message"><div className="bubble" style={{ opacity: 0.6 }}>Thinking…</div></div>}
          <div ref={bottomRef} />
        </div>

        <div className="action-toolbar">
          {[
            ['Explain visually', 'Explain this concept visually with an intuitive example.'],
            ['Show derivation', 'Show the full step-by-step derivation.'],
            ['Give a PYQ', 'Give me a GATE previous-year question on this topic.'],
            ['Quiz me', 'Ask me one GATE-level question and wait for my answer.'],
          ].map(([label, prompt]) => (
            <button key={label} className="chip" onClick={() => send(prompt)} disabled={loading}>{label}</button>
          ))}
        </div>

        <div className="chat-input-container">
          <input
            value={input}
            placeholder="Ask anything about Data Science & AI…"
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && send(input)}
            disabled={loading}
          />
          <button className="btn-primary" onClick={() => send(input)} disabled={loading || !input.trim()}>
            {loading ? '…' : 'Send'}
          </button>
        </div>
        </div>
      </div>
    </div>
  );
}
