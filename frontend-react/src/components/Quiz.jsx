import React, { useState } from 'react';

const quizQuestion = {
  prompt: 'In a factory, Machine A produces 60% of the output and Machine B produces 40%. The defect rates are 2% and 5% respectively. If a randomly selected item is defective, what is the probability it was produced by Machine B?',
  answer: 'A',
  explanation: 'Using Bayes theorem: P(B | defective) = P(defective | B)P(B) / P(defective). The numerator is 0.05 x 0.40 = 0.02. The total defect probability is 0.02 x 0.60 + 0.05 x 0.40 = 0.032. So the answer is 0.02 / 0.032 = 0.625.',
  options: [
    { id: 'A', text: '0.625' },
    { id: 'B', text: '0.375' },
    { id: 'C', text: '0.500' },
    { id: 'D', text: '0.750' }
  ]
};

const Quiz = () => {
  const [activeQuiz, setActiveQuiz] = useState(false);
  const [selectedAnswer, setSelectedAnswer] = useState('');
  const [result, setResult] = useState(null);

  const startQuiz = () => {
    setActiveQuiz(true);
    setSelectedAnswer('');
    setResult(null);
  };

  const closeQuiz = () => {
    setActiveQuiz(false);
    setSelectedAnswer('');
    setResult(null);
  };

  const submitAnswer = () => {
    if (!selectedAnswer) {
      setResult({ type: 'warning', title: 'Select an answer first.' });
      return;
    }

    const isCorrect = selectedAnswer === quizQuestion.answer;
    setResult({
      type: isCorrect ? 'success' : 'error',
      title: isCorrect ? 'Correct answer.' : 'Incorrect answer.',
      selected: selectedAnswer,
      correct: quizQuestion.answer,
      explanation: quizQuestion.explanation
    });
  };

  return (
    <div>
      <header>
        <div>
          <h1>Quiz Center</h1>
          <p className="subtitle">Test your knowledge. Build your mastery.</p>
        </div>
      </header>

      {!activeQuiz ? (
        <div className="quiz-card-grid">
          <button className="glass quiz-mode-card" type="button" onClick={startQuiz}>
            <h2>Topic Quiz</h2>
            <p>Focus on a single specific concept.</p>
          </button>
          <button className="glass quiz-mode-card" type="button" onClick={startQuiz}>
            <h2>Mixed Quiz</h2>
            <p>Random questions from mastered topics.</p>
          </button>
          <button className="glass quiz-mode-card" type="button" onClick={startQuiz}>
            <h2>Full Mock Exam</h2>
            <p>65 questions. 3 hours. GATE schema.</p>
          </button>
          <button className="glass quiz-mode-card" type="button" onClick={startQuiz}>
            <h2>Weak Topics</h2>
            <p>Target areas where accuracy is below 40%.</p>
          </button>
          <button className="glass quiz-mode-card" type="button" onClick={startQuiz}>
            <h2>Revision Quiz</h2>
            <p>Overdue topics via spaced repetition.</p>
          </button>
        </div>
      ) : (
        <div className="glass quiz-panel">
          <h2>Q1. [MCQ] [2 Marks]</h2>
          <p className="question-text">{quizQuestion.prompt}</p>

          <div className="answer-list">
            {quizQuestion.options.map(option => (
              <label
                key={option.id}
                className={`answer-option ${selectedAnswer === option.id ? 'selected' : ''}`}
              >
                <input
                  type="radio"
                  name="mock_q1"
                  value={option.id}
                  checked={selectedAnswer === option.id}
                  onChange={() => setSelectedAnswer(option.id)}
                />
                <strong>{option.id})</strong>
                <span>{option.text}</span>
              </label>
            ))}
          </div>

          {result && (
            <div className={`result-panel ${result.type}`}>
              <h3>{result.title}</h3>
              {result.correct && (
                <>
                  <p>Your answer: <strong>{result.selected}</strong></p>
                  <p>Correct answer: <strong>{result.correct}) 0.625</strong></p>
                  <p>{result.explanation}</p>
                </>
              )}
            </div>
          )}

          <div className="quiz-actions">
            <button className="btn-secondary" type="button" onClick={closeQuiz}>Cancel</button>
            <button className="btn-primary" type="button" onClick={submitAnswer}>Submit Quiz</button>
          </div>
        </div>
      )}
    </div>
  );
};

export default Quiz;
