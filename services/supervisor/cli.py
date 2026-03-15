"""
services/supervisor/cli.py
Distributed CLI — `inboxpilot-dist check` triggers the pipeline via the supervisor REST API.
"""
from __future__ import annotations
import sys
import os
import click
import httpx
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

console = Console()

SUPERVISOR_URL = os.environ.get("SUPERVISOR_URL", "http://localhost:8080")


@click.group()
def cli():
    """InboxPilot Distributed — A2A pipeline CLI"""
    pass


@cli.command()
@click.option("--mode", default="production", show_default=True,
              type=click.Choice(["demo", "production"]),
              help="Email fetch mode.")
@click.option("--supervisor-url", default=None,
              help="Override supervisor URL (default: $SUPERVISOR_URL or http://localhost:8080)")
def check(mode: str, supervisor_url: str | None):
    """Run the distributed InboxPilot pipeline via the supervisor service."""
    url = supervisor_url or SUPERVISOR_URL

    console.print(Panel(
        f"[bold cyan]InboxPilot Distributed[/bold cyan] ([yellow]{mode.upper()} MODE[/yellow])\n"
        f"[dim]Supervisor: {url}[/dim]",
        expand=False,
    ))

    # Check that supervisor is reachable
    try:
        health = httpx.get(f"{url}/health", timeout=5.0)
        health.raise_for_status()
    except Exception as exc:
        console.print(f"[bold red]❌ Cannot reach supervisor at {url}: {exc}[/bold red]")
        console.print("[dim]Is the stack running? Try: docker compose up -d[/dim]")
        sys.exit(1)

    console.rule("[bold]Triggering distributed pipeline[/bold]")
    console.print(f"  [dim]Calling POST {url}/pipeline/run ...[/dim]")

    try:
        with console.status("[cyan]Running pipeline (this may take a minute)...[/cyan]"):
            resp = httpx.post(
                f"{url}/pipeline/run",
                json={"mode": mode},
                timeout=300.0,  # LLM calls can take a while
            )
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        console.print(f"[bold red]❌ Pipeline failed: {exc.response.text}[/bold red]")
        sys.exit(1)
    except Exception as exc:
        console.print(f"[bold red]❌ Error: {exc}[/bold red]")
        sys.exit(1)

    data = resp.json()

    console.rule("[bold]Pipeline complete[/bold]")

    # Print log
    for line in data.get("log", []):
        if "[FETCH]" in line:
            console.print(f"[blue]{line}[/blue]")
        elif "[CLASSIFY]" in line:
            console.print(f"[green]{line}[/green]")
        elif "[RESPOND]" in line:
            console.print(f"[magenta]{line}[/magenta]")
        elif "→" in line:
            console.print(f"  [dim]{line}[/dim]")
        else:
            console.print(line)

    # Summary table
    table = Table(title="Session Summary", box=box.ROUNDED, show_header=False)
    table.add_column("Key", style="bold")
    table.add_column("Value")
    table.add_row("Emails processed", str(data.get("emails_processed", 0)))
    table.add_row("Drafts created", f"{data.get('drafts_created', 0)} (pending approval)")
    table.add_row("Archived", str(data.get("archived", 0)))
    table.add_row("Flagged for review", str(data.get("flagged_for_review", 0)))
    table.add_row("Session ID", data.get("session_id", ""))
    if data.get("errors", 0):
        table.add_row("[red]Errors[/red]", str(data["errors"]))
    console.print(table)


if __name__ == "__main__":
    cli()
