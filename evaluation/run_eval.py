import json
import sys
from pathlib import Path
from typing import Any, Dict, List
from app.agent.orchestrator import AgentOrchestrator
from evaluation.evaluators import CaseEvaluator

def run_evaluation(eval_file: str = "evaluation/visible-cases.json", output_json: str = "evaluation/eval_results.json") -> Dict[str, Any]:
    eval_path = Path(eval_file)
    if not eval_path.exists():
        print(f"Error: Evaluation file not found at {eval_path}")
        sys.exit(1)

    with open(eval_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    cases: List[Dict[str, Any]] = data.get("cases", [])
    agent = AgentOrchestrator()

    total_cases = len(cases)
    passed_cases = 0
    failed_cases = 0
    case_results: List[Dict[str, Any]] = []

    print("\n" + "=" * 65)
    print("ASTER & ROW SUPPORT AGENT — EVALUATION RUNNER")
    print("=" * 65 + "\n")

    for case in cases:
        case_id = case.get("id", "unknown")
        category = case.get("category", "general")
        messages = case.get("messages", [])
        expect_spec = case.get("expect", {})

        session_id = f"eval_{case_id}"
        last_response = None

        # Execute conversation turns sequentially in the case session
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                last_response = agent.process_query(content, session_id=session_id)

        if not last_response:
            passed = False
            failures = ["No user messages in evaluation case"]
        else:
            passed, failures = CaseEvaluator.evaluate_case(last_response, expect_spec)

        if passed:
            passed_cases += 1
            status_str = "[PASS]"
        else:
            failed_cases += 1
            status_str = "[FAIL]"

        res_dict = {
            "id": case_id,
            "category": category,
            "passed": passed,
            "failures": failures,
            "answer": last_response.answer if last_response else "",
            "sources": last_response.sources if last_response else [],
            "handoff": last_response.handoff if last_response else False,
            "tool_used": last_response.tool_used if last_response else None
        }
        case_results.append(res_dict)

        print(f"{status_str} {case_id:<35} Category: {category}")
        if not passed:
            for fail_msg in failures:
                print(f"       Reason: {fail_msg}")
            print(f"       Answer: {last_response.answer if last_response else ''}\n")

    pass_rate = (passed_cases / total_cases * 100) if total_cases > 0 else 0.0

    print("\n" + "=" * 65)
    print("EVALUATION SUMMARY")
    print("=" * 65)
    print(f"Total Cases : {total_cases}")
    print(f"Passed      : {passed_cases}")
    print(f"Failed      : {failed_cases}")
    print(f"Pass Rate   : {pass_rate:.1f}%\n")

    # Save machine-readable JSON result
    summary_data = {
        "total": total_cases,
        "passed": passed_cases,
        "failed": failed_cases,
        "pass_rate": pass_rate,
        "case_results": case_results
    }
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)

    return summary_data

def main():
    run_evaluation()

if __name__ == "__main__":
    main()
