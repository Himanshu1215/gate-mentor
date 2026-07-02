import React, { useEffect, useMemo, useState } from 'react';
import api from '../api';
import MathText from './MathText';

function ProgressBar({ value }) {
  const pct = Math.max(0, Math.min(100, Number(value) || 0));
  return (
    <div className="progress-track">
      <div className="progress-fill" style={{ width: `${pct}%` }} />
    </div>
  );
}

function DiffDots({ n }) {
  return (
    <div className="diff-dots" title={`Difficulty ${n}/8`}>
      {Array.from({ length: 8 }, (_, i) => <i key={i} className={i < n ? 'on' : ''} />)}
    </div>
  );
}

function flattenConcepts(subjects) {
  return (subjects || []).flatMap((s) => s.concepts || []);
}

function groupByTopic(concepts) {
  return concepts.reduce((acc, concept) => {
    if (!acc[concept.topic]) acc[concept.topic] = [];
    acc[concept.topic].push(concept);
    return acc;
  }, {});
}

function GraphNode({ concept, active, onClick }) {
  if (!concept) return null;
  return (
    <button className={`graph-node ${active ? 'current' : ''}`} onClick={() => onClick(concept.concept_id)}>
      <span>{concept.subtopic || concept.topic}</span>
      <small>Lvl {concept.mastery_level}/8</small>
    </button>
  );
}

function DependencyGraph({ concept, lookup, onSelect }) {
  const prereqs = (concept.prerequisites || []).map((id) => lookup[id]).filter(Boolean);
  const dependents = (concept.dependents || []).map((id) => lookup[id]).filter(Boolean);
  return (
    <div className="dependency-graph">
      <div className="graph-column">
        <div className="graph-label">Prerequisites</div>
        {prereqs.length ? prereqs.map((c) => <GraphNode key={c.concept_id} concept={c} onClick={onSelect} />) : <div className="graph-empty">Start topic</div>}
      </div>
      <div className="graph-column">
        <div className="graph-label">Current</div>
        <GraphNode concept={concept} active onClick={onSelect} />
      </div>
      <div className="graph-column">
        <div className="graph-label">Next topics</div>
        {dependents.length ? dependents.map((c) => <GraphNode key={c.concept_id} concept={c} onClick={onSelect} />) : <div className="graph-empty">End of branch</div>}
      </div>
    </div>
  );
}

export default function Topics({ navigate }) {
  const [payload, setPayload] = useState(null);
  const [active, setActive] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [error, setError] = useState(null);
  const [studyNotes, setStudyNotes] = useState({});
  const [studyNotesLoading, setStudyNotesLoading] = useState(false);
  const [selfNote, setSelfNote] = useState('');
  const [noteStatus, setNoteStatus] = useState('');
  const [files, setFiles] = useState([]);
  const [uploadStatus, setUploadStatus] = useState('');
  const [revisionStatus, setRevisionStatus] = useState('');

  const [testQuestions, setTestQuestions] = useState({});
  const [testLoading, setTestLoading] = useState(false);
  const [testAnswers, setTestAnswers] = useState({});
  const [testRevealed, setTestRevealed] = useState(new Set());

  const subjects = payload?.subjects || [];
  const allConcepts = useMemo(() => flattenConcepts(subjects), [subjects]);
  const lookup = useMemo(() => Object.fromEntries(allConcepts.map((c) => [c.concept_id, c])), [allConcepts]);
  const current = subjects.find((s) => s.subject === active);
  const selected = selectedId ? lookup[selectedId] : null;

  useEffect(() => {
    api.getConcepts()
      .then((d) => {
        setPayload(d);
        if (d.subjects?.length) setActive(d.subjects[0].subject);
      })
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    setNoteStatus('');
    setUploadStatus('');
    setRevisionStatus('');
    api.getConcept(selectedId)
      .then((d) => {
        setSelfNote(d.notes?.self_note || '');
        setFiles(d.notes?.uploaded_files || []);
      })
      .catch(() => {
        setSelfNote('');
        setFiles([]);
      });

    if (!studyNotes[selectedId]) {
      setStudyNotesLoading(true);
      api.getStudyNotes(selectedId)
        .then((d) => setStudyNotes((prev) => ({ ...prev, [selectedId]: d })))
        .catch(() => setStudyNotes((prev) => ({ ...prev, [selectedId]: { available: false } })))
        .finally(() => setStudyNotesLoading(false));
    }
  }, [selectedId]);

  const selectConcept = (conceptId) => {
    const concept = lookup[conceptId];
    if (concept) setActive(concept.subject);
    setSelectedId(conceptId);
  };

  const practiceQuestions = async () => {
    if (!selected) return;
    setTestLoading(true);
    try {
      const q1 = await api.quizNext({ mode: 'topic', concept_id: selected.concept_id, exclude: '' });
      const qs = [q1];
      try {
        const q2 = await api.quizNext({ mode: 'topic', concept_id: selected.concept_id, exclude: q1.pyq_id });
        if (q2 && q2.pyq_id !== q1.pyq_id) qs.push(q2);
      } catch (e) {}
      setTestQuestions((p) => ({ ...p, [selected.concept_id]: qs }));
    } catch (e) {
      /* non-fatal — button stays available to retry */
    } finally {
      setTestLoading(false);
    }
  };

  const saveNotes = async () => {
    if (!selected) return;
    setNoteStatus('Saving...');
    try {
      const saved = await api.saveConceptNotes(selected.concept_id, selfNote);
      setSelfNote(saved.content || '');
      setNoteStatus('Saved');
    } catch (e) {
      setNoteStatus(`Failed: ${e.message}`);
    }
  };

  const uploadFile = async (event) => {
    const file = event.target.files?.[0];
    if (!selected || !file) return;
    setUploadStatus('Uploading...');
    try {
      await api.uploadConceptFile(selected.concept_id, file);
      const refreshed = await api.getConceptFiles(selected.concept_id);
      setFiles(refreshed.files || []);
      setUploadStatus('Uploaded');
    } catch (e) {
      setUploadStatus(`Failed: ${e.message}`);
    } finally {
      event.target.value = '';
    }
  };

  const scheduleRevision = async () => {
    if (!selected) return;
    setRevisionStatus('Scheduling...');
    try {
      await api.scheduleRevision(selected.concept_id, 1);
      setRevisionStatus('Added to revision for tomorrow');
    } catch (e) {
      setRevisionStatus(`Failed: ${e.message}`);
    }
  };

  if (error) return <div className="empty">Couldn't load syllabus: {error}</div>;
  if (!payload) return <div className="loading"><span className="spinner" /> Loading syllabus...</div>;

  if (selected) {
    const noteState = studyNotes[selected.concept_id];
    const prereqNames = (selected.blocked_by || []).map((id) => lookup[id]?.subtopic || id).join(', ');
    return (
      <div className="concept-detail">
        <button className="btn-secondary" onClick={() => setSelectedId(null)}>Back to syllabus</button>

        <header className="detail-header">
          <div>
            <div className="cc-topic">{selected.subject} / {selected.topic}</div>
            <h1>{selected.subtopic}</h1>
            <p className="subtitle">{selected.status} / Difficulty {selected.difficulty}/8 / {selected.est_learning_time_mins} min learn / {selected.est_revision_time_mins} min revise</p>
          </div>
          <div className="detail-score">
            <b>{selected.progress_percent}%</b>
            <span>topic progress</span>
          </div>
        </header>

        <div className="card detail-meta">
          <div>
            <span>Mastery</span>
            <b>Level {selected.mastery_level}/8</b>
            <ProgressBar value={selected.progress_percent} />
          </div>
          <div>
            <span>Accuracy</span>
            <b>{Math.round((selected.accuracy || 0) * 100)}%</b>
            <ProgressBar value={(selected.accuracy || 0) * 100} />
          </div>
          <div>
            <span>Importance</span>
            <b>{Math.round((selected.importance_weight || 0) * 100)}%</b>
            <ProgressBar value={(selected.importance_weight || 0) * 100} />
          </div>
        </div>

        {selected.locked && <div className="empty compact">Locked for practice until prerequisites improve: {prereqNames}</div>}

        <div className="card">
          <h2>Learning graph</h2>
          <DependencyGraph concept={selected} lookup={lookup} onSelect={selectConcept} />
        </div>

        <div className="detail-grid">
          <section className="card ai-notes-panel">
            <div className="panel-head">
              <h2>Study notes</h2>
              <button className="chip" onClick={practiceQuestions} disabled={testLoading}>
                {testLoading ? 'Loading…' : 'Practice 2 questions'}
              </button>
            </div>
            {studyNotesLoading && <div className="loading"><span className="spinner" /> Loading notes...</div>}
            {!studyNotesLoading && noteState && !noteState.available && (
              <div className="empty compact">
                Notes not generated yet for this concept.
                <div style={{ marginTop: '0.6rem' }}>
                  <button className="btn-secondary" onClick={() => navigate('tutor', { prefill: `Explain ${selected.subtopic} from ${selected.subject} for GATE DA with examples.` })}>Ask tutor</button>
                </div>
              </div>
            )}
            {!studyNotesLoading && noteState?.available && (
              <div className="notes-output" style={{ whiteSpace: 'pre-wrap' }}>{noteState.content}</div>
            )}

            {testQuestions[selected.concept_id] && testQuestions[selected.concept_id].length > 0 && (
              <div style={{ marginTop: '1.5rem', borderTop: '1px solid var(--border)', paddingTop: '1.5rem' }}>
                <h3 style={{ marginBottom: '1rem' }}>Test Yourself</h3>
                {testQuestions[selected.concept_id].map((q) => {
                   const qKey = `${selected.concept_id}_${q.pyq_id}`;
                   const isRev = testRevealed.has(qKey);
                   const clickAns = async (k) => {
                      if (isRev) return;
                      setTestAnswers(p => ({...p, [qKey]: k}));
                      setTestRevealed(s => { const n = new Set(s); n.add(qKey); return n; });
                      const isCorrect = k && q.answer && String(q.answer).toUpperCase() === String(k).toUpperCase();
                      try {
                        await api.submitQuiz({
                          session_id: 'test-' + Math.random().toString(36).slice(2,9),
                          concept_id: selected.concept_id,
                          is_correct: !!isCorrect,
                          confidence: 3,
                          question_id: q.pyq_id,
                          user_answer: k,
                          correct_answer: q.answer,
                          time_taken_sec: 15,
                          source: 'quiz'
                        });
                      } catch(e) {}
                   };
                   
                   return (
                     <div key={q.pyq_id} style={{ marginBottom: '1.2rem', padding: '1rem', background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '6px' }}>
                       <div style={{ marginBottom: '0.8rem' }}><MathText>{q.question_text}</MathText></div>
                       {q.options && Object.keys(q.options).length > 0 ? (
                         <div className="pyq-options">
                           {Object.entries(q.options).map(([k, v]) => {
                              let cls = 'pyq-opt';
                              if (isRev) {
                                 if (q.answer && String(q.answer).toUpperCase() === k) cls += ' ans';
                                 else if (testAnswers[qKey] === k) cls += ' wrong';
                              }
                              return (
                                <div key={k} className={cls} onClick={() => clickAns(k)} style={{ cursor: isRev ? 'default' : 'pointer', ...(cls.includes('wrong') ? {borderColor: 'var(--danger)', background: 'rgba(239,68,68,0.1)'} : {}) }}>
                                  <b>{k})</b> <MathText>{v}</MathText>
                                </div>
                              );
                           })}
                         </div>
                       ) : (
                         <div className="field">
                           <input disabled={isRev} placeholder="Numerical answer and press Enter" onKeyDown={(e) => {
                             if (e.key === 'Enter' && e.target.value) clickAns(e.target.value);
                           }} />
                           {isRev && <div style={{marginTop:'0.5rem'}}><b>Your Answer:</b> {testAnswers[qKey] || '(Blank)'}</div>}
                         </div>
                       )}
                       
                       {!isRev && <button className="btn-secondary" style={{ marginTop: '0.8rem' }} onClick={() => clickAns(null)}>Show answer</button>}
                       
                       {isRev && (
                         <div style={{ marginTop: '1rem', fontSize: '0.95rem' }}>
                           <div><b>Correct Answer:</b> <span style={{ color: 'var(--success)' }}>{q.answer || 'N/A'}</span></div>
                           <div style={{ marginTop: '0.5rem', background: 'rgba(0,0,0,0.2)', padding: '0.8rem', borderRadius: '4px' }}>
                              <MathText>{q.solution || 'No explanation available.'}</MathText>
                           </div>
                         </div>
                       )}
                     </div>
                   );
                })}
              </div>
            )}
          </section>

          <section className="card uploaded-notes-panel">
            <h2>Uploaded notes</h2>
            <div className="upload-row">
              <input type="file" accept=".pdf,.md,.txt" onChange={uploadFile} />
              {uploadStatus && <span className="save-status">{uploadStatus}</span>}
            </div>
            <div className="file-list">
              {files.length === 0 && <p className="subtitle">No PDFs or files uploaded for this topic yet.</p>}
              {files.map((f) => (
                <a className="file-item" key={f.file_id} href={`/api/concepts/${selected.concept_id}/files/${f.file_id}`} target="_blank" rel="noreferrer">
                  <span>{f.filename}</span>
                  <small>{f.file_type || 'file'} / {f.uploaded_at}</small>
                </a>
              ))}
            </div>
          </section>
        </div>

        <section className="card self-notes-panel">
          <div className="panel-head">
            <h2>My self notes</h2>
            {noteStatus && <span className="save-status">{noteStatus}</span>}
          </div>
          <textarea
            className="notes-textarea"
            value={selfNote}
            onChange={(e) => setSelfNote(e.target.value)}
            placeholder="Write formulas, shortcuts, mistakes, and personal reminders for this topic."
          />
          <div className="concept-actions">
            <button className="btn-primary" onClick={saveNotes}>Save notes</button>
            <button className="btn-secondary" onClick={() => navigate('quiz', { mode: 'topic', conceptId: selected.concept_id, topic: selected.subtopic })}>Practice questions</button>
            <button className="btn-secondary" onClick={() => navigate('pyqs', { concept_id: selected.concept_id })}>Solve PYQs</button>
            <button className="btn-secondary" onClick={() => navigate('tutor', { prefill: `Explain ${selected.subtopic} from ${selected.subject} for GATE DA with examples.` })}>Ask tutor</button>
            <button className="btn-secondary" onClick={scheduleRevision}>Add to revision</button>
            {revisionStatus && <span className="save-status">{revisionStatus}</span>}
          </div>
        </section>
      </div>
    );
  }

  const grouped = current ? groupByTopic(current.concepts || []) : {};

  return (
    <div>
      <header className="page-header">
        <div>
          <h1>Syllabus</h1>
          <p className="subtitle">Topic-wise GATE DA syllabus with notes, graph, PYQs, practice, and revision.</p>
        </div>
      </header>

      <section className="card syllabus-overview">
        <div className="overall-progress">
          <div>
            <h2>Overall GATE DA progress</h2>
            <p className="subtitle">{payload.overall.mastered}/{payload.overall.total} mastered / average mastery {payload.overall.average_mastery}/8</p>
          </div>
          <b>{payload.overall.progress_percent}%</b>
        </div>
        <ProgressBar value={payload.overall.progress_percent} />
      </section>

      <div className="subject-progress-list">
        {subjects.map((s) => (
          <button key={s.subject} className={`subject-progress-row ${active === s.subject ? 'active' : ''}`} onClick={() => setActive(s.subject)}>
            <span>{s.subject}</span>
            <ProgressBar value={s.progress_percent || s.readiness} />
            <b>{s.progress_percent || s.readiness}%</b>
          </button>
        ))}
      </div>

      <div className="subject-tabs">
        {subjects.map((s) => (
          <button key={s.subject} className={`subject-tab ${active === s.subject ? 'active' : ''}`} onClick={() => setActive(s.subject)}>
            {s.subject}<span className="st-count">{s.mastered}/{s.total}</span>
          </button>
        ))}
      </div>

      {current && Object.entries(grouped).map(([topic, concepts]) => (
        <section className="topic-section" key={topic}>
          <h2 className="topic-section-title">{topic}</h2>
          <div className="concept-grid">
            {concepts.map((c) => (
              <div className={`concept-card card ${c.locked ? 'locked' : ''}`} key={c.concept_id}>
                <div className="cc-head">
                  <div>
                    <div className="cc-topic">{c.status}</div>
                    <div className="cc-title">{c.subtopic}</div>
                  </div>
                  <DiffDots n={c.difficulty || 5} />
                </div>
                <div>
                  <div className="mini-row"><span>Mastery</span><span>Lvl {c.mastery_level}/8</span></div>
                  <ProgressBar value={c.progress_percent} />
                </div>
                {c.locked && <div className="lock-badge">Locked by prerequisites</div>}
                <div className="concept-actions">
                  <button className="chip" onClick={() => selectConcept(c.concept_id)}>Detail</button>
                  <button className="chip" onClick={() => navigate('quiz', { mode: 'topic', conceptId: c.concept_id, topic: c.subtopic })}>Quiz</button>
                  <button className="chip" onClick={() => navigate('pyqs', { concept_id: c.concept_id })}>PYQs</button>
                </div>
              </div>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
