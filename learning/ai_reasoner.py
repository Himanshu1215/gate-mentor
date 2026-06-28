import os
import logging
from typing import List, Dict

# NOTE: The following dependencies need to be installed via requirements.txt
try:
    from langchain_groq import ChatGroq
    from langchain.prompts import ChatPromptTemplate
    from langchain.schema import SystemMessage, HumanMessage
    HAS_LANGCHAIN = True
except ImportError:
    logging.warning("LangChain dependencies not installed. Run: pip install -r requirements.txt")
    HAS_LANGCHAIN = False

logger = logging.getLogger(__name__)

class AIReasoningEngine:
    """
    LLM-based component responsible for explanations, summarizations, and generating questions.
    Operates independently of deterministic state logic.
    """
    def __init__(self, api_key: str = None):
        # Fallback to env var if not passed
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "mock_key")
        self.llm = None
        
        if HAS_LANGCHAIN:
            try:
                self.llm = ChatGroq(
                    temperature=0.2, 
                    model_name="llama-3.1-70b-versatile",
                    groq_api_key=self.api_key
                )
            except Exception as e:
                logger.error(f"Failed to initialize ChatGroq: {e}")

    def generate_explanation(self, query: str, context_chunks: List[Dict[str, str]], persona: str = "Professor") -> str:
        """Generates a grounded explanation based entirely on provided context."""
        
        system_prompt = f"""You are a GATE DA AI Mentor adopting the '{persona}' persona.
        Your goal is to answer the user's question using ONLY the provided context.
        Always cite the source metadata at the end of your explanation.
        If the context does not contain the answer, explicitly state that you cannot answer based on trusted sources.
        """
        
        # Format the context
        context_str = "\n---\n".join([f"Source: {chunk['metadata'].get('source')}\nContent: {chunk['content']}" for chunk in context_chunks])
        
        human_prompt = f"Context:\n{context_str}\n\nQuestion: {query}"
        
        if self.llm:
            try:
                messages = [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=human_prompt)
                ]
                response = self.llm.invoke(messages)
                return response.content
            except Exception as e:
                logger.error(f"LLM Generation failed: {e}")
                return "Error generating response from LLM."
        
        # Mock response for testing without API keys
        return f"[Mock Response for '{query}'] Based on the retrieved context, this is a mock explanation. \n\nCitations: [Mock Source]"

    def generate_quiz_question(self, concept_id: str, context_chunks: List[Dict[str, str]]) -> Dict:
        """Generates a multiple choice question based on the context."""
        # For Milestone 1, returns a mocked static dictionary
        return {
            "concept_id": concept_id,
            "question": "What does Naive Bayes assume about features?",
            "options": ["A) They are dependent", "B) They are conditionally independent", "C) They are identical", "D) None of the above"],
            "answer": "B"
        }

if __name__ == "__main__":
    reasoner = AIReasoningEngine()
    print(reasoner.generate_explanation("What is Naive Bayes?", []))
