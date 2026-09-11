#!/usr/bin/env python3
"""Run eval/golden.yaml against the chat webhook and score the results.

Scores three things per CLAUDE.md/PLAN.md:
  - retrieval hit rate  (was the expected source in the top-k?)
  - faithfulness        (LLM judge: is the answer supported by retrieved chunks only?)
  - refusal accuracy    (did it refuse exactly the questions it should have?)

Writes a timestamped JSON + markdown report to eval/results/.

Status: scaffold only (Milestone 0). Real implementation lands in Milestone 3,
after eval/golden.yaml has real questions and Milestone 2's chat webhook exists.

Usage:
    python scripts/eval.py

Requires (from .env): the chat webhook to be reachable, plus OPENAI_API_KEY for
the faithfulness judge.
"""
import argparse
import os
import sys


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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--golden", default="eval/golden.yaml", help="Path to the golden question set")
    parser.add_argument("--out-dir", default="eval/results", help="Where to write the report")
    parser.parse_args()

    require_env("OPENAI_API_KEY")
    sys.exit("eval is not implemented yet — arrives in Milestone 3, after the chat webhook (M2) exists.")


if __name__ == "__main__":
    main()
