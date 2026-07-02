import React, { useState, useEffect, useCallback } from 'react';
import api from '../api';
import MathText from './MathText';

const PAGE = 10;
const BOOKMARK_KEY = 'gate_pyq_bookmarks';

function loadBookmarks() {
  try { return new Set(JSON.parse(localStorage.getItem(BOOKMARK_KEY) || '[]')); }
  catch { return new Set(); }
}

export default function PYQs({ params, navigate }) {
  const [filters, setFilters] = useState(null);
  const [q, setQ] = useState('');
  const [year, setYear] = useState('');
  const [exam, setExam] = useState('');
  const [subject, setSubject] = useState('');
  const [type, setType] = useState('');
  const [hasSolution, setHasSolution] = useState(false);
  const [includeLow, setIncludeLow] = useState(false);
  const [conceptId, setConceptId] = useState(params?.concept_id || '');

  const [result, setResult] = useState(null);
  const [page, setPage] = useState(0);
  const [expanded, setExpanded] = useState(null);
  const [bookmarks, setBookmarks] = useState(loadBookmarks);
  const [loading, setLoading] = useState(false);
  
  const [answers, setAnswers] = useState({});
  const [revealed, setRevealed] = useState(new Set());
  const [qStarts, setQStarts] = useState({});

  const handleExpand = (pId) => {
    if (expanded === pId) {
      setExpanded(null);
    } else {
      setExpanded(pId);
      if (!revealed.has(pId) && !qStarts[pId]) {
        setQStarts(s => ({...s, [pId]: Date.now()}));
      }
    }
  };

  const submitAttempt = async (p, userAns) => {
    const isCorrect = userAns && p.answer && String(p.answer).toUpperCase() === String(userAns).toUpperCase();
    const tSec = qStarts[p.id] ? (Date.now() - qStarts[p.id]) / 1000 : 5;
    
    setAnswers(a => ({...a, [p.id]: userAns}));
    setRevealed(r => { const n = new Set(r); n.add(p.id); return n; });
    
    try {
      await api.submitQuiz({
        session_id: 'pyq-' + Math.random().toString(36).slice(2,9),
        concept_id: p.concept_id || 'GENERAL',
        is_correct: !!isCorrect,
        confidence: 3,
        question_id: p.id,
        user_answer: userAns,
        correct_answer: p.answer,
        time_taken_sec: tSec,
        source: 'pyq'
      });
    } catch(e) {}
  };

  useEffect(() => { api.getPyqFilters().then(setFilters).catch(() => {}); }, []);

  const search = useCallback(async (resetPage = true) => {
    setLoading(true);
    const offset = (resetPage ? 0 : page) * PAGE;
    if (resetPage) setPage(0);
    try {
      const data = await api.getPyqs({
        q, year, exam, subject, type,
        has_solution: hasSolution ? true : undefined,
        quality: includeLow ? 'all' : 'ok',
        concept_id: conceptId || undefined,
        limit: PAGE, offset,
      });
      setResult(data);
    } catch (e) { setResult({ items: [], total: 0 }); }
    finally { setLoading(false); }
  }, [q, year, exam, subject, type, hasSolution, includeLow, conceptId, page]);

  // initial + filter-driven search
  useEffect(() => { search(true); /* eslint-disable-next-line */ }, [year, exam, subject, type, hasSolution, includeLow, conceptId]);
  useEffect(() => { search(false); /* eslint-disable-next-line */ }, [page]);

  const toggleBookmark = (id) => {
    setBookmarks((prev) => {
      const n = new Set(prev);
      n.has(id) ? n.delete(id) : n.add(id);
      localStorage.setItem(BOOKMARK_KEY, JSON.stringify([...n]));
      return n;
    });
  };

  const items = result?.items || [];
  const total = result?.total || 0;
  const pages = Math.ceil(total / PAGE);

  return (
    <div>
      <header className="page-header">
        <div>
          <h1>PYQ Explorer</h1>
          <p className="subtitle">{filters ? `${filters.stats.total} real questions · ${filters.stats.with_solution} with full solutions` : 'Previous Year Questions'}</p>
        </div>
      </header>

      <div className="pyq-filters">
        <div className="pyq-search">
          <input value={q} placeholder="🔍 Search questions…" onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && search(true)} />
        </div>
        <select className="app-select" value={year} onChange={(e) => setYear(e.target.value)}>
          <option value="">All years</option>
          {filters?.years.map((y) => <option key={y} value={y}>{y}</option>)}
        </select>
        <select className="app-select" value={exam} onChange={(e) => setExam(e.target.value)}>
          <option value="">All exams</option>
          {filters?.exams.map((x) => <option key={x} value={x}>{x}</option>)}
        </select>
        <select className="app-select" value={subject} onChange={(e) => setSubject(e.target.value)}>
          <option value="">All subjects</option>
          {filters?.subjects.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select className="app-select" value={type} onChange={(e) => setType(e.target.value)}>
          <option value="">All types</option>
          <option value="MCQ">MCQ</option>
          <option value="MSQ">MSQ</option>
          <option value="NAT">NAT</option>
        </select>
        <button className="chip" style={hasSolution ? { borderColor: 'var(--accent-primary)', color: '#fff' } : {}}
          onClick={() => setHasSolution((v) => !v)}>{hasSolution ? '✓ ' : ''}With solution</button>
        <button className="chip" style={includeLow ? { borderColor: 'var(--warning)', color: '#fff' } : {}}
          onClick={() => setIncludeLow((v) => !v)} title="Show questions with imperfect PDF extraction">{includeLow ? '✓ ' : ''}Include low-quality</button>
        {conceptId && <button className="chip" onClick={() => setConceptId('')}>✕ concept: {conceptId}</button>}
      </div>

      {loading && <div className="loading"><span className="spinner" /> Searching…</div>}
      {!loading && items.length === 0 && <div className="empty">No questions match these filters.</div>}

      <div className="pyq-list">
        {items.map((p) => {
          const open = expanded === p.id;
          const marked = bookmarks.has(p.id);
          return (
            <div className="pyq-card card" key={p.id}>
              <div className="pyq-meta">
                {p.exam && <span className="tag">{p.exam} {p.year}</span>}
                <span className="tag accent">{p.question_type || 'MCQ'}</span>
                {p.marks && <span className="tag gold">{p.marks}m</span>}
                {p.subject && <span className="tag">{p.subject}</span>}
                {p.has_solution && <span className="tag" style={{ color: 'var(--success)' }}>solution</span>}
                {p.has_answer && (p.answer_verified
                  ? <span className="tag" style={{ color: 'var(--success)' }}>✓ verified</span>
                  : <span className="tag" style={{ color: 'var(--warning)' }} title="Answer not yet human/LLM-verified">⚠ unverified</span>)}
              </div>
              <div className="pyq-q">
                <div className="q-body" onClick={() => handleExpand(p.id)} style={{ cursor: 'pointer' }}>
                  <MathText>{p.question_text}</MathText>
                </div>
                <button className={`pyq-star ${marked ? 'on' : ''}`} title="Bookmark" onClick={() => toggleBookmark(p.id)}>
                  {marked ? '★' : '☆'}
                </button>
              </div>

              {open && (
                <div className="pyq-detail">
                  {p.options && Object.keys(p.options).length > 0 ? (
                    <div className="pyq-options">
                      {Object.entries(p.options).map(([k, v]) => {
                        const isRev = revealed.has(p.id);
                        let cls = 'pyq-opt';
                        if (isRev) {
                           if (p.answer && String(p.answer).toUpperCase() === k) cls += ' ans';
                           else if (answers[p.id] === k) cls += ' wrong';
                        }
                        const click = () => { if (!isRev) submitAttempt(p, k); };
                        
                        return (
                          <div key={k} className={cls} onClick={click} style={{ cursor: isRev ? 'default' : 'pointer', ...(cls.includes('wrong') ? {borderColor: 'var(--danger)', background: 'rgba(239,68,68,0.1)'} : {}) }}>
                            <b>{k})</b> <MathText>{v}</MathText>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="field" style={{ marginTop: '1rem' }}>
                      <label>Your answer (numerical)</label>
                      <input 
                         disabled={revealed.has(p.id)} 
                         placeholder="Type a number and press Enter" 
                         onKeyDown={(e) => {
                           if (e.key === 'Enter' && !revealed.has(p.id) && e.target.value) {
                             submitAttempt(p, e.target.value);
                           }
                         }} 
                      />
                      {revealed.has(p.id) && <div style={{marginTop: '0.5rem'}}><b>Your Answer:</b> {answers[p.id] || '(Blank)'}</div>}
                    </div>
                  )}

                  {!revealed.has(p.id) && (
                     <button className="btn-secondary" style={{ marginTop: '1rem' }} onClick={() => submitAttempt(p, null)}>Show answer</button>
                  )}

                  {revealed.has(p.id) && (
                    <div style={{ marginTop: '1.2rem' }}>
                      {p.answer && <p style={{ marginBottom: '0.7rem' }}><b>Correct Answer:</b> <span style={{ color: 'var(--success)' }}>{p.answer}</span></p>}
                      {p.solution
                        ? <div className="solution"><MathText>{p.solution}</MathText></div>
                        : <p className="subtitle">No worked solution on file for this question.</p>}
                      <div className="action-toolbar" style={{ marginTop: '0.8rem' }}>
                        <button className="chip" onClick={() => navigate('tutor', { prefill: `Explain this GATE question:\n\n${p.question_text}` })}>🤖 Ask tutor</button>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {pages > 1 && (
        <div className="pager">
          <button className="btn-secondary" disabled={page === 0} onClick={() => setPage((p) => Math.max(0, p - 1))}>← Prev</button>
          <span>Page {page + 1} of {pages} · {total} questions</span>
          <button className="btn-secondary" disabled={page + 1 >= pages} onClick={() => setPage((p) => p + 1)}>Next →</button>
        </div>
      )}
    </div>
  );
}
