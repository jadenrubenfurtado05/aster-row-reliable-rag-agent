from app.agent.orchestrator import AgentOrchestrator


def print_response(response):
    print("\nAgent:")
    print(response.answer)

    if response.sources:
        print("\nSources:")
        for source in response.sources:
            print(f"  - {source}")

    print(f"\nHandoff: {'Yes' if response.handoff else 'No'}")

    if response.handoff_reason:
        print(f"Reason: {response.handoff_reason}")

    if response.tool_used:
        print(f"Tool used: {response.tool_used}")

    print()


def main():
    print("=" * 60)
    print("Aster & Row Support Agent")
    print("Offline / Mock LLM Mode")
    print("=" * 60)
    print("Type 'exit' or 'quit' to end the session.\n")

    agent = AgentOrchestrator()

    session_id = "demo-session"

    while True:
        try:
            user_query = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

        if not user_query:
            continue

        if user_query.lower() in {"exit", "quit"}:
            print("Goodbye!")
            break

        try:
            response = agent.process_query(
                user_query,
                session_id=session_id
            )
            print_response(response)
        except Exception as exc:
            print(f"\nError: {exc}\n")


if __name__ == "__main__":
    main()