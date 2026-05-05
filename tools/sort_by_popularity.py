"""Reorder the GAMES list in app.py by play count.

Reads play counts from a running server (default http://127.0.0.1:5000)
or from a local JSON file, then rewrites app.py with the most-played
games listed first. Games with no recorded plays sort to the end in
their original order.

Usage:
    # default: query the local dev server
    python tools/sort_by_popularity.py

    # query the live deployment
    python tools/sort_by_popularity.py --url https://gamegalaxy.onrender.com

    # use a local file (e.g. play_counts.json copied from prod)
    python tools/sort_by_popularity.py --file play_counts.json

    # see the proposed order without writing app.py
    python tools/sort_by_popularity.py --dry-run

After running, review `git diff app.py`, commit, and push.
"""

import argparse
import ast
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_PY = ROOT / "app.py"


def fetch_counts_from_url(base_url: str) -> dict:
    url = base_url.rstrip("/") + "/api/stats"
    print(f"Fetching {url}", file=sys.stderr)
    req = urllib.request.Request(url, headers={"User-Agent": "gg-popularity-sort/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def load_counts_from_file(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def parse_games(source: str):
    """Locate the GAMES = [...] assignment in app.py and return:
        (games_list, start_offset, end_offset)
    `start_offset` and `end_offset` are byte indices that span the entire
    `GAMES = [...]` assignment (so the caller can splice in a replacement).
    """
    tree = ast.parse(source)
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        if node.targets[0].id != "GAMES":
            continue
        # Convert the literal list of dicts to Python objects
        games = ast.literal_eval(node.value)
        # Find byte offsets of the assignment's start / end lines
        lines = source.splitlines(keepends=True)
        start_line = node.lineno - 1
        end_line = node.end_lineno  # already 1-based inclusive; slicing uses it as exclusive
        start_offset = sum(len(l) for l in lines[:start_line])
        end_offset   = sum(len(l) for l in lines[:end_line])
        return games, start_offset, end_offset
    raise RuntimeError("GAMES assignment not found in app.py")


# Mirror the original style: a 4-space-indented dict per game with these
# keys in this order. external_url (optional) is appended only if present.
KEY_ORDER = ["slug", "title", "category", "blurb", "color", "external_url"]


def render_games(games):
    out = ["GAMES = ["]
    for g in games:
        out.append("    {")
        for key in KEY_ORDER:
            if key not in g:
                continue
            value = g[key]
            out.append(f'        "{key}": {render_value(value)},')
        out.append("    },")
    out.append("]")
    return "\n".join(out)


def render_value(v):
    if isinstance(v, str):
        # Use double quotes; escape any double quotes inside.
        return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return repr(v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:5000",
                    help="Base URL of a running Game Galaxy instance to fetch /api/stats from.")
    ap.add_argument("--file", type=Path,
                    help="Read counts from a local JSON file instead of HTTP.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print the proposed order, don't write app.py.")
    args = ap.parse_args()

    if args.file:
        counts = load_counts_from_file(args.file)
    else:
        try:
            counts = fetch_counts_from_url(args.url)
        except urllib.error.URLError as e:
            print(f"Couldn't reach {args.url}: {e}", file=sys.stderr)
            print("Hint: pass --url <prod-url> or --file <path>.", file=sys.stderr)
            return 2

    if not counts:
        print("No play counts recorded yet — nothing to sort.", file=sys.stderr)
        return 1

    source = APP_PY.read_text(encoding="utf-8")
    games, start, end = parse_games(source)

    # Stable sort: more plays first, ties keep original order.
    indexed = list(enumerate(games))
    indexed.sort(key=lambda pair: (-counts.get(pair[1]["slug"], 0), pair[0]))
    sorted_games = [g for _, g in indexed]

    print(f"{'#':>2}  {'plays':>5}  slug")
    for i, g in enumerate(sorted_games, 1):
        plays = counts.get(g["slug"], 0)
        print(f"{i:>2}  {plays:>5}  {g['slug']}")

    if args.dry_run:
        print("\n(dry run — app.py not modified)")
        return 0

    new_block = render_games(sorted_games)
    new_source = source[:start] + new_block + source[end:]
    if new_source == source:
        print("\nOrder already matches popularity — no changes.")
        return 0
    APP_PY.write_text(new_source, encoding="utf-8")
    print(f"\nRewrote {APP_PY.relative_to(ROOT)}. Review with `git diff app.py`, then commit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
