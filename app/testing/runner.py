"""CLI runner for testing bookmark processing and model comparison.

Usage:
    # Test with a URL and bookmark file
    python -m app.testing.runner --url https://python.org --bookmarks bookmarks.html

    # Compare multiple models
    python -m app.testing.runner --url https://python.org --bookmarks bookmarks.json \
        --models openai/gpt-4o-mini openai/gpt-4o anthropic/claude-3-haiku-20240307

    # Output results to JSON file
    python -m app.testing.runner --url https://python.org --bookmarks bookmarks.html \
        --output results.json

    # Use inline folder structure (JSON)
    python -m app.testing.runner --url https://python.org \
        --folders '[{"id": "1", "name": "Tech", "children": [{"id": "2", "name": "Python", "children": []}]}]'
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

from app.testing.core import DEFAULT_MODEL, compare_models, run_test
from app.testing.parsers import extract_folder_names, parse_bookmarks_file
from app.testing.schemas import TestCase

try:
    from rich.console import Console
    from rich.table import Table

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


def print_result_table(results: list, console=None):
    """Print results in a formatted table."""
    if RICH_AVAILABLE and console:
        table = Table(title="Test Results")
        table.add_column("Model", style="cyan")
        table.add_column("Recommended Folder", style="green")
        table.add_column("New Folder", style="yellow")
        table.add_column("Analysis Time", style="blue")
        table.add_column("Total Time", style="magenta")
        table.add_column("Status", style="bold")

        for result in results:
            status = "[green]OK[/green]" if result.success else f"[red]FAIL: {result.error}[/red]"
            table.add_row(
                result.model,
                result.recommendation.recommended_folder or "-",
                result.recommendation.new_folder_name or "-",
                f"{result.analysis_time_ms:.0f}ms",
                f"{result.total_time_ms:.0f}ms",
                status,
            )

        console.print(table)
    else:
        print("\n" + "=" * 80)
        print("TEST RESULTS")
        print("=" * 80)
        for result in results:
            print(f"\nModel: {result.model}")
            print(f"  Recommended Folder: {result.recommendation.recommended_folder or '(none)'}")
            print(f"  New Folder Name: {result.recommendation.new_folder_name or '(none)'}")
            print(f"  Analysis Time: {result.analysis_time_ms:.0f}ms")
            print(f"  Recommendation Time: {result.recommendation_time_ms:.0f}ms")
            print(f"  Total Time: {result.total_time_ms:.0f}ms")
            print(f"  Status: {'OK' if result.success else f'FAIL: {result.error}'}")
        print("=" * 80)


def print_analysis(result, console=None):
    """Print URL analysis details."""
    if not result.success:
        return

    analysis = result.analysis
    if RICH_AVAILABLE and console:
        console.print("\n[bold]URL Analysis:[/bold]")
        console.print(f"  [cyan]Title:[/cyan] {analysis.title}")
        console.print(f"  [cyan]Summary:[/cyan] {analysis.summary}")
        console.print(f"  [cyan]Keywords:[/cyan] {', '.join(analysis.keywords)}")
    else:
        print("\nURL Analysis:")
        print(f"  Title: {analysis.title}")
        print(f"  Summary: {analysis.summary}")
        print(f"  Keywords: {', '.join(analysis.keywords)}")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Test bookmark processing and compare AI models",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--url",
        required=True,
        help="URL to analyze and get folder recommendation for",
    )

    folder_group = parser.add_mutually_exclusive_group(required=True)
    folder_group.add_argument(
        "--bookmarks",
        type=Path,
        help="Path to bookmark export file (HTML or JSON)",
    )
    folder_group.add_argument(
        "--folders",
        type=str,
        help="Inline JSON folder structure",
    )

    parser.add_argument(
        "--models",
        nargs="+",
        default=[DEFAULT_MODEL],
        help=f"Model(s) to test (default: {DEFAULT_MODEL}). "
        "Examples: openai/gpt-4o-mini, openai/gpt-4o, anthropic/claude-3-haiku-20240307",
    )

    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Save results to JSON file",
    )

    parser.add_argument(
        "--show-folders",
        action="store_true",
        help="Show parsed folder structure before running test",
    )

    parser.add_argument(
        "--show-analysis",
        action="store_true",
        help="Show detailed URL analysis in output",
    )

    parser.add_argument(
        "--name",
        default="cli-test",
        help="Name for this test case (used in output)",
    )

    return parser.parse_args()


async def main():
    """Main entry point for CLI."""
    args = parse_args()

    console = Console() if RICH_AVAILABLE else None

    if args.bookmarks:
        if console:
            console.print(f"[dim]Loading bookmarks from {args.bookmarks}...[/dim]")
        else:
            print(f"Loading bookmarks from {args.bookmarks}...")

        try:
            folders = parse_bookmarks_file(args.bookmarks)
        except (FileNotFoundError, ValueError) as e:
            print(f"Error loading bookmarks: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        try:
            from app.schemas.analyze import Folder

            folder_data = json.loads(args.folders)
            if isinstance(folder_data, dict):
                folder_data = [folder_data]
            folders = [Folder.model_validate(f) for f in folder_data]
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Error parsing folder JSON: {e}", file=sys.stderr)
            sys.exit(1)

    if args.show_folders:
        folder_paths = extract_folder_names(folders)
        if console:
            console.print("\n[bold]Parsed Folder Structure:[/bold]")
            for path in folder_paths:
                console.print(f"  {path}")
        else:
            print("\nParsed Folder Structure:")
            for path in folder_paths:
                print(f"  {path}")
        print()

    test_case = TestCase(
        name=args.name,
        url=args.url,
        folders=folders,
    )

    if console:
        console.print(f"\n[bold]Testing URL:[/bold] {args.url}")
        console.print(f"[bold]Models:[/bold] {', '.join(args.models)}")
    else:
        print(f"\nTesting URL: {args.url}")
        print(f"Models: {', '.join(args.models)}")

    if len(args.models) > 1:
        if console:
            console.print("[dim]Comparing models...[/dim]")
        else:
            print("Comparing models...")
        comparison = await compare_models(test_case, args.models)
        results = comparison.results
    else:
        result = await run_test(test_case, model=args.models[0])
        results = [result]

    if args.show_analysis and results:
        print_analysis(results[0], console)

    print_result_table(results, console)

    if args.output:
        output_data = {
            "timestamp": datetime.now().isoformat(),
            "url": args.url,
            "models": args.models,
            "results": [r.model_dump() for r in results],
        }
        args.output.write_text(json.dumps(output_data, indent=2, default=str))
        if console:
            console.print(f"\n[dim]Results saved to {args.output}[/dim]")
        else:
            print(f"\nResults saved to {args.output}")


def run():
    """Entry point for the CLI command."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
