import React, { useState, useRef, useEffect } from 'react';
import api from '../api';

const SESSION_ID = 'tutor-' + Math.random().toString(36).slice(2, 9);
const PERSONAS = ['Professor', 'Friendly Mentor', 'IIT Lecturer', 'Beginner Friendly'];

export default function AITutor({ params }) {
  const [messages, setMessages] = useState([
    { role: 'ai', content: "Hello! I'm your AI Mentor, grounded in your GATE DA knowledge base. Ask me anything — or tap a shortcut below." },
  ]);
  const [input, setInput] = useState('');
  const [persona, setPersona] = useState('Professor');
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);
  const prefilledRef = useRef(false);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages, loading]);

  const send = async (text) => {
    const trimmed = (text ?? '').trim();
    if (!trimmed || loading) return;
    setMessages((m) => [...m, { role: 'user', content: trimmed }]);
    setInput('');
    setLoading(true);
    try {
      const data = await api.chat(trimmed, SESSION_ID, persona);
      setMessages((m) => [...m, { role: 'ai', content: data.reply, citations: data.citations }]);
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
      <header className="page-header">
        <div>
          <h1>AI Tutor</h1>
          <p className="subtitle">Your personal mentor, grounded in the GATE DA syllabus via RAG.</p>
        </div>
        <div className="select-row">
          <select className="app-select" value={persona} onChange={(e) => setPersona(e.target.value)} aria-label="Tutor persona">
            {PERSONAS.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>
      </header>

      <div className="glass chat-panel" style={{ borderRadius: 'var(--radius)' }}>
        <div className="messages">
          {messages.map((m, i) => (
            <div key={i} className={`message ${m.role}-message`}>
              <div className="bubble">
                {m.content}
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
  );
}
