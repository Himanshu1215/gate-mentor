import React, { useState } from 'react';

const mockPyqs = [
  {
    id: '2024_Q45',
    year: 2024,
    subject: 'Probability',
    marks: 2,
    type: 'MCQ',
    question: 'A factory has two machines with different production shares and defect rates. Find the posterior probability that a defective item came from Machine B.',
    hint: 'Write the total defective probability first, then divide Machine B defects by total defects.',
    solution: 'P(B | D) = P(D | B)P(B) / [P(D | A)P(A) + P(D | B)P(B)]. This gives 0.05 x 0.40 / (0.02 x 0.60 + 0.05 x 0.40) = 0.625.',
    similar: 'Practice Bayes theorem questions with medical tests, spam classification, and faulty batch selection.'
  },
  {
    id: '2023_Q12',
    year: 2023,
    subject: 'Linear Algebra',
    marks: 1,
    type: 'NAT',
    question: 'Find the determinant of the matrix [[1,2],[3,4]].',
    hint: 'For a 2 x 2 matrix [[a,b],[c,d]], determinant is ad - bc.',
    solution: 'The determinant is 1 x 4 - 2 x 3 = 4 - 6 = -2.',
    similar: 'Try determinant questions with triangular matrices and rank-deficient matrices.'
  },
  {
    id: '2024_Q22',
    year: 2024,
    subject: 'Machine Learning',
    marks: 2,
    type: 'MSQ',
    question: 'Which statements about SVM decision boundaries and margins are true?',
    hint: 'Focus on support vectors, margin maximization, and kernel transformations.',
    solution: 'SVM maximizes the margin between classes. Support vectors are the training points that determine the boundary. Kernels allow nonlinear separation in transformed feature spaces.',
    similar: 'Review margin, hinge loss, kernel trick, and support vector identification.'
  }
];

const PYQs = () => {
  const [expandedId, setExpandedId] = useState(null);
  const [activePanel, setActivePanel] = useState({});

  const toggleExpanded = (id) => {
    setExpandedId(expandedId === id ? null : id);
    setActivePanel({});
  };

  const showPanel = (id, panel) => {
    setActivePanel(prev => ({ ...prev, [id]: prev[id] === panel ? null : panel }));
  };

  const getPanelText = (pyq) => {
    const panel = activePanel[pyq.id];
    if (panel === 'try') return 'Solve it without looking at the solution. Write the known probabilities, compute the denominator, then substitute into the final expression.';
    if (panel === 'hint') return pyq.hint;
    if (panel === 'solution') return pyq.solution;
    if (panel === 'similar') return pyq.similar;
    return null;
  };

  return (
    <div>
      <header className="page-header pyq-header">
        <div>
          <h1>PYQ Explorer</h1>
          <p className="subtitle">Filter and practice Previous Year Questions.</p>
        </div>
        <div className="select-row">
          <select className="app-select" aria-label="Filter by year"><option>Year: All</option></select>
          <select className="app-select" aria-label="Filter by subject"><option>Subject: All</option></select>
          <select className="app-select" aria-label="Filter by question type"><option>Type: All</option></select>
        </div>
      </header>

      <div className="pyq-list">
        {mockPyqs.map(pyq => (
          <div key={pyq.id} className="glass pyq-card">
            <button className="pyq-summary" type="button" onClick={() => toggleExpanded(pyq.id)}>
              <div>
                <strong>GATE {pyq.year}</strong> | {pyq.subject} | {pyq.marks} Marks [{pyq.type}]
                <p>{pyq.question}</p>
              </div>
              <span>{expandedId === pyq.id ? 'Collapse' : 'Expand'}</span>
            </button>

            {expandedId === pyq.id && (
              <div className="pyq-expanded">
                <div className="action-toolbar">
                  <button className="chip" type="button" onClick={() => showPanel(pyq.id, 'try')}>Try yourself</button>
                  <button className="chip" type="button" onClick={() => showPanel(pyq.id, 'hint')}>Hint</button>
                  <button className="chip" type="button" onClick={() => showPanel(pyq.id, 'solution')}>Solution</button>
                  <button className="chip" type="button" onClick={() => showPanel(pyq.id, 'similar')}>Similar questions</button>
                </div>
                {getPanelText(pyq) && (
                  <div className="explanation-panel">
                    {getPanelText(pyq)}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

export default PYQs;
