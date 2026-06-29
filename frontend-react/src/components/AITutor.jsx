import React, { useState, useRef, useEffect } from 'react';

const SESSION_ID = 'user-' + Math.random().toString(36).slice(2, 9);
const AUTH = 'Bearer gate-mentor-token';

const AITutor = () => {
  const [messages, setMessages] = useState([
    { role: 'ai', content: "Hello! I am your AI Mentor. Let's conquer the GATE DA syllabus together." }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = async (text) => {
    const trimmed = text.trim();
    if (!trimmed || loading) return;

    setMessages(prev => [...prev, { role: 'user', content: trimmed }]);
    setInput('');
    setLoading(true);

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': AUTH,
        },
        body: JSON.stringify({ session_id: SESSION_ID, query: trimmed }),
      });

      if (!res.ok) throw new Error(`Server error ${res.status}`);
      const data = await res.json();

      setMessages(prev => [...prev, { role: 'ai', content: data.reply, citations: data.citations }]);
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'ai',
        content: `Sorry, I couldn't reach the backend. (${err.message})`
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleChip = (text) => sendMessage(text);

  return (
    <div className="ai-tutor-view">
      <header className="page-header tutor-header">
        <div>
          <h1>AI Tutor</h1>
          <p className="subtitle">Your personal mentor mapped exclusively to the GATE DA syllabus.</p>
        </div>
        <div className="select-row">
          <select className="app-select" aria-label="Tutor persona">
            <option>Professor</option>
            <option>Friend</option>
            <option>IIT Lecturer</option>
            <option>Beginner Friendly</option>
          </select>
          <select className="app-select" aria-label="Difficulty">
            <option>GATE Level</option>
            <option>Beginner</option>
            <option>Advanced</option>
          </select>
        </div>
      </header>

      <div id="chat-window" className="glass chat-panel">
        <div className="messages">
          {messages.map((message, index) => (
            <div key={`${message.role}-${index}`} className={`message ${message.role}-message`}>
              <div className="bubble">
                {message.content}
                {message.citations && message.citations.length > 0 && (
                  <div className="citations" style={{ fontSize: '0.75em', opacity: 0.6, marginTop: 4 }}>
                    Sources: {message.citations.join(', ')}
                  </div>
                )}
              </div>
            </div>
          ))}
          {loading && (
            <div className="message ai-message">
              <div className="bubble" style={{ opacity: 0.6 }}>Thinking...</div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <div className="action-toolbar tutor-actions">
          <button className="chip" type="button" onClick={() => handleChip('Explain this concept visually with an example.')}>Explain visually</button>
          <button className="chip" type="button" onClick={() => handleChip('Show the step-by-step derivation.')}>Show derivation</button>
          <button className="chip" type="button" onClick={() => handleChip('Give me a GATE PYQ on this topic.')}>Give a PYQ</button>
          <button className="chip" type="button" onClick={() => handleChip('Quiz me on this concept.')}>Quiz me</button>
          <button className="chip" type="button" onClick={() => handleChip('Create flashcards for this topic.')}>Create flashcards</button>
        </div>

        <div className="chat-input-container">
          <input
            type="text"
            id="chat-input"
            placeholder="Ask me anything about Data Science and AI..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && sendMessage(input)}
            disabled={loading}
          />
          <button className="btn-primary" type="button" onClick={() => sendMessage(input)} disabled={loading}>
            {loading ? '...' : 'Send'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default AITutor;
