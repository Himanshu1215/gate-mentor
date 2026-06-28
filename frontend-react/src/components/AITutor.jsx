import React, { useState } from 'react';

const AITutor = () => {
  const [messages, setMessages] = useState([
    { role: 'ai', content: "Hello! I am your AI Mentor. Let's conquer the GATE DA syllabus together." }
  ]);
  const [input, setInput] = useState('');

  const handleSend = () => {
    const trimmed = input.trim();
    if (!trimmed) return;

    setMessages(prev => [...prev, { role: 'user', content: trimmed }]);
    setInput('');

    setTimeout(() => {
      setMessages(prev => [
        ...prev,
        {
          role: 'ai',
          content: 'This is a simulated response. The next step is wiring this panel to /api/chat with RAG context.'
        }
      ]);
    }, 500);
  };

  return (
    <div className="ai-tutor-view">
      <header className="page-header tutor-header">
        <div>
          <h1>AI Tutor</h1>
          <p className="subtitle">Your personal ChatGPT mapped exclusively to the GATE DA syllabus.</p>
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
              <div className="bubble">{message.content}</div>
            </div>
          ))}
        </div>

        <div className="action-toolbar tutor-actions">
          <button className="chip" type="button">Explain visually</button>
          <button className="chip" type="button">Show derivation</button>
          <button className="chip" type="button">Give a PYQ</button>
          <button className="chip" type="button">Quiz me</button>
          <button className="chip" type="button">Create flashcards</button>
        </div>

        <div className="chat-input-container">
          <input
            type="text"
            id="chat-input"
            placeholder="Ask me anything about Data Science and AI..."
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => event.key === 'Enter' && handleSend()}
          />
          <button className="btn-primary" type="button" onClick={handleSend}>Send</button>
        </div>
      </div>
    </div>
  );
};

export default AITutor;
