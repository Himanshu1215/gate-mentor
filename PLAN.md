# GATE Mentor — Learning Loop Overhaul (Implementation Plan)

> **For the implementing agent:** This is the complete, authoritative spec. Implement phase by phase, in order.
> Each phase is independently shippable — verify it (see its Acceptance Criteria) and make one git commit per phase before moving on.
> Do NOT redesign the architecture, do NOT rewrite existing working modules, do NOT change the visual theme. ~70% of this plan is *wiring code that already exists*.

---

## 1. Background & Diagnosis

**Product:** Local web app for GATE Data Science & AI exam prep. FastAPI backend (`presentation/api.py`), React/Vite frontend (`frontend-react/`), SQLite (`data/gate_mentor.db`), ChromaDB RAG, local GGUF LLM via `llama-cpp-python`, LangGraph tutor agent (`learning/langgraph_agent.py`). Single user, no auth. Owner is a GATE DA 2027 aspirant (exam ~Feb 2027; profile default exam_date is 2027-02-07).

**Owner's complaint:** "The app is good but not helping me learn anything."

**Audit verdict (3-agent code audit, July 2026):** The app is a polished scoreboard around a learning loop that never closes. Durable learning = attempt → error → immediate elaborative feedback → spaced re-test of the failed item, plus calibration feedback and visible daily direction. The app breaks every stage:

| # | Failure | Evidence |
|---|---------|----------|
| 1 | **Mistakes are destroyed** | `quiz_attempts` stores only `concept_id + is_correct + confidence` — never which question or which wrong option. `POST /api/mock/grade` returns the graded result then persists only a `mocks_completed` counter — a 3-hour 65-question mock is non-reviewable. No mistakes screen exists. Quiz.jsx's `askedIds` is session-local and discarded on unmount. |
| 2 | **Personalization engine unreachable** | `planner/adaptive_scheduler.py` (`AdaptiveScheduler.generate_daily_schedule`: allocates daily time between spaced revision of lowest-accuracy concepts, capped 40%, and the next new concept from the curriculum DAG) is complete, tested, and imported by **no endpoint** — only `scripts/e2e_milestone2.py`. `GET /api/revision/due` reimplements drift thresholds inline instead of using `learning/concept_drift.py::ConceptDriftEngine`; drift only runs when `/api/coach/alerts` happens to be polled. |
| 3 | **Tutor can't teach** | `models/llm/` contains only `.gitkeep` → `learning/ai_reasoner.py::AIReasoningEngine` runs in MOCK mode (echoes ~200 chars of context). `data/chroma_db` does not exist → RAG retrieval returns the placeholder "Knowledge base is empty" — while textbooks (Strang, Ross, all-of-statistics, Han) sit un-ingested in `knowledge/textbooks/` and the working `knowledge/ingestor.py::ingest_directory()` is only invoked from a commented-out `__main__`. The agent is stateless: `/api/chat` builds `ChatState` with `messages=[]` every call; `session_id` is never used to load history; AITutor.jsx regenerates its session id on every remount; the tutor never reads `mastery_states` or `quiz_attempts`. |
| 4 | **Passive recognition dominates** | PYQs.jsx reveals the correct option + solution on card expand (recognition, not recall). AI study notes in Topics.jsx are read, never tested — and stored only in local component state (lost on navigation). Tutor Quiz node dumps question+options+answer+solution in a single message and never checks the user's answer. |
| 5 | **Insight never becomes action** | Analytics.jsx correctly diagnoses weak subjects and overconfidence (calibration chart flags confidence 4–5 with accuracy <60%) but nothing is clickable. Dashboard's "Projected AIR" is an opaque number with no lever explained. |
| 6 | **Effort silently destroyed** | `App.jsx` renders the active screen with `key={activeView}` → every sidebar click force-remounts, wiping an in-progress mock/quiz and resetting the tutor session. No confirm-navigation guard. |
| 7 | **DB is an empty, drifted shell** | Live DB: 0 quiz attempts, all 60 `mastery_states` at level 1 / accuracy 0 / `last_revised` NULL, `user_profile` empty. `infrastructure/database.py::init_db()` is **never called at API startup** (only its own `__main__` and tests). Live schema was built by `scripts/seed_syllabus.py` + an older schema: 4 orphan tables exist (`learning_analytics`, `quiz_logs`, `topic_mastery`, `user_goals`), and `concept_notes` / `concept_files` / `manual_revision_items` are missing until `_ensure_learning_tables()` (api.py ~line 349) lazily creates them. |
| 8 | **PYQ bank weakly tagged** | 646 parsed PYQ JSONs (`knowledge/official/pyqs/parsed/*.json`, loaded in-memory by `knowledge/pyq_repository.py` singleton). Only 8 distinct concept_ids; ~60% tagged `GENERAL`; difficulty null on all 646; 246 lack answer keys; solutions are LLM-distilled (`distilled:Qwen/Qwen2.5-Math-7B-Instruct`), not officially verified. Bank skews GATE ST (364) over GATE DA (282). |

**Owner's confirmed priorities:** all four — (a) know weak topics, (b) remember via spaced repetition, (c) understand concepts deeply, (d) daily study direction. **UI scope:** learning-first features + polish pass on the existing dark-glass theme (keep the theme — it's good). Exam: GATE 2027.

---

## 2. What already exists — REUSE, do not rebuild

| Capability | Where | Status |
|---|---|---|
| Quiz serve/submit loop with weak/revision/topic/mixed modes | `GET /api/quiz/next`, `POST /api/quiz/submit` (api.py) | Working; weak mode = lowest `state_level` via real SQL |
| Mastery update (±1 level, running accuracy, last_revised stamp) | `learning/decision_engine.py::MasteryCalculator.update_mastery` | Wired from quiz/submit |
| GATE-pattern mock generation + negative-marking grading; **answer key cached server-side per exam_id** | `assessment/simulation_engine.py::SimulationEngine` | Working — the cached key makes per-question persistence a one-loop change |
| Daily study planner (revision + next-concept time allocation) | `planner/adaptive_scheduler.py::AdaptiveScheduler.generate_daily_schedule(minutes)` | **Complete, orphaned — needs one endpoint** |
| Forgetting-curve decay | `learning/concept_drift.py::ConceptDriftEngine.apply_drift` | Only runs via `/api/coach/alerts` polling |
| Curriculum DAG next-concept | `curriculum/dependency_graph.py::CurriculumEngine` | Wired (`GET /api/curriculum/next`) |
| Session lifecycle incl. reflection storage | `learning/session_manager.py` — `start_session` wired; **`end_session` never called** | Needs one endpoint |
| Calibration metrics | `analytics/advanced_metrics.py::AdvancedMetrics` | Only reachable via coach |
| Gamification (XP/streak/badges), dashboard stats, analytics charts | `analytics/*.py`, `GET /api/gamification`, `/api/dashboard/stats`, `/api/analytics/overview` | Working, starved of data |
| KB ingestion (md/txt + PDF), chunking, metadata | `knowledge/ingestor.py::ingest_directory()`, `knowledge/ingestion.py` | Working, never invoked |
| GGUF auto-load with model-agnostic chat template | `learning/ai_reasoner.py` (commit 71fa596) | Needs a model *file*, not code |
| Lazy table creation pattern | `_ensure_learning_tables()` (api.py ~349) | Extend for new tables |
| Deep-link navigation between screens | `App.jsx::navigate(view, payload)` — already used Topics→Quiz, Topics/PYQs→AITutor, Dashboard→Revision | Reuse for all new click-throughs |
| Question card rendering (options, answer highlight, solution, LaTeX via MathText.jsx) | `PYQs.jsx` expand card | Reuse for Mistakes screen & mock review |
| Offline teacher-LLM batch pipeline | `scripts/data/distill_solutions.py` (commits d527ba6/71fa596) | Template for Phase 7 tagging job |

**Conventions to follow:** single-user (no auth, `user_profile` forced id=1); direct `sqlite3` SQL in api.py (no ORM); component-local fetch-on-mount in React with shared `AppContext` for profile/gamification; global stylesheet `index.css` with CSS variables (dark glassmorphism, cyan `#00f0ff` / purple `#7c3aed` accents, semantic success/danger/warning tokens); `MathText.jsx` for any question/solution text (KaTeX). Keep files under 500 lines — if `presentation/api.py` (currently 1006 lines) grows further, split into FastAPI routers (e.g. `presentation/routers/{quiz,mock,mistakes,schedule,chat}.py`) mounted from api.py.

---

## 3. Implementation Phases

### Phase 0 — Foundation & ops (½–1 day)

**0.1 Fix schema drift at startup.**
- In `presentation/api.py`, add a FastAPI lifespan (or `@app.on_event("startup")` matching the codebase's FastAPI version) that calls `infrastructure/database.py::init_db()` and the existing `_ensure_learning_tables()`.
- `init_db()` uses `CREATE TABLE IF NOT EXISTS` semantics — confirm it does; if any statement would clobber existing data, guard it. **Never DROP existing tables.** Leave the 4 orphan tables (`learning_analytics`, `quiz_logs`, `topic_mastery`, `user_goals`) alone.
- Add every new table from later phases into `infrastructure/database.py::init_db()` as well, so fresh installs and the live DB converge.

**0.2 Ingest the knowledge base.**
- Add `chromadb` and `sentence-transformers` to `requirements.txt` (pin versions compatible with the existing `knowledge/ingestor.py` code — it expects collection `gate_knowledge_base`, path `data/chroma_db`, embeddings `BAAI/bge-base-en-v1.5` cached to `models/embeddings/`).
- New script `scripts/ingest_knowledge.py`: calls `knowledge/ingestor.py::ingest_directory()` over `knowledge/textbooks/` (md/txt) and the PDF ingestor from `knowledge/ingestion.py` over textbook PDFs + `knowledge/official/syllabus/`. Idempotent (skip already-ingested sources by checking existing chunk metadata `source`). Print a summary count.
- Run it once. Verify `data/chroma_db` exists and a retrieval query returns real chunks.

**0.3 Load an LLM.**
- **Deployment target is an E2E VM with 8 GB RAM / 4 vCPU (CPU-only).** A 7B Q5 model (~5.4 GB weights + KV cache) will not fit alongside the BGE embedding model, ChromaDB, and the API process. Use a small instruct GGUF: recommend `Qwen2.5-3B-Instruct` Q4_K_M (~2 GB) or `Phi-4-mini-instruct` Q4 — `AIReasoningEngine` auto-loads any GGUF via `scripts/download_models.py`. Set a modest context (n_ctx ≈ 4096) and threads=4. Anything beats MOCK mode.
- If no model can be loaded, change the MOCK-mode reply to an honest message ("Local model not installed — run scripts/download_models.py") instead of echoing context as if it were an answer.

**Acceptance:** API starts clean; `sqlite3 data/gate_mentor.db ".tables"` shows `concept_notes`, `concept_files`, `manual_revision_items` (+ new tables); `POST /api/chat` with "explain Bayes theorem" returns grounded, non-placeholder content citing ingested sources.

---

### Phase 1 — Capture & review mistakes (1–2 days) ← highest learning impact

**1.1 New table `attempt_items`** (add to `init_db()` + `_ensure_learning_tables()`):
```sql
CREATE TABLE IF NOT EXISTS attempt_items (
  item_id      INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id   TEXT,
  source       TEXT NOT NULL CHECK(source IN ('quiz','mock','pyq')),
  exam_id      TEXT,              -- mock exam id, NULL for quiz/pyq
  question_id  TEXT NOT NULL,     -- pyq id from pyq_repository
  concept_id   TEXT,
  user_answer  TEXT,              -- selected option letter or NAT value; NULL = unattempted (mock)
  correct_answer TEXT,
  is_correct   INTEGER NOT NULL,  -- 0/1; unattempted mock rows: is_correct=0, user_answer NULL
  confidence   INTEGER,           -- 1-5, NULL for mock
  time_taken_sec REAL,
  marks_awarded REAL,             -- mock only (negative marking), NULL otherwise
  timestamp    TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_attempt_items_wrong ON attempt_items(is_correct, timestamp);
CREATE INDEX IF NOT EXISTS idx_attempt_items_exam ON attempt_items(exam_id);
```

**1.2 Extend `POST /api/quiz/submit`** (api.py ~line 197–229): accept optional `question_id`, `user_answer`, `correct_answer`, `time_taken_sec` in the request body (keep old fields working — frontend sends them from Phase 1 on). Insert an `attempt_items` row (`source='quiz'`) alongside the existing `quiz_attempts` insert and `MasteryCalculator` call. Frontend Quiz.jsx: track `time_taken_sec` per question (timestamp at question render → at submit) and send the new fields.

**1.3 Persist mock results in `POST /api/mock/grade`** (api.py ~860–880): the answer key is already cached server-side per `exam_id` in `SimulationEngine`. Before/at grading, insert one `attempt_items` row per question (`source='mock'`, including unattempted ones with `user_answer NULL`), plus one summary row:
```sql
CREATE TABLE IF NOT EXISTS mock_attempts (
  exam_id     TEXT PRIMARY KEY,
  taken_at    TEXT DEFAULT (datetime('now')),
  score REAL, max_score REAL,
  correct INTEGER, incorrect INTEGER, unattempted INTEGER,
  subject_breakdown TEXT   -- JSON as returned to the client today
);
```
Keep incrementing `user_profile.mocks_completed`.

**1.4 New endpoints:**
- `GET /api/mistakes?subject=&source=&since=&limit=&offset=` → wrong `attempt_items` rows (is_correct=0, user_answer NOT NULL), newest first, each joined to full question detail rehydrated from `knowledge/pyq_repository.py` by `question_id` (question text, options, correct answer, solution, subject/concept). Include the user's wrong answer.
- `GET /api/mock/attempts` → list of `mock_attempts` summaries.
- `GET /api/mock/attempts/{exam_id}/review` → the full paper: every `attempt_items` row for that exam joined to question detail, in original question order if recoverable (else by item_id).

**1.5 Frontend — Mistakes screen** (new `components/Mistakes.jsx`, new sidebar entry + view in App.jsx):
- List of wrong answers as expandable cards **reusing the PYQs.jsx card markup/classes** (options rendered with the user's pick highlighted in danger red and the correct one in success green; solution below; `MathText` for all math).
- Filters: subject, source (quiz/mock), time range.
- Per card actions: **"Ask tutor about this"** → existing `navigate('tutor', {prefill: ...})` with a prompt like "I answered {user_answer} but the correct answer is {correct}. Explain where my reasoning likely went wrong: {question text}". **"Re-test later"** → `POST /api/revision/schedule` with `question_id` (Phase 2.4).
- Empty state with CTA: "No mistakes logged yet — take a quiz."

**1.6 Frontend — Mock review:** after grading in MockTest.jsx, add a "Review answers" button on the score report → per-question review view (reuse the same card rendering; show marks awarded/lost per question, palette color-coded correct/incorrect/unattempted). Dashboard: "Past mocks" list from `GET /api/mock/attempts`, each opening its review.

**1.7 Frontend — Quiz summary upgrade** (Quiz.jsx): the end-of-set screen additionally lists each missed question (concept, your answer vs correct) with buttons "Review these now" (inline expand) and "Send all to revision" (batch Phase 2.4 enqueue — until Phase 2 exists, hide this button).

**Acceptance:** answer a quiz question wrongly → row in `attempt_items` with question_id/user_answer/time; Mistakes screen shows it with correct highlighting; grade a mock → `mock_attempts` + 65 `attempt_items` rows; full per-question review renders; "Ask tutor about this" lands in the tutor with the prefill.

---

### Phase 2 — Daily plan + item-level spaced repetition (1–1.5 days)

**2.1 `GET /api/schedule/today`** → instantiate `AdaptiveScheduler` and call `generate_daily_schedule(minutes)` where `minutes` derives from `user_profile.daily_goal` (if daily_goal is question-count, map ~3 min/question; read the scheduler's expected unit from its code and adapt). Return its structure as JSON: revision blocks (concept, minutes, reason) + new-concept block. Zero new planning logic.

**2.2 Dashboard "Today's plan" checklist** (Dashboard.jsx): replace the lone "Next up" card with a plan card listing: due revision items → deep-link `navigate('quiz', {mode:'revision', conceptId})`; new concept → `navigate('topics', {conceptId})`; plus "N questions to hit today's goal" → `navigate('quiz', {mode:'weak'})`. Checkable rows (checked state can live in localStorage keyed by date — cosmetic only).

**2.3 Drift consolidation:** refactor `GET /api/revision/due` to call `ConceptDriftEngine` instead of its inline threshold copy; run `apply_drift` once at API startup and then daily (simplest: track `last_drift_run` in a one-row meta table or user_profile column; run on startup if >24h). Remove the dependence on `/api/coach/alerts` polling for drift.

**2.4 Item-level spaced repetition:**
```sql
CREATE TABLE IF NOT EXISTS revision_queue_items (
  question_id  TEXT PRIMARY KEY,
  concept_id   TEXT,
  interval_days INTEGER DEFAULT 1,       -- 1 → 3 → 7 → 14
  due_at       TEXT NOT NULL,
  lapses       INTEGER DEFAULT 1,
  created_at   TEXT DEFAULT (datetime('now'))
);
```
- On every wrong `attempt_items` insert (quiz or mock): upsert into `revision_queue_items` with `due_at = now + interval_days` (reset interval to 1 on a new lapse).
- On a **correct** answer to a queued question in revision mode: advance the interval (1→3→7→14) and set new `due_at`; after passing at 14, delete the row (graduated).
- `GET /api/quiz/next?mode=revision`: serve due `revision_queue_items` questions first (rehydrate via pyq_repository), then fall back to the existing concept-level logic. Extend `POST /api/revision/schedule` to accept an optional `question_id` (writes to `revision_queue_items` instead of `manual_revision_items`).
- Revision.jsx: show due question-items count alongside due concepts ("5 failed questions + 2 concepts due today").

**Acceptance:** `GET /api/schedule/today` returns a sane plan; Dashboard checklist deep-links work; fail a question → it appears due tomorrow (test by manipulating `due_at` in sqlite); answer it right in revision mode → interval advances; drift runs at startup without `/api/coach/alerts`.

---

### Phase 3 — Active recall everywhere (1 day)

**3.1 PYQs attempt-before-reveal** (PYQs.jsx): expanding a card no longer shows the answer. Options become clickable buttons; solution and correct-answer highlight stay hidden (CSS blur or conditional render) until the user selects an option or clicks "Show answer" (counts as a skip, not an attempt). On selection: reveal + POST to `/api/quiz/submit` (`source` conveyed via new optional field or a `pyq=true` flag → recorded as `source='pyq'` in `attempt_items`; also updates mastery). Wrong picks enqueue into `revision_queue_items` like any other mistake. NAT questions get a small numeric input. Keep the existing filters/bookmarks untouched.

**3.2 Tutor quiz node two-turn** (learning/langgraph_agent.py): when routed to Quiz, return only the question + options and stash `{pending_question_id, correct_answer}` in the session state (Phase 4.1's persisted session makes this possible; if Phase 4 not yet done, keep a small in-memory dict keyed by session_id). On the next user message for that session, grade it: compare to the key, reply correct/incorrect + solution, and record an `attempt_items` row (`source='quiz'`, session_id).

**3.3 Retrieval checks after AI notes** (Topics.jsx): after AI notes render, show "Test yourself" with 2–3 questions fetched from `GET /api/quiz/next?mode=topic&concept_id=X` (sequential fetches with `exclude`), using the standard quiz interaction and submitting normally.

**Acceptance:** browsing PYQs requires an attempt before seeing answers and moves mastery/analytics; tutor asks then grades on the following turn; reading notes ends in a scored mini-check.

---

### Phase 4 — Tutor memory & personalization (1–2 days)

**4.1 Persist chat.**
```sql
CREATE TABLE IF NOT EXISTS chat_messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('user','assistant')),
  content TEXT NOT NULL,
  timestamp TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_chat_session ON chat_messages(session_id, id);
```
- AITutor.jsx: stable session id — generate once, store in localStorage (`gate_tutor_session`), never regenerate on remount; load history on mount via new `GET /api/chat/history?session_id=` and render it.
- `/api/chat`: load the last ~10 turns from `chat_messages` into `ChatState.messages` before invoking the graph; append the new user message + reply after. Cap the prompt context to fit the model's window.

**4.2 Student-context injection:** build a small context block (top 3–5 weakest concepts from `mastery_states`, last 5 wrong `attempt_items` with question ids/topics) and inject it into the Explainer node's system prompt: "Student's weak areas: … Recent mistakes: …". Router unchanged except passing state through.

**4.3 Persist AI notes** (Topics.jsx + api.py): add `ai_content TEXT` column to `concept_notes` (ALTER TABLE guarded by pragma check; also add to init_db). Extend the notes GET/PUT endpoints to carry `ai_content` separately from user `content`. Topics.jsx saves AI notes on generation and loads them on concept open — regenerate only on explicit "Regenerate" click.

**Acceptance:** tutor remembers the previous turn after a page refresh; asking "explain where I went wrong on that last one" works against injected mistake context; AI notes survive navigation and reload instantly.

---

### Phase 5 — Actionable analytics + metacognition (1 day)

**5.1 Clickable diagnosis:** Analytics.jsx — every subject-readiness bar → `navigate('quiz', {mode:'topic'-equivalent for subject or 'weak'})`; calibration red bars → quiz over the offending concepts. Dashboard weak-area/readiness tiles likewise. (Backend modes already exist; pass subject→concept mapping via the concepts list already fetched in Topics/AppContext or a small endpoint if needed.) Add a pointer cursor + tooltip "Click to practice".

**5.2 In-the-moment calibration** (Quiz.jsx, client-only): confidence ≥4 and wrong → distinct banner "⚠ Overconfident — under GATE negative marking this costs you marks. Slow down on {concept}."; confidence ≤2 and right → "You knew this — trust it." Quiz summary gains a calibration line ("overconfident on N of M").

**5.3 Session closure + reflection:** `POST /api/session/end {session_id, reflection}` → existing `SessionManager.end_session`. Frontend: on quiz-set completion and mock submission, show a single optional input "What tripped you up today?" → sends reflection. Start a session (existing `POST /api/session/start`) when a quiz set/mock begins if none active.

**5.4 Explain the AIR number** (Dashboard + `planner/goal_engine.py`): alongside Projected AIR, render "Biggest lever: master {concept} (+impact)" — compute from `GoalEngine` inputs + `concepts.importance_weight` × (8 − state_level), pick the top concept; link it to its topic page.

**Acceptance:** clicking any analytics bar lands in a relevant quiz; a confident-wrong answer shows the banner immediately; sessions get end_time + reflection rows; AIR card shows a concrete next lever.

---

### Phase 6 — Stop destroying work + UI polish (1 day)

**6.1 Kill the remount bug** (App.jsx): remove `key={activeView}` (or key only screens safe to remount — Dashboard, Analytics, PYQs). Lift in-progress quiz state and mock state (exam_id, answers map, time remaining, current index) into AppContext, mirrored to localStorage (`gate_mock_inprogress`). On MockTest mount with saved state and a server-cached exam_id → "Resume mock" banner. Add a confirm dialog when navigating away while a mock timer runs.

**6.2 Polish pass** (index.css + components), keeping the existing dark-glass theme and tokens:
- `:focus-visible` outlines on all custom controls (options, chips, nav); ARIA labels on icon-only buttons; keyboard operability for quiz options (radio semantics).
- Consistent empty states with CTAs everywhere data can be empty ("No data yet — take your first quiz →") instead of blank charts/zeros.
- Replace load-bearing emoji icons where ambiguous (nav can keep them; action buttons should have text labels).
- Loading skeletons for Dashboard/Analytics cards instead of spinner-only.

**Acceptance:** clicking the sidebar mid-mock warns; refusing keeps the mock; accepting and returning offers Resume; a keyboard-only user can complete a quiz; first-run screens all show CTAs, not emptiness.

---

### Phase 7 — (BACKLOG, optional, after 1–6) PYQ tagging batch job (2–4 days)

Offline script in the style of `scripts/data/distill_solutions.py`: for each of the 646 parsed PYQ JSONs, a teacher LLM assigns `concept_id` (one of the 60 in `scripts/seed_syllabus.py`'s DAG — give the model the concept list with subtopic descriptions), `difficulty` 1–10, and verifies/derives the answer key for the 246 answerless items (flag low-confidence ones `answer_source:"llm-derived"` and keep them out of the default answerable pool). Write back into the JSON files in place (fields already exist in the schema). Spot-check ≥40 items manually. Then: quiz/next can serve difficulty-banded, truly concept-targeted, interleaved sets, and `MasteryCalculator` can weight updates by difficulty. **Do not block Phases 1–6 on this.**

---

## 4. Cross-cutting rules

- **Never lose user data**: all schema changes are additive (`CREATE TABLE IF NOT EXISTS`, guarded `ALTER TABLE ADD COLUMN`). Never DROP/recreate.
- **Every new table** goes in BOTH `infrastructure/database.py::init_db()` and `_ensure_learning_tables()`.
- **All question/solution text** through `MathText.jsx` (KaTeX).
- **Reuse `navigate(view, payload)`** for every cross-screen action; no router library.
- Match existing code style: direct sqlite3 + parameterized queries in the API; functional React components with hooks; existing CSS classes/variables.
- Keep files <500 lines — split `presentation/api.py` into routers when you touch it heavily.
- Run backend + frontend and drive each acceptance flow before committing a phase; also run `pytest tests/` and `tests/e2e_test_suite.py` (some tests may assume the old schema — update tests, don't weaken assertions).
- One commit per phase with message `Phase N: <summary>`.

## 5. Verification (end-to-end, after all phases)

1. Fresh run: delete nothing; start backend (`uvicorn presentation.api:app --port 8000`) and frontend (`npm run dev` in `frontend-react/`); onboard a profile.
2. Take a 10-question weak-mode quiz answering some wrong → mistakes appear in Mistakes screen, wrong ones queued in revision, calibration banner fires on a confident-wrong, summary lists misses, reflection prompt appears.
3. `GET /api/schedule/today` drives the Dashboard checklist; every row deep-links correctly.
4. Take + submit a short mock → score report → per-question review → past-mocks list.
5. PYQ explorer: attempt-before-reveal, attempt recorded, mastery moves.
6. Tutor: ask for an explanation (grounded, cites sources), "quiz me" (two-turn grade), refresh page → history persists, "explain my last mistake" references the actual mistake.
7. Analytics: click a weak bar → targeted quiz.
8. Mid-mock sidebar click → warning; resume works.
wht


