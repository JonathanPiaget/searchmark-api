"""Evaluate /recommend folder choice against the user's own Firefox bookmarks.

Usage: uv run python scripts/eval_recommend.py fixtures/bookmarks.json --sample 25 --seed 1
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

from app.main import fetch_and_analyze_url, get_folder_recommendation
from app.parsers import firefox_leaves, folders_to_json, parse_bookmarks_file

load_dotenv(".envs/.local/.fastapi")


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
    rec = await get_folder_recommendation(analysis, folders_json)
    row.update(got=rec.recommended_folder, latency_ms=round((time.perf_counter() - start) * 1000))
    row["status"] = verdict(expected, rec.recommended_folder)
    return row


async def run(export: Path, sample: int, seed: int | None, out: Path) -> None:
    folders_json = folders_to_json(parse_bookmarks_file(export))
    picked = random.Random(seed).sample(firefox_leaves(export), sample)  # noqa: S311 - sampling, not crypto
    rows = []
    with out.open("w", encoding="utf-8") as f:
        for i, (url, expected) in enumerate(picked, 1):
            typer.echo(f"[{i}/{sample}] {url}", err=True)
            row = await evaluate_one(url, expected, folders_json)
            rows.append(row)
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    counts = {s: sum(r["status"] == s for r in rows) for s in ("exact", "related", "miss", "skipped")}
    latencies = [r["latency_ms"] for r in rows if r["latency_ms"] is not None]
    typer.echo(f"\n{counts}  median step-2 latency: {statistics.median(latencies) if latencies else 0:.0f} ms")
    typer.echo("\nMisses:")
    for r in rows:
        if r["status"] == "miss":
            typer.echo(f"  {r['url']}\n    expected: {r['expected']}\n    got:      {r['got']}")


def main(
    export: Annotated[Path, typer.Argument(help="Firefox JSON bookmarks export", exists=True)],
    sample: Annotated[int, typer.Option(help="Number of bookmarks to evaluate")] = 25,
    seed: Annotated[int | None, typer.Option(help="Random seed for reproducible sampling")] = None,
    out: Annotated[Path, typer.Option(help="JSONL output file")] = Path("fixtures/eval/recommend.jsonl"),
) -> None:
    asyncio.run(run(export, sample, seed, out))


if __name__ == "__main__":
    typer.run(main)
