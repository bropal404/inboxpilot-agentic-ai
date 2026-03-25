"""
inboxpilot/agents/fetch_agent.py
Fetch Agent: retrieves emails via IMAP (demo or real mode).
"""
from __future__ import annotations
from typing import List
from inboxpilot.models import EmailObject
from inboxpilot.tools.imap_tool import fetch_emails_demo, fetch_emails_real


def run_fetch_agent(config: dict) -> List[EmailObject]:
    """
    Fetch emails based on mode in config.
    Returns a list of EmailObject instances.
    """
    mode = config.get("app", {}).get("mode", "demo")
    demo_cfg = config.get("app", {}).get("demo", {})
    email_cfg = config.get("email", {})
    latency_ms = demo_cfg.get("latency_ms", 300)
    count = demo_cfg.get("email_count", 5)

    if mode == "demo":
        emails = fetch_emails_demo(latency_ms=latency_ms, count=count)
    else:
        import os
        emails = fetch_emails_real(
            host=email_cfg.get("imap_host", "imap.gmail.com"),
            port=email_cfg.get("imap_port", 993),
            username=os.environ.get("INBOX_EMAIL", email_cfg.get("username", "")),
            password=os.environ.get("INBOX_PASSWORD", email_cfg.get("password", "")),
            folder=email_cfg.get("check_folder", "INBOX"),
            max_fetch=email_cfg.get("max_fetch", 10),
        )
    return emails
