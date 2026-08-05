import structlog
from agents.base import BaseAgent, AgentResult, AgentStatus, Finding
from agents.ai_client import ask
from agents.github_client import GitHubRepoClient
from api.services.github_auth import get_github_auth_service

logger = structlog.get_logger(__name__)

SYSTEM_PROMPT = """\
You are a senior software architect. Analyze the provided code and identify:
1. Code smells (God classes, long methods, deep nesting, magic numbers, etc.)
2. Code duplication (repeated logic that should be extracted)
3. Architectural issues (circular dependencies, missing abstractions, wrong layer placement)

Respond in structured JSON only:
{
  "findings": [
    {
      "severity": "high|medium|low",
      "category": "smell|duplication|architecture",
      "message": "...",
      "file": "path/to/file.py",
      "line": null,
      "suggestion": "..."
    }
  ],
  "summary": "..."
}
"""


class ArchitectureAgent(BaseAgent):
    name = "architecture_agent"

    async def run(self, *, event_type: str, payload: dict, installation_id: int) -> AgentResult:
        if event_type != "pull_request":
            return self._skip("only runs on pull_request events")

        action = payload.get("action")
        if action not in ("opened", "synchronize", "reopened"):
            return self._skip(f"ignoring action={action}")

        pr = payload.get("pull_request", {})
        repo = payload.get("repository", {})
        pr_number = pr.get("number")
        head_sha = pr.get("head", {}).get("sha")
        owner, repo_name = repo.get("full_name", "/").split("/", 1)

        try:
            auth = get_github_auth_service()
            token = await auth.get_installation_token(installation_id)
            gh = GitHubRepoClient(token, owner, repo_name)

            changed_files = await gh.get_pr_files(pr_number)
            code_files = [f for f in changed_files if f.endswith((".py", ".ts", ".js", ".go", ".java"))]

            if not code_files:
                return self._skip("no analyzable code files in PR")

            # Build context: collect up to 5 files, max 500 lines each
            code_context = ""
            for path in code_files[:5]:
                repo_file = await gh.get_file(path, ref=head_sha)
                if repo_file:
                    lines = repo_file.content.splitlines()[:500]
                    code_context += f"\n\n--- {path} ---\n" + "\n".join(lines)

            import json
            response = await ask(SYSTEM_PROMPT, f"Analyze these files:\n{code_context}")

            try:
                data = json.loads(response)
            except json.JSONDecodeError:
                data = {"findings": [], "summary": response}

            findings = [
                Finding(
                    severity=f.get("severity", "low"),
                    category=f.get("category", "smell"),
                    message=f.get("message", ""),
                    file=f.get("file"),
                    line=f.get("line"),
                    suggestion=f.get("suggestion"),
                )
                for f in data.get("findings", [])
            ]

            summary = data.get("summary", "Architecture analysis complete.")
            conclusion = "failure" if any(f.severity == "high" for f in findings) else "success"

            await gh.post_check_run(
                name="Architecture Agent",
                head_sha=head_sha,
                conclusion=conclusion,
                summary=summary,
                details="\n".join(f"- [{f.severity.upper()}] {f.file}: {f.message}" for f in findings),
            )

            logger.info("Architecture analysis complete", findings=len(findings), pr=pr_number)
            return self._result(AgentStatus.SUCCESS, findings=findings, actions=["posted_check_run"])

        except Exception as exc:
            logger.error("Architecture agent failed", error=str(exc))
            return self._result(AgentStatus.FAILED, error=str(exc))
