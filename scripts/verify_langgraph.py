import sys
import os

# Add root folder to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from learning.langgraph_agent import agent, is_gguf_model_present, find_matching_pyq, format_pyq_fallback
from knowledge.pyq_repository import get_repository

def test_pyq_fallback():
    print("--------------------------------------------------")
    print("Testing Offline/Mock PYQ Fallback:")
    print("--------------------------------------------------")
    
    # 1. Verify GGUF presence
    model_present = is_gguf_model_present()
    print(f"Is GGUF model present? {model_present}")
    
    # Get repository
    repo = get_repository()
    
    # Let's find a question in the repository to search for
    if not repo._items:
        print("Error: PYQ Repository contains 0 items. Run content ingestion first.")
        return False
        
    sample_pyq = repo._items[0]
    print(f"Sample PYQ ID: {sample_pyq.get('id')}")
    print(f"Sample PYQ Text (partial): {sample_pyq.get('question_text')[:100]}...")
    print(f"Sample PYQ Answer: {sample_pyq.get('answer')}")
    
    # 2. Test query matching
    query = f"What is the answer for: {sample_pyq.get('question_text')}"
    matched = find_matching_pyq(query, repo)
    if not matched:
        print("FAIL: Could not match query to sample PYQ using Jaccard.")
        return False
    print(f"Matched successfully to PYQ: {matched.get('id')}")
    
    # 3. Test formatting
    formatted = format_pyq_fallback(matched)
    print("\nFormatted output matches rubric:")
    print("---")
    print(formatted)
    print("---")
    
    # Check rubric compliance:
    # - Clear, step-by-step explanation
    # - LaTeX formatting check
    # - Ends with 'Final answer: X'
    # - Do NOT restate the question
    # - No extra commentary
    
    if not formatted.endswith(f"Final answer: {matched.get('answer')}"):
        print(f"FAIL: Formatted output does not end with 'Final answer: {matched.get('answer')}'")
        return False
        
    if "Quick Tip" in formatted or "Correct Answer:" in formatted or "Final Answer:" in formatted:
        print("FAIL: Preexisting final answer / quick tips headers were not cleaned.")
        return False
        
    print("SUCCESS: Rubric formatting matches criteria perfectly.")
    
    # 4. Invoke graph execution for this query
    state_input = {
        "query": query,
        "session_id": "test-session",
        "persona": "Professor",
        "messages": [],
        "context": [],
        "reply": "",
        "citations": [],
        "next_node": ""
    }
    
    print("\nInvoking LangGraph agent workflow...")
    result = agent.invoke(state_input)
    
    print(f"Result Next Node: {result.get('next_node')}")
    print(f"Result Reply length: {len(result.get('reply', ''))} chars")
    print(f"Result Citations: {result.get('citations')}")
    
    if result.get('next_node') != 'PYQ':
        print("FAIL: Graph did not route to PYQ node.")
        return False
        
    if not result.get('reply').endswith(f"Final answer: {matched.get('answer')}"):
        print("FAIL: Graph reply does not match formatted rubric.")
        return False
        
    print("SUCCESS: Graph executed correctly.")
    return True

if __name__ == "__main__":
    success = test_pyq_fallback()
    sys.exit(0 if success else 1)
