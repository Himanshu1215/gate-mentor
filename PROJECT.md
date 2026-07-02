# Project: GATE Mentor

## Architecture
GATE Mentor is a desktop/local web application designed to help students prepare for the GATE Data Science & AI exam.
- **Frontend**: A Vite-based React application (`frontend-react`) with components for topics (Syllabus experience), practice quizzes, mock tests, and a chat interface (`AITutor.jsx`).
- **Backend API**: A FastAPI service (`presentation/api.py`) exposing endpoints at `http://localhost:8000`.
- **Intelligence Engine**: Grounded RAG system retrieving from ChromaDB, leveraging a local Phi-4-mini-instruct GGUF model via `llama-cpp-python`.
- **LangGraph Agent**: A new LangGraph-based service that handles AI Tutor sessions. It routes tutoring prompts (Visual Explanation, Derivations, PYQs, Quizzes) through a structured multi-agent state graph using the local LLM and ChromaDB retriever.

```
[React Frontend] (AITutor.jsx / Topics.jsx)
        │
        ▼ (HTTP REST)
[FastAPI Backend] (presentation/api.py)
        │
        ▼ (Internal Service Invocation)
[LangGraph Agent Service] (learning/langgraph_agent.py)
   ├── state: ChatState (messages, context, session, persona)
   ├── nodes:
   │     ├── RouterNode (identifies user intent)
   │     ├── RetrieveNode (queries ChromaDB / KnowledgeBase)
   │     ├── ExplainerNode (uses local LLM for standard RAG & Rubric formatting)
   │     ├── QuizNode (fetches/generates concept quizzes)
   │     └── PYQNode (fetches past GATE questions)
   └── resources: ChromaDB, sqlite3 DB, local Phi-4-mini LLM
```

## Milestones
| # | Name | Scope | Dependencies | Status | Conv ID |
|---|------|-------|-------------|--------|---------|
| 1 | Exploration & Setup | Explore codebase, dependencies, verify database & model paths, configure LangGraph environment | None | DONE | 0309de69-38b4-4df1-86e1-ec72965efa9e |
| 2 | E2E Test Suite Setup | Dual Track: Write comprehensive opaque-box test suite (Tiers 1-4) in `tests/e2e_test_suite.py` and output `TEST_READY.md` | None | DONE | 2535f8e3-602f-4c9a-a979-03601a11b138 |
| 3 | LangGraph Backend | Implement LangGraph agent in `learning/langgraph_agent.py` and integrate it into FastAPI `/api/chat` endpoint | M1, M2 | DONE | 136d5bc1-ea02-49a0-9276-00d5f14d064b |
| 4 | Frontend & Syllabus | Re-verify frontend connection, ensure all Syllabus features and AI tutor components interact properly | M3 | DONE | 052de6f6-d075-4e19-a424-cbcce741c540 |
| 5 | Adversarial Hardening | Implement Tier 5 testing (adversarial coverage hardening) and fix any outstanding edge cases | M4 | DONE | cec7a685-408d-4d7b-b9de-a9ea6ba3b2c8 |
| 6 | Verification & Sign-off | Run full test suite, verify all checks and formatting rubrics pass | M5 | IN_PROGRESS | 547d3cdc-3dba-4e64-b555-d5409b837df9 |

## Interface Contracts
### `POST /api/chat`
- **Request**: `{ "session_id": "string", "query": "string", "persona": "string" }`
- **Response**: `{ "reply": "string", "citations": ["string"] }`
- **Formatting Rubric**: AI explanations must:
  - Be step-by-step.
  - Use LaTeX for mathematical formatting.
  - End with "Final answer: X" (for direct questions/quizzes).
  - Show GATE-level rigor.
  - Avoid restating the question unnecessarily.

## Code Layout
- `presentation/api.py` - FastAPI endpoints, CORS, database session management
- `learning/langgraph_agent.py` - LangGraph state graph definition, nodes, and integration
- `learning/ai_reasoner.py` - Local LLM Wrapper (Phi-4-mini-instruct)
- `knowledge/pyq_repository.py` - SQLite & JSON PYQ registry and filter logic
- `frontend-react/` - Frontend codebase
  - `src/components/AITutor.jsx` - AI Tutor Chat UI
  - `src/components/Topics.jsx` - Syllabus view, detail view, note taker, file uploader
