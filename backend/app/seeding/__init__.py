"""Seed data for the CodefyUI Online Judge.

Idempotently inserts a default admin user, a starter contest, and 5 baseline
problems (with pre-generated hidden test data) on container boot. Re-running
is safe: existing rows are detected by slug/email and skipped.

Entry point: ``python -m app.seeding.runner``.
"""
