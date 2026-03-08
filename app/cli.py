"""Searchmark CLI — get folder recommendations for bookmarks."""

import asyncio
from pathlib import Path
from typing import Annotated

import typer
from dotenv import load_dotenv
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel

from app.main import fetch_and_analyze_url, get_folder_recommendation
from app.parsers import folders_to_json, parse_bookmarks_file
from app.schemas.analyze import RecommendationResponse

load_dotenv(".envs/.local/.fastapi")

app = typer.Typer(name="searchmark", no_args_is_help=True)
console = Console(stderr=True)
stdout = Console()


def _format_recommendation(rec: RecommendationResponse) -> list[str]:
    lines = [
        f"[bold]Title:[/bold] {rec.title}",
        f"[bold]Summary:[/bold] {rec.summary}",
        f"[bold]Folder:[/bold] [green]{rec.recommended_folder}[/green]",
    ]
    if rec.new_folder_name:
        lines.append(f"[bold]New folder:[/bold] [yellow]{rec.new_folder_name}[/yellow]")
    lines.append(f"[bold]Reasoning:[/bold] {rec.reasoning}")
    return lines


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

    stdout.print(Panel("\n".join(_format_recommendation(recommendation)), title="Recommendation"))


@app.command()
def compare(
    url: Annotated[str, typer.Argument(help="URL to get folder recommendations for")],
    bookmarks: Annotated[
        Path, typer.Option("--bookmarks", "-b", help="Bookmarks file (JSON or HTML)", exists=True)
    ] = Path("fixtures/bookmarks.json"),
) -> None:
    """Compare existing-folder vs new-folder recommendations (single URL analysis)."""
    asyncio.run(_compare(url, bookmarks))


async def _compare(url: str, bookmarks: Path) -> None:
    folders = parse_bookmarks_file(bookmarks)
    folders_json = folders_to_json(folders)

    console.print(f"[dim]Analyzing {url}...[/dim]")
    analysis = await fetch_and_analyze_url(url)

    console.print("[dim]Getting both recommendations...[/dim]")
    existing, new = await asyncio.gather(
        get_folder_recommendation(analysis, folders_json, create_new_folder=False),
        get_folder_recommendation(analysis, folders_json, create_new_folder=True),
    )

    stdout.print(
        Columns(
            [
                Panel("\n".join(_format_recommendation(existing)), title="Existing folder"),
                Panel("\n".join(_format_recommendation(new)), title="New folder"),
            ],
            equal=True,
        )
    )
