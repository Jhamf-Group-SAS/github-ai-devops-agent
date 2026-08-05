import json
import re

import structlog

from agents.ai_client import ask
from agents.base import AgentResult, AgentStatus, BaseAgent, Finding
from agents.github_client import GitHubRepoClient
from api.services.github_auth import get_github_auth_service

logger = structlog.get_logger(__name__)

# Compiled secret patterns — no AI needed for known signatures
SECRET_PATTERNS: list[tuple[str, str, re.Pattern]] = [
    ("critical", "aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("critical", "private_key", re.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----")),
    ("critical", "github_token", re.compile(r"gh[pousr]_[A-Za-z0-9_]{36,}")),
    ("high", "generic_password", re.compile(r'(?i)password\s*=\s*["\'][^"\']{8,}["\']')),
    ("high", "generic_api_key", re.compile(r'(?i)api[_-]?key\s*=\s*["\'][^"\']{16,}["\']')),
    (
        "medium",
        "slack_webhook",
        re.compile(r"https://hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/"),
    ),
    ("medium", "stripe_key", re.compile(r"sk_live_[0-9a-zA-Z]{24,}")),
]

DEPENDENCY_SYSTEM = """\
You are a security expert. Given a list of Python dependencies (from requirements.txt or pyproject.toml),
identify any with known vulnerabilities, outdated versions with CVEs, or dangerous packages.

Respond in JSON only:
{
  "findings": [
    {"severity": "critical|high|medium|low", "package": "...", "version": "...", "message": "...", "cve": "CVE-..."}
  ]
}
"""


class SecurityAgent(BaseAgent):
    name = "security_agent"

    async def run(self, *, event_type: str, payload: dict, installation_id: int) -> AgentResult:
        if event_type not in ("pull_request", "push"):
            return self._skip(f"ignoring event={event_type}")

        repo = payload.get("repository", {})
        owner, repo_name = repo.get("full_name", "/").split("/", 1)

        if event_type == "pull_request":
            action = payload.get("action")
            if action not in ("opened", "synchronize", "reopened"):
                return self._skip(f"ignoring action={action}")
            pr = payload.get("pull_request", {})
            head_sha = pr.get("head", {}).get("sha", "HEAD")
            pr_number = pr.get("number")
        else:
            head_sha = payload.get("after", "HEAD")
            pr_number = None

        try:
            auth = get_github_auth_service()
            token = await auth.get_installation_token(installation_id)
            gh = GitHubRepoClient(token, owner, repo_name)

            findings: list[Finding] = []

            # 1. Secret scanning — check changed/all files
            if pr_number:
                file_paths = await gh.get_pr_files(pr_number)
            else:
                file_paths = await gh.list_files(ref=head_sha, max_files=50)

            for path in file_paths[:20]:
                if any(path.endswith(ext) for ext in (".png", ".jpg", ".gif", ".lock", ".sum")):
                    continue
                repo_file = await gh.get_file(path, ref=head_sha)
                if not repo_file:
                    continue
                for severity, category, pattern in SECRET_PATTERNS:
                    for match in pattern.finditer(repo_file.content):
                        line_num = repo_file.content[: match.start()].count("\n") + 1
                        findings.append(
                            Finding(
                                severity=severity,
                                category="secret",
                                message=f"Potential {category} detected",
                                file=path,
                                line=line_num,
                                suggestion="Remove secret and rotate immediately. Use environment variables.",
                            )
                        )

            # 2. Dependency CVE check via Claude
            req_file = await gh.get_file("requirements.txt", ref=head_sha)
            if not req_file:
                req_file = await gh.get_file("pyproject.toml", ref=head_sha)

            if req_file:
                response = await ask(DEPENDENCY_SYSTEM, f"Dependencies:\n{req_file.content}")
                try:
                    dep_data = json.loads(response)
                    for f in dep_data.get("findings", []):
                        findings.append(
                            Finding(
                                severity=f.get("severity", "medium"),
                                category="cve",
                                message=f"{f.get('package')} {f.get('version')}: {f.get('message')}",
                                file=req_file.path,
                                suggestion=f.get("cve"),
                            )
                        )
                except json.JSONDecodeError:
                    pass

            critical = sum(1 for f in findings if f.severity == "critical")
            conclusion = "failure" if critical > 0 else "success"
            summary = f"Security scan: {len(findings)} finding(s), {critical} critical."

            if head_sha and pr_number:
                await gh.post_check_run(
                    name="Security Agent",
                    head_sha=head_sha,
                    conclusion=conclusion,
                    summary=summary,
                    details="\n".join(
                        f"- [{f.severity.upper()}] {f.file}:{f.line or '?'} — {f.message}"
                        for f in findings
                    ),
                )

            logger.info("Security scan complete", findings=len(findings), critical=critical)
            return self._result(
                AgentStatus.SUCCESS, findings=findings, actions=["secret_scan", "dependency_check"]
            )

        except Exception as exc:
            logger.error("Security agent failed", error=str(exc))
            return self._result(AgentStatus.FAILED, error=str(exc))
