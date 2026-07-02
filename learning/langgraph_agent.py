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
def router_node(state: ChatState) -> ChatState:
    """Identifies the user's intent and updates the next node state."""
    query = state.get("query", "")
    
    # 1. GGUF Model absence check for offline/mock fallback
    if not is_gguf_model_present():
        from knowledge.pyq_repository import get_repository
        repo = get_repository()
        matched = find_matching_pyq(query, repo)
        if matched:
            state["next_node"] = "PYQ"
            state["context"] = [{
                "content": matched.get("question_text", ""),
                "metadata": {"source": matched.get("id", "Unknown")}
            }]
            return state

    # 2. Intent-based routing
    query_lower = query.lower()
    if "quiz" in query_lower or "test" in query_lower:
        state["next_node"] = "Quiz"
    elif "pyq" in query_lower or "previous year" in query_lower or "gate question" in query_lower:
        state["next_node"] = "PYQ"
    else:
        state["next_node"] = "Retrieve"
        
    return state

def retrieve_node(state: ChatState) -> ChatState:
    """Retrieves top relevant knowledge chunks from ChromaDB."""
    query = state.get("query", "")
    from knowledge.ingestor import KnowledgeIngestor
    
    retriever = KnowledgeIngestor()
    context_chunks = retriever.query(query, top_k=5)
    
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
    
    from learning.ai_reasoner import AIReasoningEngine
    reasoner = AIReasoningEngine()
    
    reply = reasoner.generate_explanation(query, context_chunks, persona=persona)
    citations = list({chunk["metadata"].get("source", "Unknown") for chunk in context_chunks})
    
    state["reply"] = reply
    state["citations"] = citations
    return state

def quiz_node(state: ChatState) -> ChatState:
    """Generates or fetches quiz questions for a concept."""
    query = state.get("query", "")
    
    from knowledge.pyq_repository import get_repository
    repo = get_repository()
    
    # Extract concept ID if present
    concept_id = "ML_NB_001"
    match = re.search(r'[A-Z]{2,4}_[A-Z0-9]+_\d+', query)
    if match:
        concept_id = match.group(0)
        
    if is_gguf_model_present():
        from learning.ai_reasoner import AIReasoningEngine
        reasoner = AIReasoningEngine()
        from knowledge.ingestor import KnowledgeIngestor
        retriever = KnowledgeIngestor()
        context_chunks = retriever.query(query, top_k=3)
        try:
            quiz_data = reasoner.generate_quiz_question(concept_id, context_chunks)
            reply = f"Here is a quiz question on {concept_id}:\n\n{quiz_data.get('question')}\n\nOptions:\n"
            for opt in quiz_data.get("options", []):
                reply += f"{opt}\n"
            reply += f"\nCorrect answer: {quiz_data.get('answer')}\nExplanation: {quiz_data.get('explanation')}"
            citations = list({chunk["metadata"].get("source", "System") for chunk in context_chunks})
        except Exception:
            q = repo.random_question(concept_id=concept_id) or repo.random_question()
            reply = f"Quiz Question:\n{q.get('question_text')}\n\nOptions:\n"
            for k, v in (q.get("options") or {}).items():
                reply += f"{k}) {v}\n"
            reply += f"\nCorrect answer: {q.get('answer')}\nExplanation: {q.get('solution')}"
            citations = [q.get("id")]
    else:
        q = repo.random_question(concept_id=concept_id) or repo.random_question()
        if q:
            reply = f"Quiz Question:\n{q.get('question_text')}\n\nOptions:\n"
            for k, v in (q.get("options") or {}).items():
                reply += f"{k}) {v}\n"
            reply += f"\nCorrect answer: {q.get('answer')}\nExplanation: {q.get('solution')}"
            citations = [q.get("id")]
        else:
            reply = "No quiz questions available."
            citations = []
            
    state["reply"] = reply
    state["citations"] = citations
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
    
    workflow.set_entry_point("Router")
    
    def route_decision(state: ChatState) -> str:
        return state.get("next_node", "Retrieve")
        
    workflow.add_conditional_edges(
        "Router",
        route_decision,
        {
            "Retrieve": "Retrieve",
            "Quiz": "Quiz",
            "PYQ": "PYQ"
        }
    )
    
    workflow.add_edge("Retrieve", "Explainer")
    workflow.add_edge("Explainer", END)
    workflow.add_edge("Quiz", END)
    workflow.add_edge("PYQ", END)
    
    return workflow.compile()

agent = get_agent()
