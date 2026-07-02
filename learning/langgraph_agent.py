import os
import re
import glob
import logging
import random
from typing import Dict, Any, List, Optional
from typing_extensions import TypedDict

logger = logging.getLogger(__name__)

# Try importing LangGraph
try:
    from langgraph.graph import StateGraph, END
    HAS_LANGGRAPH = True
except ImportError:
    HAS_LANGGRAPH = False
    logger.warning("langgraph not installed in current environment. Using CompiledMockGraph fallback.")

# ---------------------------------------------------------------------------
# ChatState definition
# ---------------------------------------------------------------------------
class ChatState(TypedDict):
    query: str
    session_id: str
    persona: str
    messages: List[Dict[str, Any]]
    context: List[Dict[str, Any]]
    reply: str
    citations: List[str]
    next_node: str
    concept_id: Optional[str]

# ---------------------------------------------------------------------------
# CompiledMockGraph Fallback when langgraph is not installed
# ---------------------------------------------------------------------------
if not HAS_LANGGRAPH:
    class StateGraph:
        def __init__(self, state_schema):
            self.state_schema = state_schema
            self.nodes = {}
            self.entry_point = None
            self.edges = []
            self.conditional_edges = {}

        def add_node(self, name, node):
            self.nodes[name] = node

        def set_entry_point(self, name):
            self.entry_point = name

        def add_edge(self, start, end):
            self.edges.append((start, end))

        def add_conditional_edges(self, start, router, path_map):
            self.conditional_edges[start] = (router, path_map)

        def compile(self):
            return CompiledMockGraph(self)

    END = "END"

    class CompiledMockGraph:
        def __init__(self, graph):
            self.graph = graph

        def invoke(self, state: dict) -> dict:
            curr = self.graph.entry_point
            state = dict(state)
            visited = set()
            while curr and curr != "END":
                if curr in visited:
                    break
                visited.add(curr)
                node_fn = self.graph.nodes.get(curr)
                if not node_fn:
                    break
                state = node_fn(state)
                if curr in self.graph.conditional_edges:
                    router_fn, path_map = self.graph.conditional_edges[curr]
                    next_node_name = router_fn(state)
                    curr = path_map.get(next_node_name, "END")
                else:
                    next_node = None
                    for start, end in self.graph.edges:
                        if start == curr:
                            next_node = end
                            break
                    curr = next_node if next_node else "END"
            return state

# ---------------------------------------------------------------------------
# Helper functions for Offline/Mock Fallback
# ---------------------------------------------------------------------------
def is_gguf_model_present() -> bool:
    """Check if any GGUF models are present in the models/llm/ folder."""
    llm_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "models", "llm"))
    env_override = os.environ.get("LLM_MODEL_PATH")
    if env_override and os.path.exists(env_override):
        return True
    preferred = os.path.join(llm_dir, "phi-4-mini-instruct-q4_k_m.gguf")
    if os.path.exists(preferred):
        return True
    candidates = glob.glob(os.path.join(llm_dir, "*.gguf"))
    return len(candidates) > 0

def find_matching_pyq(query: str, repo) -> Optional[Dict[str, Any]]:
    """Find a PYQ from the repository that matches the user query using Jaccard overlap."""
    def get_tokens(s):
        s = re.sub(r'[^\w\s]', '', s).lower()
        return set(s.split())

    query_tokens = get_tokens(query)
    stopwords = {
        "what", "is", "the", "of", "a", "an", "and", "in", "on", "at", "to", "for",
        "with", "by", "from", "that", "this", "these", "those", "it", "its", "was",
        "were", "been", "has", "have", "had", "do", "does", "did", "be", "being", "are",
        "if", "then", "else", "let", "consider", "suppose", "value"
    }
    query_tokens = query_tokens - stopwords
    if not query_tokens:
        return None

    best_match = None
    best_similarity = 0.0

    for item in repo._items:
        q_text = item.get("question_text", "")
        q_tokens = get_tokens(q_text) - stopwords
        if not q_tokens:
            continue
        
        intersection = query_tokens.intersection(q_tokens)
        similarity = len(intersection) / max(len(query_tokens), 1)
        if similarity > best_similarity:
            best_similarity = similarity
            best_match = item

    # Threshold: overlap of 60% of non-stopword query tokens, minimum of 4 query tokens
    if best_match and best_similarity >= 0.6 and len(query_tokens) >= 4:
        return best_match

    return None

def clean_solution(solution: str) -> str:
    """Clean the solution text to remove trailing question fragments or final answer segments."""
    if solution is None or not isinstance(solution, str):
        return ""
    lines = []
    for line in solution.split('\n'):
        line_lower = line.lower()
        if 'final answer' in line_lower or 'quick tip' in line_lower or 'correct answer' in line_lower:
            break
        if re.match(r'^\d+\s*\.\s*[a-zA-Z]', line):
            break
        lines.append(line)
    
    clean_text = '\n'.join(lines).strip()
    # Strip any preexisting final answer declarations
    clean_text = re.sub(r'(?i)final\s*answer.*$', '', clean_text).strip()
    return clean_text

def format_pyq_fallback(pyq: Dict[str, Any]) -> str:
    """Format the matched PYQ solution strictly according to the rubric."""
    if pyq is None or not isinstance(pyq, dict):
        return "No solution details available."
    sol = pyq.get("solution", "")
    clean_sol = clean_solution(sol)
    ans = pyq.get("answer", "")
    
    if not ans:
        ans = "N/A"
    if not clean_sol:
        clean_sol = "No solution explanation available."
        
    return f"{clean_sol}\n\nFinal answer: {ans}"

# ---------------------------------------------------------------------------
# State Graph Nodes
# ---------------------------------------------------------------------------
_PENDING_QUIZ_STATES = {}

_EXPLAIN_KEYWORDS = ("notes", "explain", "what is", "derive", "study", "teach")
_QUIZ_KEYWORDS = ("quiz", "test")
_PYQ_KEYWORDS = ("pyq", "previous year", "gate question")


def router_node(state: ChatState) -> ChatState:
    """Identifies the user's intent and updates the next node state.

    Intent-first: explanatory queries (notes/explain/what is/derive/study/
    teach) ALWAYS go to Retrieve, even in mock/offline mode. Previously, a
    mock-mode Jaccard PYQ match ran before intent classification and could
    hijack a "explain eigenvalues"-style query into a raw PYQ dump just
    because it happened to overlap with a stored question. That fuzzy match
    is now scoped inside the PYQ branch (see pyq_node), so it only ever
    fires once intent has already resolved to PYQ.
    """
    query = state.get("query", "")
    session_id = state.get("session_id", "")

    if session_id and session_id in _PENDING_QUIZ_STATES:
        state["next_node"] = "QuizGrade"
        return state

    query_lower = query.lower()
    if any(kw in query_lower for kw in _EXPLAIN_KEYWORDS):
        state["next_node"] = "Retrieve"
    elif any(kw in query_lower for kw in _QUIZ_KEYWORDS):
        state["next_node"] = "Quiz"
    elif any(kw in query_lower for kw in _PYQ_KEYWORDS):
        state["next_node"] = "PYQ"
    else:
        state["next_node"] = "Retrieve"

    return state

def retrieve_node(state: ChatState) -> ChatState:
    """Retrieves top relevant knowledge chunks from ChromaDB.

    Filters by explicit concept_id when the caller supplied one (e.g. from
    the Topics page); otherwise best-effort classifies a subject from the
    query text so retrieval stays scoped to the right corner of the corpus.
    """
    query = state.get("query", "")
    concept_id = state.get("concept_id")
    from knowledge.ingestor import KnowledgeIngestor

    subject = None
    if not concept_id:
        from core.subject_map import classify_query_subject
        subject = classify_query_subject(query)

    retriever = KnowledgeIngestor()
    context_chunks = retriever.query(query, concept_id=concept_id, subject=subject, top_k=5)

    if not context_chunks:
        context_chunks = [{
            "content": "Knowledge base is empty. Please ingest GATE content first via /api/upload or scripts/ingest_content.py.",
            "metadata": {"source": "System"}
        }]

    state["context"] = context_chunks
    return state

def explainer_node(state: ChatState) -> ChatState:
    """Generates a detailed tutorial explanation based on context."""
    query = state.get("query", "")
    context_chunks = state.get("context", [])
    persona = state.get("persona", "Professor")
    messages = state.get("messages", [])
    
    from learning.ai_reasoner import AIReasoningEngine
    reasoner = AIReasoningEngine()
    
    import sqlite3
    DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "gate_mentor.db")
    profile_summary = ""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        user = conn.execute("SELECT * FROM user_profile WHERE id=1").fetchone()
        if user:
            profile_summary += f"Student Target AIR: {user['target_air'] or 'N/A'}, Exam Date: {user['exam_date'] or 'N/A'}\n"
        
        weak = conn.execute("SELECT c.topic, m.state_level FROM mastery_states m JOIN concepts c ON m.concept_id=c.concept_id WHERE m.state_level <= 3 LIMIT 5").fetchall()
        if weak:
            profile_summary += "Student's Weak Concepts (Level 1-3 out of 8): " + ", ".join([f"{r['topic']} (L{r['state_level']})" for r in weak]) + "\n"
            
        strong = conn.execute("SELECT c.topic, m.state_level FROM mastery_states m JOIN concepts c ON m.concept_id=c.concept_id WHERE m.state_level >= 7 LIMIT 5").fetchall()
        if strong:
            profile_summary += "Student's Strong Concepts (Level 7-8 out of 8): " + ", ".join([f"{r['topic']} (L{r['state_level']})" for r in strong]) + "\n"
        conn.close()
    except Exception as e:
        logger.error(f"Error fetching profile context: {e}")
    
    reply = reasoner.generate_chat_reply(query, messages, context_chunks, persona, profile_summary)
    citations = list({chunk["metadata"].get("source", "Unknown") for chunk in context_chunks})
    
    state["reply"] = reply
    state["citations"] = citations
    return state

def quiz_node(state: ChatState) -> ChatState:
    """Generates or fetches quiz questions for a concept."""
    query = state.get("query", "")
    session_id = state.get("session_id", "")
    
    from knowledge.pyq_repository import get_repository
    repo = get_repository()
    
    concept_id = "ML_NB_001"
    match = re.search(r'[A-Z]{2,4}_[A-Z0-9]+_\d+', query)
    if match:
        concept_id = match.group(0)
        
    q = repo.random_question(concept_id=concept_id) or repo.random_question()
    if q:
        reply = f"Quiz Question:\n{q.get('question_text')}\n\nOptions:\n"
        for k, v in (q.get("options") or {}).items():
            reply += f"{k}) {v}\n"
        reply += "\n*Reply with your answer (e.g. A, B, C, D) to check it!*"
        
        _PENDING_QUIZ_STATES[session_id] = {
            "question_id": q.get("id"),
            "concept_id": q.get("concept_id") or concept_id,
            "correct_answer": q.get("answer", ""),
            "solution": q.get("solution", ""),
            "citations": [q.get("id")]
        }
        citations = [q.get("id")]
    else:
        reply = "No quiz questions available."
        citations = []
            
    state["reply"] = reply
    state["citations"] = citations
    return state

def quiz_grade_node(state: ChatState) -> ChatState:
    session_id = state.get("session_id", "")
    query = state.get("query", "").strip()
    
    pending = _PENDING_QUIZ_STATES.pop(session_id, None)
    if not pending:
        state["reply"] = "Quiz session expired."
        state["citations"] = []
        return state
        
    user_ans = query.upper()
    correct_ans = str(pending["correct_answer"]).upper()
    
    is_correct = (user_ans == correct_ans) or (len(user_ans) > 0 and user_ans in correct_ans)
    
    import sqlite3
    DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "gate_mentor.db")
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("""
            INSERT INTO attempt_items
            (session_id, source, question_id, concept_id, user_answer, correct_answer, is_correct, confidence, time_taken_sec)
            VALUES (?, 'quiz', ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id, pending["question_id"], pending["concept_id"],
            query, pending["correct_answer"], 1 if is_correct else 0, 3, 10
        ))
        if not is_correct:
            conn.execute("""
                INSERT INTO revision_queue_items (question_id, concept_id, interval_days, due_at, lapses)
                VALUES (?, ?, 1, datetime('now', '+1 day'), 1)
                ON CONFLICT(question_id) DO UPDATE SET interval_days = 1, due_at = datetime('now', '+1 day'), lapses = lapses + 1
            """, (pending["question_id"], pending["concept_id"]))
        else:
            row = conn.execute("SELECT interval_days FROM revision_queue_items WHERE question_id = ?", (pending["question_id"],)).fetchone()
            if row:
                curr_interval = row[0]
                next_interval = {1: 3, 3: 7, 7: 14}.get(curr_interval, 14)
                if curr_interval >= 14:
                    conn.execute("DELETE FROM revision_queue_items WHERE question_id = ?", (pending["question_id"],))
                else:
                    conn.execute("UPDATE revision_queue_items SET interval_days = ?, due_at = datetime('now', '+' || ? || ' days') WHERE question_id = ?", (next_interval, next_interval, pending["question_id"]))
        conn.commit()
    except Exception as e:
        logger.error(f"Failed to record quiz grade: {e}")
    finally:
        conn.close()
        
    reply = "✅ **Correct!**\n\n" if is_correct else f"❌ **Incorrect.** The correct answer was **{pending['correct_answer']}**.\n\n"
    reply += f"**Explanation:**\n{pending.get('solution')}"
    
    state["reply"] = reply
    state["citations"] = pending.get("citations", [])
    return state

def pyq_node(state: ChatState) -> ChatState:
    """Fetches and formats a past year GATE question."""
    query = state.get("query", "")
    from knowledge.pyq_repository import get_repository
    repo = get_repository()
    
    matched_id = None
    if state.get("context") and len(state["context"]) == 1:
        matched_id = state["context"][0]["metadata"].get("source")
        
    matched = None
    if matched_id:
        matched = repo.get(matched_id)
    else:
        matched = find_matching_pyq(query, repo)
        
    if matched:
        reply = format_pyq_fallback(matched)
        citations = [matched.get("id", "Unknown")]
    else:
        items = repo.filter(q=query)
        if items:
            pyq = items[0]
            reply = format_pyq_fallback(pyq)
            citations = [pyq.get("id", "Unknown")]
        else:
            pyq = repo.random_question()
            if pyq:
                reply = f"Here is a past year question:\n{pyq.get('question_text')}\n\nOptions:\n"
                for k, v in (pyq.get("options") or {}).items():
                    reply += f"{k}) {v}\n"
                reply += f"\nCorrect answer: {pyq.get('answer')}\nExplanation: {pyq.get('solution')}"
                citations = [pyq.get("id")]
            else:
                reply = "No PYQs found matching the query."
                citations = []
                
    state["reply"] = reply
    state["citations"] = citations
    return state

# ---------------------------------------------------------------------------
# Compile the Graph workflow
# ---------------------------------------------------------------------------
def get_agent():
    workflow = StateGraph(ChatState)
    workflow.add_node("Router", router_node)
    workflow.add_node("Retrieve", retrieve_node)
    workflow.add_node("Explainer", explainer_node)
    workflow.add_node("Quiz", quiz_node)
    workflow.add_node("PYQ", pyq_node)
    
    workflow.add_node("QuizGrade", quiz_grade_node)
    
    workflow.set_entry_point("Router")
    
    def route_decision(state: ChatState) -> str:
        return state.get("next_node", "Retrieve")
        
    workflow.add_conditional_edges(
        "Router",
        route_decision,
        {
            "Retrieve": "Retrieve",
            "Quiz": "Quiz",
            "QuizGrade": "QuizGrade",
            "PYQ": "PYQ"
        }
    )
    
    workflow.add_edge("Retrieve", "Explainer")
    workflow.add_edge("Explainer", END)
    workflow.add_edge("Quiz", END)
    workflow.add_edge("QuizGrade", END)
    workflow.add_edge("PYQ", END)
    
    return workflow.compile()

agent = get_agent()
