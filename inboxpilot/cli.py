"""
inboxpilot/cli.py
CLI for InboxPilot — commands: check, review, config, learn, stats
"""
from __future__ import annotations
import os
import sys
import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich import box

from inboxpilot.config_loader import load_config, save_config
from inboxpilot.db import SimulatedDatabase

console = Console()


def _get_db(config: dict) -> SimulatedDatabase:
    persist_path = config.get("memory", {}).get("persist_path", "inboxpilot_memory.json")
    return SimulatedDatabase(persist_path=persist_path)


def _check_openai_key():
    if not os.environ.get("GROQ_API_KEY"):
        console.print("[bold red]❌ GROQ_API_KEY environment variable is not set.[/bold red]")
        console.print("Set it with: [cyan]export GROQ_API_KEY=gsk_...[/cyan]")
        console.print("Get a FREE key at: [link]https://console.groq.com[/link] (no credit card needed)")
        sys.exit(1)


# ── CLI group ──────────────────────────────────────────────────────────────────

@click.group()
def cli():
    """InboxPilot — Agentic AI Email Assistant"""
    pass


# ── check ──────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--config-path", default="config.yaml", show_default=True, help="Path to config file.")
def check(config_path):
    """Run the full email processing pipeline."""
    _check_openai_key()
    config = load_config(config_path)
    mode = config.get("app", {}).get("mode", "demo")
    version = config.get("app", {}).get("version", "1.0.0")

    console.print(Panel(
        f"[bold cyan]InboxPilot v{version}[/bold cyan] ([yellow]{mode.upper()} MODE[/yellow])",
        expand=False,
    ))

    db = _get_db(config)

    log_lines = []

    def logger(msg: str):
        log_lines.append(msg)
        # Colour-code by prefix
        if msg.startswith("[FETCH]"):
            console.print(f"[blue]{msg}[/blue]")
        elif msg.startswith("[CLASSIFY]"):
            console.print(f"[green]{msg}[/green]")
        elif msg.startswith("[RESPOND]"):
            console.print(f"[magenta]{msg}[/magenta]")
        elif msg.strip().startswith("→"):
            console.print(f"  [dim]{msg.strip()}[/dim]")
        else:
            console.print(msg)

    from inboxpilot.orchestrator import run_pipeline

    console.rule("[bold]Starting pipeline[/bold]")
    final_state = run_pipeline(config=config, db=db, logger=logger)
    console.rule("[bold]Pipeline complete[/bold]")

    # Summary table
    drafts = final_state.get("drafts_created", [])
    actions = final_state.get("actions_taken", [])
    archived = sum(1 for a in actions if "archived" in a.get("action", "").lower() or "newsletter" in a.get("action", "").lower())
    flagged = sum(1 for a in actions if "manual" in a.get("action", "").lower())

    table = Table(title="Session Summary", box=box.ROUNDED, show_header=False)
    table.add_column("Key", style="bold")
    table.add_column("Value")
    table.add_row("Emails processed", str(final_state.get("total_emails", 0)))
    table.add_row("Drafts created", f"{len(drafts)} (pending approval)")
    table.add_row("Archived", str(archived))
    table.add_row("Flagged for manual review", str(flagged))
    table.add_row("Session ID", final_state.get("session_id", ""))
    if final_state.get("errors"):
        table.add_row("[red]Errors[/red]", str(len(final_state["errors"])))
    console.print(table)

    if drafts:
        console.print("\n[bold]Run [cyan]inboxpilot review[/cyan] to approve pending drafts.[/bold]")


# ── review ─────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--config-path", default="config.yaml", show_default=True)
def review(config_path):
    """Interactively review and approve pending draft responses."""
    config = load_config(config_path)
    db = _get_db(config)

    pending = db.get_pending_drafts()
    if not pending:
        console.print("[yellow]No pending drafts to review.[/yellow]")
        return

    console.print(Panel(f"[bold]Pending Drafts ({len(pending)})[/bold]", expand=False))

    for i, draft in enumerate(pending, 1):
        console.rule(f"[{i}/{len(pending)}] {draft.subject}")
        email_rec = db.get_email(draft.email_id)
        if email_rec:
            console.print(f"[dim]To: {email_rec.sender_email}[/dim]")
        if draft.proposed_meetings:
            slots = ", ".join(f"{m['day']} at {m['time']}" for m in draft.proposed_meetings)
            console.print(f"[dim]Proposed meeting slots: {slots}[/dim]")
        console.print()
        console.print(Panel(draft.body, title="Draft", border_style="cyan"))
        console.print()

        choice = Prompt.ask(
            "[a]pprove  [e]dit  [d]iscard  [s]kip",
            choices=["a", "e", "d", "s"],
            default="s",
        )
        if choice == "a":
            db.approve_draft(draft.id)
            db.save()
            console.print("[green]✓ Draft approved.[/green]")
        elif choice == "e":
            console.print("[yellow]Opening editor... (paste your edited body, end with a blank line)[/yellow]")
            lines = []
            while True:
                line = input()
                if line == "":
                    break
                lines.append(line)
            draft.body = "\n".join(lines)
            db.save_draft(draft)
            db.approve_draft(draft.id)
            db.save()
            console.print("[green]✓ Edited draft approved.[/green]")
        elif choice == "d":
            db.discard_draft(draft.id)
            db.save()
            console.print("[red]Draft discarded.[/red]")
        else:
            console.print("[dim]Skipped.[/dim]")

    console.print("\n[bold]Review complete.[/bold]")


# ── config ─────────────────────────────────────────────────────────────────────

@cli.command("config")
@click.option("--config-path", default="config.yaml", show_default=True)
def config_cmd(config_path):
    """Interactive configuration wizard."""
    console.print(Panel("[bold]InboxPilot Configuration Wizard[/bold]", expand=False))
    cfg = load_config(config_path) if os.path.exists(config_path) else {}

    app_cfg = cfg.setdefault("app", {})
    mode_in = Prompt.ask("Mode", choices=["demo", "production"], default=app_cfg.get("mode", "demo"))
    app_cfg["mode"] = mode_in

    api_key = Prompt.ask("OpenAI API Key (leave blank to use env var)", default="", password=True)
    if api_key.strip():
        os.environ["OPENAI_API_KEY"] = api_key.strip()
        console.print("[yellow]Note: API key set for this session only — export OPENAI_API_KEY to persist.[/yellow]")

    demo_cfg = app_cfg.setdefault("demo", {})
    count = Prompt.ask("Demo email count", default=str(demo_cfg.get("email_count", 5)))
    demo_cfg["email_count"] = int(count)

    auto_save = Confirm.ask("Auto-save drafts?", default=True)
    cfg.setdefault("email", {})["auto_save_drafts"] = auto_save

    save_config(cfg, config_path)
    console.print(f"\n[green]✓ Configuration saved to {config_path}[/green]")


# ── learn ──────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--config-path", default="config.yaml", show_default=True)
def learn(config_path):
    """Simulate learning writing style from sent mail."""
    import time
    config = load_config(config_path)
    db = _get_db(config)

    console.print("[bold]Learning your writing style...[/bold]")
    with console.status("Analysing sent emails..."):
        time.sleep(1.2)

    # Seed style samples into DB
    from inboxpilot.tools.style_tool import STYLE_SAMPLES
    for sample in STYLE_SAMPLES:
        db.add_style_sample(sample["text"], sample["context"])
    db.save()

    table = Table(title="Style Profile Created", box=box.ROUNDED, show_header=False)
    table.add_column("Metric", style="bold")
    table.add_column("Value")
    table.add_row("Average length", "65 words")
    table.add_row("Common sign-offs", "Best, Thanks, Cheers")
    table.add_row("Formality", "Professional-friendly")
    table.add_row("Response time pattern", "Morning (9–11am)")
    table.add_row("Samples stored", str(len(STYLE_SAMPLES)))
    console.print(table)
    console.print("[green]✓ Profile saved to memory.[/green]")


# ── stats ──────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--config-path", default="config.yaml", show_default=True)
def stats(config_path):
    """Show processing statistics."""
    config = load_config(config_path)
    db = _get_db(config)
    s = db.get_stats()

    console.print(Panel("[bold]InboxPilot Statistics[/bold]", expand=False))

    overview = Table(box=box.ROUNDED, show_header=False)
    overview.add_column("Metric", style="bold")
    overview.add_column("Value", style="cyan")
    overview.add_row("Sessions run", str(s["sessions"]))
    overview.add_row("Emails processed", str(s["emails_processed"]))
    overview.add_row("Drafts created", str(s["drafts_created"]))
    overview.add_row("Drafts approved", str(s["drafts_approved"]))
    overview.add_row("Average confidence", str(s["avg_confidence"]))
    console.print(overview)

    if s["category_counts"]:
        console.print()
        cat_table = Table(title="Category Breakdown", box=box.SIMPLE_HEAD)
        cat_table.add_column("Category", style="bold")
        cat_table.add_column("Count", justify="right")
        for cat, count in sorted(s["category_counts"].items(), key=lambda x: -x[1]):
            cat_table.add_row(cat, str(count))
        console.print(cat_table)

    # Rough time saved estimate: 3 min per draft approved
    time_saved_min = s["drafts_approved"] * 3
    hours = time_saved_min // 60
    mins = time_saved_min % 60
    console.print(f"\n[bold]Estimated time saved:[/bold] [green]{hours}h {mins}m[/green]")

    sessions = db.list_sessions(limit=5)
    if sessions:
        console.print()
        ses_table = Table(title="Recent Sessions", box=box.SIMPLE_HEAD)
        ses_table.add_column("Session ID")
        ses_table.add_column("Started")
        ses_table.add_column("Emails")
        ses_table.add_column("Drafts")
        ses_table.add_column("Status")
        for ses in sessions:
            ses_table.add_row(
                ses.id,
                ses.started_at[:19].replace("T", " "),
                str(ses.emails_processed),
                str(ses.drafts_created),
                ses.status,
            )
        console.print(ses_table)
