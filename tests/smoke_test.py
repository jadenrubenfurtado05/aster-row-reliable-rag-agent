import json
from app.agent.orchestrator import AgentOrchestrator

def main():
    agent = AgentOrchestrator()

    test_queries = [
        "What is the standard return window?",
        "How long do TrailPlus members have to return an item?",
        "Where is my order ORD-1007?",
        "Cancel order ORD-1007.",
        "How do I clean the Breeze Tumbler?",
        "Do you ship to a country not listed in the knowledge base?",
        "Where is ord-1007?"
    ]

    for idx, q in enumerate(test_queries, 1):
        print(f"=== SMOKE TEST #{idx}: \"{q}\" ===")
        res = agent.process_query(q)
        meta = res.trace_metadata or {}
        print(f"Route / Tool Used: {res.tool_used}")
        print(f"RAG Used: {meta.get('use_rag')}")
        print(f"Order Lookup Used: {meta.get('use_order_tool')}")
        print(f"Final Answer: {res.answer}")
        print(f"Sources: {res.sources}")
        print(f"Handoff Status: {res.handoff}")
        if res.handoff_reason:
            print(f"Handoff Reason: {res.handoff_reason}")
        print("-" * 60 + "\n")

if __name__ == "__main__":
    main()
