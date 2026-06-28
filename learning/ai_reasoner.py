import os
import logging
import json
from typing import List, Dict

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Local LLM via llama-cpp-python (CPU-only, GGUF quantized model)
# Model: microsoft/Phi-4-mini-instruct  (Q4_K_M GGUF, ~2.5 GB RAM)
# Download: scripts/download_models.py
# ---------------------------------------------------------------------------
try:
    from llama_cpp import Llama
    HAS_LLAMA_CPP = True
except ImportError:
    logger.warning("llama-cpp-python not installed. Run: pip install -r requirements.txt")
    HAS_LLAMA_CPP = False

# Model file location (downloaded by scripts/download_models.py)
MODEL_DIR  = os.path.join(os.path.dirname(__file__), "..", "models")
MODEL_FILE = os.path.join(MODEL_DIR, "phi-4-mini-instruct-q4_k_m.gguf")

class AIReasoningEngine:
    """
    Local LLM-based component for explanations, summaries, and quiz generation.
    Uses Phi-4-mini-instruct via llama-cpp-python for fully offline CPU inference.
    Falls back to structured mock responses if the model file is not yet downloaded.
    """

    def __init__(self):
        self.llm = None

        if HAS_LLAMA_CPP and os.path.exists(MODEL_FILE):
            try:
                logger.info(f"Loading local LLM from {MODEL_FILE} ...")
                self.llm = Llama(
                    model_path=MODEL_FILE,
                    n_ctx=4096,          # context window
                    n_threads=4,         # match 4 vCPUs
                    n_batch=512,         # tokens per batch
                    verbose=False,
                )
                logger.info("Local LLM loaded successfully.")
            except Exception as e:
                logger.error(f"Failed to load local LLM: {e}")
        else:
            if not os.path.exists(MODEL_FILE):
                logger.warning(
                    f"Model file not found at {MODEL_FILE}. "
                    "Run: python scripts/download_models.py  to download Phi-4-mini."
                )
            logger.warning("Running in MOCK mode — responses are simulated.")

    # ------------------------------------------------------------------
    # Internal helper: call the local LLM
    # ------------------------------------------------------------------
    def _call_llm(self, system_prompt: str, user_prompt: str, max_tokens: int = 512) -> str:
        """Sends a chat-formatted prompt to the local Phi-4-mini model."""
        # Phi-4 uses ChatML format
        prompt = (
            f"<|system|>\n{system_prompt}<|end|>\n"
            f"<|user|>\n{user_prompt}<|end|>\n"
            f"<|assistant|>\n"
        )
        output = self.llm(
            prompt,
            max_tokens=max_tokens,
            temperature=0.2,
            top_p=0.95,
            stop=["<|end|>", "<|user|>"],
            echo=False,
        )
        return output["choices"][0]["text"].strip()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def generate_explanation(
        self,
        query: str,
        context_chunks: List[Dict[str, str]],
        persona: str = "Professor",
    ) -> str:
        """
        Generates a grounded explanation based ONLY on the provided RAG context chunks.
        If no LLM is available, returns a structured mock response.
        """
        system_prompt = (
            f"You are a GATE DA AI Mentor with the persona of a '{persona}'. "
            "Answer the student's question using ONLY the provided context. "
            "Be concise, precise, and GATE-exam focused. "
            "Always cite the source at the end. "
            "If the context lacks the answer, say: 'I cannot find this in the trusted sources.'"
        )

        context_str = "\n---\n".join(
            [
                f"Source: {chunk['metadata'].get('source', 'Unknown')}\n"
                f"Content: {chunk['content']}"
                for chunk in context_chunks
            ]
        )
        user_prompt = f"Context:\n{context_str}\n\nQuestion: {query}"

        if self.llm:
            try:
                return self._call_llm(system_prompt, user_prompt, max_tokens=512)
            except Exception as e:
                logger.error(f"LLM generation failed: {e}")
                return "Error generating response from the local LLM."

        # ── Mock fallback ──────────────────────────────────────────────
        if context_chunks:
            snippet = context_chunks[0]["content"][:200]
            source  = context_chunks[0]["metadata"].get("source", "Unknown")
            return (
                f"[MOCK] Based on the retrieved context:\n\n"
                f"{snippet}...\n\n"
                f"[Citation: {source}]"
            )
        return (
            f"[MOCK] No context retrieved for query: '{query}'. "
            "Please ingest GATE content first."
        )

    def generate_quiz_question(
        self,
        concept_id: str,
        context_chunks: List[Dict[str, str]],
    ) -> Dict:
        """
        Generates a GATE-style MCQ for the given concept using retrieved context.
        Falls back to a concept-specific mock if the LLM is unavailable.
        """
        system_prompt = (
            "You are a GATE DA exam question generator. "
            "Using the provided context, generate ONE multiple-choice question "
            "in valid JSON. The JSON must have exactly these keys: "
            "'question' (string), 'options' (list of 4 strings like 'A) ...'), "
            "'answer' (single letter A/B/C/D), 'explanation' (string). "
            "Make the question GATE-level difficulty. Output ONLY the JSON object."
        )

        context_str = "\n---\n".join(
            [chunk["content"] for chunk in context_chunks]
        ) if context_chunks else f"Generate a question about concept: {concept_id}"

        user_prompt = (
            f"Concept ID: {concept_id}\n\n"
            f"Context:\n{context_str}\n\n"
            "Generate a GATE-style MCQ as JSON:"
        )

        if self.llm:
            try:
                raw = self._call_llm(system_prompt, user_prompt, max_tokens=300)
                # Extract JSON from model output
                start = raw.find("{")
                end   = raw.rfind("}") + 1
                if start != -1 and end > start:
                    return json.loads(raw[start:end])
            except Exception as e:
                logger.error(f"Quiz generation failed: {e}")

        # ── Concept-aware mock fallback ────────────────────────────────
        mock_questions = {
            "ML_RV_001": {
                "question": "A random variable X follows N(0,1). What is P(X > 0)?",
                "options": ["A) 0.25", "B) 0.5", "C) 0.75", "D) 1.0"],
                "answer": "B",
                "explanation": "By symmetry of normal distribution, P(X>0) = 0.5",
            },
            "LA_EIG_001": {
                "question": "If A is a 3×3 matrix with eigenvalues 1, 2, 3, what is det(A)?",
                "options": ["A) 1", "B) 3", "C) 6", "D) 9"],
                "answer": "C",
                "explanation": "det(A) = product of eigenvalues = 1×2×3 = 6",
            },
            "ML_NB_001": {
                "question": "What does Naive Bayes assume about features?",
                "options": [
                    "A) They are dependent",
                    "B) They are conditionally independent given the class",
                    "C) They are identical",
                    "D) They follow a uniform distribution",
                ],
                "answer": "B",
                "explanation": "Naive Bayes assumes conditional independence of features given class label.",
            },
        }

        # Return matching mock or generic fallback
        return mock_questions.get(
            concept_id,
            {
                "concept_id": concept_id,
                "question": f"Which of the following best describes '{concept_id}'?",
                "options": ["A) Option A", "B) Option B", "C) Option C", "D) Option D"],
                "answer": "A",
                "explanation": f"[Mock] Model not loaded. Run scripts/download_models.py.",
            },
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    engine = AIReasoningEngine()
    print(engine.generate_explanation("What is Bayes theorem?", []))
