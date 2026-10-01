#!/usr/bin/env python3
"""Run eval/golden.yaml against the chat webhook and score the results.

Scores three things per CLAUDE.md/PLAN.md:
  - retrieval hit rate  (was the expected source in the top-k, for answerable questions)
  - faithfulness        (LLM judge: is the answer supported by ITS OWN retrieved
                          chunks, for every question the system actually answered)
  - refusal accuracy    (did it refuse exactly the questions marked should_refuse?)

The judge is the same self-hosted CHAT_MODEL the system answers with (zero
additional cost, consistent with the rest of this project) -- a model judging its
own output has a known self-favoring bias; treat faithfulness here as a useful
signal to track over time (M4 tuning), not an absolute, audited number. Worth a
second, independent judge model later if this ever needs to survive real scrutiny.

Writes a timestamped JSON + markdown report to eval/results/.

Usage:
    python scripts/eval.py
    python scripts/eval.py --golden eval/golden.yaml --out-dir eval/results

Requires (from .env): N8N_PORT (to build the default chat webhook URL),
OLLAMA_BASE_URL, CHAT_MODEL (for the faithfulness judge).
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

try:
    import yaml
except ImportError:
    sys.exit(
        "Missing dependency: PyYAML. Install with:\n"
        "  python -m pip install -r scripts/requirements.txt"
    )


def load_dotenv_if_present(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


def require_env(*names: str) -> dict:
    load_dotenv_if_present()
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        sys.exit(
            f"Missing required environment variable(s): {', '.join(missing)}. "
            f"Copy .env.example to .env and fill them in."
        )
    return {n: os.environ[n] for n in names}


def post_json(url: str, body: dict, timeout: int) -> tuple:
    """Returns (status_code, parsed_json_or_none, raw_text, elapsed_seconds)."""
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            elapsed = time.monotonic() - start
            try:
                return resp.status, json.loads(raw), raw, elapsed
            except json.JSONDecodeError:
                return resp.status, None, raw, elapsed
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        elapsed = time.monotonic() - start
        try:
            return e.code, json.loads(raw), raw, elapsed
        except json.JSONDecodeError:
            return e.code, None, raw, elapsed
    except urllib.error.URLError as e:
        elapsed = time.monotonic() - start
        return None, None, f"Connection error: {e.reason}", elapsed
    except OSError as e:
        # A bare socket timeout (TimeoutError) isn't always wrapped in URLError --
        # confirmed the hard way: this crashed a 28-question run on question 12
        # instead of recording one failed row and continuing. Every question here
        # is a real, possibly-slow model generation; one slow outlier must not take
        # down the whole eval.
        elapsed = time.monotonic() - start
        return None, None, f"Request failed: {e}", elapsed


JUDGE_PROMPT_TEMPLATE = """You are grading whether an AI assistant's answer is faithful \
to the given source material.

Source material:
{sources}

Answer to grade:
{answer}

The answer is allowed to paraphrase, summarize, reorganize, or restate the source \
material in different words -- that is NOT a violation and must not be marked NO for \
that reason alone. Only respond NO if the answer asserts a specific fact, number, or \
claim that is not present in and not a reasonable restatement of the source material.

Given that standard, is the answer faithful to the source material? Respond with \
exactly one word: YES or NO."""
# Calibrated empirically (scripts/eval.py's earlier, stricter wording marked a
# textbook-faithful paraphrase as NO -- verified directly against Ollama with
# planted verbatim/paraphrase/unsupported/partially-unsupported test cases before
# trusting this version; see PLAN.md M3 for the numbers). A 3B local model judging
# its own family's output is still a known-noisy signal, not an audited one.


def judge_faithfulness(ollama_base_url: str, chat_model: str, answer: str, sources: list, timeout: int) -> str:
    """Returns 'yes', 'no', or 'unclear' (judge call failed or gave an unparseable reply)."""
    source_text = "\n\n".join(
        f"[{s.get('index')}] ({s.get('source_path')}, chunk {s.get('chunk_index')}):\n{s.get('content', '')}"
        for s in sources
    )
    prompt = JUDGE_PROMPT_TEMPLATE.format(sources=source_text, answer=answer)
    status, parsed, raw, _ = post_json(
        f"{ollama_base_url}/api/generate",
        {"model": chat_model, "prompt": prompt, "stream": False},
        timeout,
    )
    if status != 200 or not parsed or "response" not in parsed:
        return "unclear"
    verdict = parsed["response"].strip().upper()
    if verdict.startswith("YES"):
        return "yes"
    if verdict.startswith("NO"):
        return "no"
    return "unclear"


def run_eval(golden_path: str, chat_url: str, ollama_base_url: str, chat_model: str, timeout: int, on_progress=None) -> dict:
    with open(golden_path, "r", encoding="utf-8") as f:
        golden = yaml.safe_load(f) or {}
    questions = golden.get("questions", [])
    if not questions:
        sys.exit(f"No questions found in {golden_path} (expected a top-level 'questions' list).")

    results = []
    for i, q in enumerate(questions, 1):
        question_text = q["question"]
        expected_source = q.get("expected_source")
        should_refuse = bool(q.get("should_refuse"))

        print(f"[{i}/{len(questions)}] {question_text[:70]}...", file=sys.stderr)
        status, parsed, raw, elapsed = post_json(chat_url, {"question": question_text}, timeout)

        row = {
            "question": question_text,
            "expected_source": expected_source,
            "should_refuse": should_refuse,
            "http_status": status,
            "latency_seconds": round(elapsed, 2),
        }

        if status != 200 or not parsed:
            row.update({"error": raw[:500], "actual_refused": None, "retrieval_hit": None, "faithful": None})
            results.append(row)
            if on_progress:
                on_progress(results)
            continue

        answer = parsed.get("answer", "")
        sources = parsed.get("sources", [])
        actual_refused = len(sources) == 0
        row["answer"] = answer
        row["sources"] = [{"source_path": s.get("source_path"), "similarity": s.get("similarity")} for s in sources]
        row["actual_refused"] = actual_refused
        row["refusal_correct"] = actual_refused == should_refuse

        if not should_refuse:
            row["retrieval_hit"] = any(s.get("source_path") == expected_source for s in sources)
        else:
            row["retrieval_hit"] = None  # not applicable

        if not actual_refused:
            row["faithful"] = judge_faithfulness(ollama_base_url, chat_model, answer, sources, timeout)
        else:
            row["faithful"] = None  # not applicable -- nothing was answered to judge

        results.append(row)
        if on_progress:
            on_progress(results)

    return {"generated_at": datetime.now(timezone.utc).isoformat(), "questions": results}


def summarize(report: dict) -> dict:
    rows = report["questions"]
    answerable = [r for r in rows if r["should_refuse"] is False and r.get("retrieval_hit") is not None]
    refusal_rows = [r for r in rows if r.get("refusal_correct") is not None]
    faithful_rows = [r for r in rows if r.get("faithful") in ("yes", "no")]

    retrieval_hit_rate = (sum(1 for r in answerable if r["retrieval_hit"]) / len(answerable)) if answerable else None
    refusal_accuracy = (sum(1 for r in refusal_rows if r["refusal_correct"]) / len(refusal_rows)) if refusal_rows else None
    faithfulness = (sum(1 for r in faithful_rows if r["faithful"] == "yes") / len(faithful_rows)) if faithful_rows else None

    errors = sum(1 for r in rows if r.get("error"))

    return {
        "total_questions": len(rows),
        "errors": errors,
        "retrieval_hit_rate": retrieval_hit_rate,
        "retrieval_hit_rate_n": len(answerable),
        "refusal_accuracy": refusal_accuracy,
        "refusal_accuracy_n": len(refusal_rows),
        "faithfulness": faithfulness,
        "faithfulness_n": len(faithful_rows),
    }


def write_markdown(report: dict, summary: dict, out_path: str) -> None:
    def pct(x):
        return f"{x * 100:.1f}%" if x is not None else "n/a"

    incomplete_notice = "\n**INCOMPLETE -- run did not finish; these numbers cover only the questions reached so far.**\n" if not report.get("complete", True) else ""
    lines = [
        f"# Eval report -- {report['generated_at']}",
        incomplete_notice,
        "| Metric | Score | n |",
        "|---|---|---|",
        f"| Retrieval hit rate | {pct(summary['retrieval_hit_rate'])} | {summary['retrieval_hit_rate_n']} |",
        f"| Faithfulness | {pct(summary['faithfulness'])} | {summary['faithfulness_n']} |",
        f"| Refusal accuracy | {pct(summary['refusal_accuracy'])} | {summary['refusal_accuracy_n']} |",
        "",
        f"Total questions: {summary['total_questions']} ({summary['errors']} errored)",
        "",
        "## Per-question detail",
        "",
        "| # | Question | Expected refuse | Actual refuse | Retrieval hit | Faithful | Latency (s) |",
        "|---|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(report["questions"], 1):
        lines.append(
            f"| {i} | {r['question'][:60]} | {r['should_refuse']} | {r.get('actual_refused')} | "
            f"{r.get('retrieval_hit')} | {r.get('faithful')} | {r.get('latency_seconds')} |"
        )
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--golden", default="eval/golden.yaml", help="Path to the golden question set")
    parser.add_argument("--out-dir", default="eval/results", help="Where to write the report")
    parser.add_argument("--chat-url", default=None, help="Chat webhook URL (default: built from N8N_PORT)")
    # Must stay above the chat workflow's own "Call Chat Model" HTTP timeout (600s) --
    # otherwise eval.py gives up and reports a spurious error before n8n's own
    # timeout would have. (Both got raised together after CPU-only generation on
    # longer questions genuinely exceeded the previous 300s/420s pair -- see PLAN.md M3.)
    parser.add_argument("--timeout", type=int, default=650, help="Per-request timeout in seconds (default 650)")
    args = parser.parse_args()

    env = require_env("OLLAMA_BASE_URL", "CHAT_MODEL")
    load_dotenv_if_present()
    n8n_port = os.environ.get("N8N_PORT", "5678")
    chat_url = args.chat_url or f"http://localhost:{n8n_port}/webhook/chat"

    if not os.path.exists(args.golden):
        sys.exit(f"No such file: {args.golden}")

    os.makedirs(args.out_dir, exist_ok=True)

    # Each question is a real, possibly slow model generation (or two) -- a run
    # crashing (or being interrupted) on question 20 of 28 must not throw away the
    # first 19's results. Checkpointed after every question, to the same files the
    # final report lands in; a partial report from an interrupted run is clearly
    # marked incomplete rather than silently mistaken for a finished one.
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = os.path.join(args.out_dir, f"{timestamp}.json")
    md_path = os.path.join(args.out_dir, f"{timestamp}.md")

    def checkpoint(results_so_far):
        partial = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "questions": results_so_far,
            "complete": len(results_so_far) == total_questions,
        }
        partial["summary"] = summarize(partial)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(partial, f, indent=2)
        write_markdown(partial, partial["summary"], md_path)

    with open(args.golden, "r", encoding="utf-8") as f:
        total_questions = len(yaml.safe_load(f).get("questions", []))

    report = run_eval(
        args.golden, chat_url, env["OLLAMA_BASE_URL"], env["CHAT_MODEL"], args.timeout,
        on_progress=checkpoint,
    )
    report["complete"] = True
    summary = summarize(report)
    report["summary"] = summary

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    write_markdown(report, summary, md_path)

    print(f"\nRetrieval hit rate: {summary['retrieval_hit_rate']} (n={summary['retrieval_hit_rate_n']})")
    print(f"Faithfulness:       {summary['faithfulness']} (n={summary['faithfulness_n']})")
    print(f"Refusal accuracy:   {summary['refusal_accuracy']} (n={summary['refusal_accuracy_n']})")
    print(f"\nWrote {json_path}\nWrote {md_path}")


if __name__ == "__main__":
    main()
