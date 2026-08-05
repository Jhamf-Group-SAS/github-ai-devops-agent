from unittest.mock import MagicMock

import pytest

from agents.base import AgentStatus, Finding
from agents.security import SECRET_PATTERNS

# ---------------------------------------------------------------------------
# Security agent — secret scanning (no external calls needed)
# ---------------------------------------------------------------------------


def test_secret_patterns_detect_aws_key():
    aws_pattern = next(p for _, cat, p in SECRET_PATTERNS if cat == "aws_access_key")
    assert aws_pattern.search("AKIAIOSFODNN7EXAMPLE") is not None


def test_secret_patterns_detect_github_token():
    gh_pattern = next(p for _, cat, p in SECRET_PATTERNS if cat == "github_token")
    assert gh_pattern.search("ghs_abcdefghijklmnopqrstuvwxyz012345") is not None


def test_secret_patterns_no_false_positive_on_placeholder():
    aws_pattern = next(p for _, cat, p in SECRET_PATTERNS if cat == "aws_access_key")
    assert aws_pattern.search("YOUR_AWS_ACCESS_KEY") is None


# ---------------------------------------------------------------------------
# Architecture agent — skip logic
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_architecture_agent_skips_non_pr_events():
    from agents.architecture import ArchitectureAgent

    agent = ArchitectureAgent()
    result = await agent.run(event_type="push", payload={}, installation_id=1)
    assert result.status == AgentStatus.SKIPPED


@pytest.mark.anyio
async def test_architecture_agent_skips_closed_pr():
    from agents.architecture import ArchitectureAgent

    agent = ArchitectureAgent()
    result = await agent.run(
        event_type="pull_request",
        payload={"action": "closed"},
        installation_id=1,
    )
    assert result.status == AgentStatus.SKIPPED


# ---------------------------------------------------------------------------
# Deploy agent — skip logic
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_deploy_agent_skips_non_default_branch():
    from agents.deploy import DeployAgent

    agent = DeployAgent()
    result = await agent.run(
        event_type="push",
        payload={
            "ref": "refs/heads/feature-x",
            "repository": {"default_branch": "main", "full_name": "org/repo"},
        },
        installation_id=1,
    )
    assert result.status == AgentStatus.SKIPPED


@pytest.mark.anyio
async def test_deploy_agent_skips_non_push():
    from agents.deploy import DeployAgent

    agent = DeployAgent()
    result = await agent.run(event_type="pull_request", payload={}, installation_id=1)
    assert result.status == AgentStatus.SKIPPED


# ---------------------------------------------------------------------------
# AgentResult helpers
# ---------------------------------------------------------------------------


def test_agent_result_counts_severity():
    result = MagicMock()
    result.findings = [
        Finding("critical", "secret", "AWS key found"),
        Finding("high", "cve", "CVE in package"),
        Finding("low", "smell", "Long method"),
    ]
    from agents.base import AgentResult, AgentStatus

    r = AgentResult(agent="test", status=AgentStatus.SUCCESS, findings=result.findings)
    assert r.critical_count == 1
    assert r.high_count == 1
