"""Searchmark CLI — get folder recommendations for bookmarks."""

import asyncio
from pathlib import Path
from typing import Annotated

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

from app.main import fetch_and_analyze_url, get_folder_recommendation
from app.testing.parsers import folders_to_json, parse_bookmarks_file

load_dotenv(".envs/.local/.fastapi")

app = typer.Typer(name="searchmark", no_args_is_help=True)
console = Console(stderr=True)


@app.command()
def recommend(
    url: Annotated[str, typer.Argument(help="URL to get a folder recommendation for")],
    bookmarks: Annotated[
        Path, typer.Option("--bookmarks", "-b", help="Bookmarks file (JSON or HTML)", exists=True)
    ] = Path("fixtures/bookmarks.json"),
    new_folder: Annotated[bool, typer.Option("--new-folder", "-n", help="Suggest creating a new folder")] = False,
) -> None:
    asyncio.run(_recommend(url, bookmarks, new_folder))


async def _recommend(url: str, bookmarks: Path, new_folder: bool) -> None:
    folders = parse_bookmarks_file(bookmarks)

    console.print(f"[dim]Analyzing {url}...[/dim]")
    analysis = await fetch_and_analyze_url(url)

    console.print("[dim]Getting recommendation...[/dim]")
    recommendation = await get_folder_recommendation(analysis, folders_to_json(folders), new_folder)

    lines = [
        f"[bold]Title:[/bold] {recommendation.title}",
        f"[bold]Summary:[/bold] {recommendation.summary}",
        f"[bold]Folder:[/bold] [green]{recommendation.recommended_folder}[/green]",
    ]
    if recommendation.new_folder_name:
        lines.append(f"[bold]New folder:[/bold] [yellow]{recommendation.new_folder_name}[/yellow]")
    lines.append(f"[bold]Reasoning:[/bold] {recommendation.reasoning}")

    Console().print(Panel("\n".join(lines), title="Recommendation"))
