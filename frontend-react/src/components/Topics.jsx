import React, { useState } from 'react';

const syllabus = {
  Probability: [
    { topic: 'Random Variables', mastery: 3, difficulty: 5 },
    { topic: 'Conditional Probability', mastery: 4, difficulty: 6 },
    { topic: 'Bayes Rule', mastery: 3, difficulty: 7 },
    { topic: 'Distributions', mastery: 2, difficulty: 7 }
  ],
  'Linear Algebra': [
    { topic: 'Matrix Operations', mastery: 5, difficulty: 4 },
    { topic: 'Vector Spaces', mastery: 6, difficulty: 6 },
    { topic: 'Eigenvalues', mastery: 2, difficulty: 8 },
    { topic: 'SVD', mastery: 1, difficulty: 9 }
  ],
  'Machine Learning': [
    { topic: 'Linear Regression', mastery: 4, difficulty: 5 },
    { topic: 'Logistic Regression', mastery: 2, difficulty: 6 },
    { topic: 'SVM', mastery: 1, difficulty: 8 },
    { topic: 'Decision Trees', mastery: 3, difficulty: 6 }
  ]
};

const Topics = () => {
  const [activeSubject, setActiveSubject] = useState('Probability');

  return (
    <div>
      <header>
        <div>
          <h1>Topic Explorer</h1>
          <p className="subtitle">Navigate the GATE DA syllabus dynamically.</p>
        </div>
      </header>

      <div className="topics-layout">
        <div className="glass subject-list">
          {Object.keys(syllabus).map(subject => (
            <button
              key={subject}
              type="button"
              className={`subject-btn ${activeSubject === subject ? 'active' : ''}`}
              onClick={() => setActiveSubject(subject)}
            >
              {subject}
            </button>
          ))}
        </div>

        <div className="topic-card-list">
          {syllabus[activeSubject].map((item, index) => (
            <div key={item.topic} className="glass topic-card">
              <div className="topic-card-header">
                <h3>{index + 1}. {item.topic}</h3>
                <div className="topic-meta">
                  <span>Mastery: Lvl {item.mastery}/8</span>
                  <span>Difficulty: {item.difficulty}/10</span>
                </div>
              </div>

              <div className="action-toolbar">
                <button className="chip" type="button">PYQs (12)</button>
                <button className="chip" type="button">Official Notes</button>
                <button className="chip" type="button">Video Lectures</button>
                <button className="chip" type="button">Formula Sheet</button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default Topics;
