import json

import structlog

from agents.ai_client import ask
from agents.base import AgentResult, AgentStatus, BaseAgent, Finding
from agents.github_client import GitHubRepoClient
from api.services.github_auth import get_github_auth_service

logger = structlog.get_logger(__name__)

SYSTEM_PROMPT = """\
You are a senior QA engineer. Given source code files, generate comprehensive pytest tests.

Rules:
- Use pytest with async support where needed (pytest-asyncio)
- Cover happy paths, edge cases, and error cases
- Mock external dependencies
- Aim for >90% coverage of the provided code
- Do NOT include explanations, only return the test file content

Return only valid Python code, no markdown fences.
"""

COVERAGE_SYSTEM = """\
You are a test coverage analyst. Given a list of source files and existing test files,
identify which functions/classes lack test coverage.

Respond in JSON only:
{
  "coverage_gaps": [
    {"file": "...", "symbol": "function_name", "severity": "high|medium|low", "reason": "..."}
  ],
  "estimated_coverage": 0-100
}
"""


class TestAgent(BaseAgent):
    name = "test_agent"

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
        head_branch = pr.get("head", {}).get("ref", "main")
        owner, repo_name = repo.get("full_name", "/").split("/", 1)

        try:
            auth = get_github_auth_service()
            token = await auth.get_installation_token(installation_id)
            gh = GitHubRepoClient(token, owner, repo_name)

            changed_files = await gh.get_pr_files(pr_number)
            python_files = [
                f for f in changed_files if f.endswith(".py") and not f.startswith("test")
            ]

            if not python_files:
                return self._skip("no Python source files changed")

            findings: list[Finding] = []
            actions: list[str] = []
            pr_url = None

            # 1. Coverage gap analysis
            all_files = await gh.list_files(ref=head_sha)
            test_files = [f for f in all_files if f.startswith("test") or "/test" in f]
            source_files = [f for f in python_files[:5]]

            source_context = ""
            for path in source_files:
                repo_file = await gh.get_file(path, ref=head_sha)
                if repo_file:
                    source_context += f"\n--- SOURCE: {path} ---\n{repo_file.content[:3000]}"

            test_context = ""
            for path in test_files[:3]:
                repo_file = await gh.get_file(path, ref=head_sha)
                if repo_file:
                    test_context += f"\n--- TEST: {path} ---\n{repo_file.content[:1000]}"

            coverage_response = await ask(
                COVERAGE_SYSTEM,
                f"Source files:\n{source_context}\n\nExisting tests:\n{test_context or 'None'}",
            )

            try:
                coverage_data = json.loads(coverage_response)
                estimated = coverage_data.get("estimated_coverage", 0)
                for gap in coverage_data.get("coverage_gaps", []):
                    findings.append(
                        Finding(
                            severity=gap.get("severity", "medium"),
                            category="coverage",
                            message=f"Missing tests for {gap.get('symbol')} in {gap.get('file')}",
                            file=gap.get("file"),
                            suggestion=gap.get("reason"),
                        )
                    )
            except json.JSONDecodeError:
                estimated = 0

            actions.append("coverage_analysis")

            # 2. Generate tests for the first uncovered source file
            if findings and source_files:
                first_file = source_files[0]
                repo_file = await gh.get_file(first_file, ref=head_sha)
                if repo_file:
                    generated_tests = await ask(
                        SYSTEM_PROMPT,
                        f"Generate tests for:\n\n{repo_file.content}",
                        max_tokens=2048,
                    )

                    test_path = first_file.replace("api/", "tests/").replace(".py", "_test.py")
                    if not test_path.startswith("tests/"):
                        test_path = f"tests/generated/{test_path}"

                    existing = await gh.get_file(test_path, ref=head_sha)
                    branch_name = f"agent/tests-{pr_number}"

                    try:
                        await gh.create_branch(branch_name, from_ref=head_branch)
                    except Exception as exc:
                        logger.debug("Branch may already exist", error=str(exc))

                    await gh.create_or_update_file(
                        path=test_path,
                        content=generated_tests,
                        message=f"test: generate tests for {first_file} [agent]",
                        branch=branch_name,
                        sha=existing.sha if existing else None,
                    )

                    pr_url = await gh.create_pull_request(
                        title=f"test: generated tests for PR #{pr_number}",
                        body=f"Auto-generated by Test Agent.\n\nEstimated coverage: {estimated}%\n\nFindings: {len(findings)}",
                        head=branch_name,
                        base=head_branch,
                    )
                    actions.append("generated_tests_pr")

            conclusion = "success" if estimated >= 80 else "neutral"
            await gh.post_check_run(
                name="Test Agent",
                head_sha=head_sha,
                conclusion=conclusion,
                summary=f"Estimated coverage: {estimated}%. {len(findings)} gap(s) found.",
                details="\n".join(f"- [{f.severity.upper()}] {f.message}" for f in findings),
            )

            logger.info("Test analysis complete", gaps=len(findings), coverage=estimated)
            return self._result(
                AgentStatus.SUCCESS, findings=findings, actions=actions, pr_url=pr_url
            )

        except Exception as exc:
            logger.error("Test agent failed", error=str(exc))
            return self._result(AgentStatus.FAILED, error=str(exc))
