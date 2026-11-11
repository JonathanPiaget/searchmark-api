"""Evaluate /recommend folder choice against the user's own Firefox bookmarks.

Usage:
  uv run python scripts/eval_recommend.py run fixtures/bookmarks.json --set fixtures/eval/golden.jsonl
  SEARCHMARK_MODEL=openai/gpt-4o uv run python scripts/eval_recommend.py run fixtures/bookmarks.json --set ...
  uv run python scripts/eval_recommend.py compare fixtures/eval/golden-*.jsonl
"""

import asyncio
import json
import random
import statistics
import time
from pathlib import Path
from typing import Annotated

import httpx
import typer
from dotenv import load_dotenv
from fastapi import HTTPException

from app.main import MODEL, fetch_and_analyze_url, get_folder_recommendation
from app.parsers import firefox_leaves, folders_to_json, parse_bookmarks_file

load_dotenv(".envs/.local/.fastapi")
app = typer.Typer(no_args_is_help=True)


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def verdict(expected: str, got: str) -> str:
    if expected == got:
        return "exact"
    parent = lambda p: p.rsplit("/", 1)[0]
    if got.startswith(expected + "/") or expected.startswith(got + "/") or parent(expected) == parent(got):
        return "related"
    return "miss"


async def evaluate_one(url: str, expected: str, folders_json: str) -> dict:
    row = {"url": url, "expected": expected, "got": None, "status": "skipped", "latency_ms": None}
    try:
        analysis = await fetch_and_analyze_url(url)
    except (httpx.HTTPError, HTTPException) as e:
        row["error"] = repr(e)[:200]  # repr: httpx timeouts have an empty str()
        return row
    start = time.perf_counter()
    try:
        rec = await get_folder_recommendation(analysis, folders_json)
    except Exception as e:
        row.update(status="miss", error=repr(e)[:200])
        return row
    row.update(got=rec.recommended_folder, latency_ms=round((time.perf_counter() - start) * 1000))
    row["status"] = verdict(expected, rec.recommended_folder)
    return row


async def run(export: Path, sample: int, seed: int | None, out: Path, fixed_set: Path | None) -> None:
    folders_json = folders_to_json(parse_bookmarks_file(export))
    if fixed_set:
        leaves = [(r["url"], r["expected"]) for r in read_jsonl(fixed_set)]
        sample = len(leaves)
    else:
        leaves = firefox_leaves(export)
        random.Random(seed).shuffle(leaves)  # noqa: S311 - sampling, not crypto
    rows: list[dict] = []
    scored = 0
    with out.open("w", encoding="utf-8") as f:
        for url, expected in leaves:  # keep drawing so skipped pages are replaced
            if scored >= sample:
                break
            typer.echo(f"[{scored + 1}/{sample}] {url}", err=True)
            row = await evaluate_one(url, expected, folders_json)
            scored += row["status"] != "skipped"
            rows.append(row)
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    counts = {s: sum(r["status"] == s for r in rows) for s in ("exact", "related", "miss", "skipped")}
    latencies = [r["latency_ms"] for r in rows if r["latency_ms"] is not None]
    typer.echo(f"\n{counts}  median step-2 latency: {statistics.median(latencies) if latencies else 0:.0f} ms")
    typer.echo("\nMisses:")
    for r in rows:
        if r["status"] == "miss":
            typer.echo(f"  {r['url']}\n    expected: {r['expected']}\n    got:      {r['got']}")


@app.command("run")
def run_cmd(
    export: Annotated[Path, typer.Argument(help="Firefox JSON bookmarks export", exists=True)],
    sample: Annotated[int, typer.Option(help="Number of scored bookmarks (skipped ones are replaced)")] = 25,
    seed: Annotated[int | None, typer.Option(help="Random seed for reproducible sampling")] = None,
    out: Annotated[Path | None, typer.Option(help="JSONL output (default: fixtures/eval/<set>-<model>.jsonl)")] = None,
    fixed_set: Annotated[
        Path | None, typer.Option("--set", help="JSONL of {url, expected}: evaluate exactly these instead of sampling")
    ] = None,
) -> None:
    """Evaluate the current model (override with SEARCHMARK_MODEL) and write one JSONL row per URL."""
    out = out or Path(f"fixtures/eval/{fixed_set.stem if fixed_set else 'recommend'}-{MODEL.rsplit('/', 1)[-1]}.jsonl")
    typer.echo(f"model: {MODEL}  ->  {out}", err=True)
    asyncio.run(run(export, sample, seed, out, fixed_set))


@app.command()
def compare(results: Annotated[list[Path], typer.Argument(help="Result JSONL files, one per model")]) -> None:
    """Side-by-side status per URL and totals for several result files."""
    runs = {p.stem: {r["url"]: r for r in read_jsonl(p)} for p in results}
    urls = sorted({u for rows in runs.values() for u in rows})
    width = max(len(n) for n in runs)
    for url in urls:
        cells = [f"{runs[n].get(url, {}).get('status', '-'):8}" for n in runs]
        typer.echo(f"{' '.join(cells)}  {url}")
    typer.echo("\n" + "  ".join(f"{s:8}" for s in ("exact", "related", "miss", "skipped", "median_ms")) + "  model")
    for name, rows in runs.items():
        counts = [sum(r["status"] == s for r in rows.values()) for s in ("exact", "related", "miss", "skipped")]
        lat = [r["latency_ms"] for r in rows.values() if r["latency_ms"] is not None]
        median = statistics.median(lat) if lat else 0
        typer.echo("  ".join(f"{c:<8}" for c in [*counts, round(median)]) + f"  {name:<{width}}")


if __name__ == "__main__":
    app()
