"""
Event filtering utilities for webhook processing.
"""

IGNORED_ACTIONS = {"labeled", "unlabeled", "assigned", "unassigned", "milestoned"}


def should_process_pr(action: str) -> bool:
    """Return True if the pull_request action warrants agent analysis."""
    return action in {"opened", "synchronize", "reopened"}


def should_process_push(ref: str) -> bool:
    """Return True if the push is to a branch we care about (not tags)."""
    return ref.startswith("refs/heads/")
