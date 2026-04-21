#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["anthropic", "pyyaml"]
# ///
"""
Synthesize insights.yaml from data/ files using Claude API.
Reads all .txt files in data/, calls Claude, writes _bazaar/examples/insights.yaml.

Usage:
    python scripts/synthesize_insights.py --data-dir data/ --out _bazaar/examples/insights.yaml
"""

import argparse
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

import anthropic
import yaml


SYSTEM_PROMPT = """\
You are synthesizing a developer profile from raw activity reports and persona analyses.
Output ONLY valid YAML — no markdown fences, no explanation, no preamble.
The YAML must conform exactly to this schema:

generated_at: <ISO 8601 datetime>
summary: <2-3 sentence professional summary, present tense>
tagline: <1 sentence, punchy, systems-focused>
role: <job title>
focus_areas:
  - <area 1>
  - <area 2>
active_projects:
  - name: <project name>
    description: <one line>
    url: <github url or omit>
stats:
  sessions_per_day: <string like "~15">
  total_sessions: <integer>
  commits: <integer>
  lines_added: <integer>
  lines_removed: <integer>
  peak_day: <string describing highest-throughput day>
  spec_to_ship_best: <string describing fastest ship>
workflow_style: <1-2 sentences describing orchestration style>
what_you_work_on:
  - name: <area name>
    sessions: <integer or omit>
    description: <2-3 sentences>

Rules:
- active_projects: list the 6 most recently active repos only
- focus_areas: 4-6 items, concise noun phrases
- stats: extract from numbers in the source material; omit fields you cannot find
- what_you_work_on: top 4-5 areas by session count
- Do not invent data not present in the source material
- today's date is: """ + datetime.now(timezone.utc).strftime("%Y-%m-%d")


def load_data_files(data_dir: Path) -> str:
    parts = []
    for f in sorted(data_dir.glob("*.txt")):
        content = f.read_text(encoding="utf-8").strip()
        if content:
            parts.append(f"=== {f.name} ===\n{content}")
    return "\n\n".join(parts)


def synthesize(data_dir: Path, out_path: Path) -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    source = load_data_files(data_dir)
    if not source:
        print("ERROR: no .txt files found in data/", file=sys.stderr)
        sys.exit(1)

    print(f"synthesizing from {len(source)} chars of source data...", file=sys.stderr)

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"Synthesize the profile YAML from these reports:\n\n{source}",
            }
        ],
    )

    raw = message.content[0].text.strip()

    # Validate it parses as YAML before writing
    try:
        parsed = yaml.safe_load(raw)
    except yaml.YAMLError as e:
        print(f"ERROR: Claude returned invalid YAML: {e}", file=sys.stderr)
        print("--- raw output ---", file=sys.stderr)
        print(raw, file=sys.stderr)
        sys.exit(1)

    if not isinstance(parsed, dict):
        print("ERROR: Claude returned non-dict YAML", file=sys.stderr)
        sys.exit(1)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(raw + "\n", encoding="utf-8")
    print(f"wrote {out_path}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=Path("_bazaar/examples/insights.yaml"))
    args = parser.parse_args()
    synthesize(args.data_dir, args.out)


if __name__ == "__main__":
    main()
