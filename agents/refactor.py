import json

import structlog

from agents.ai_client import ask
from agents.base import AgentResult, AgentStatus, BaseAgent, Finding
from agents.github_client import GitHubRepoClient
from api.services.github_auth import get_github_auth_service

logger = structlog.get_logger(__name__)

SYSTEM_PROMPT = """\
You are a senior software engineer specializing in refactoring.

Given a source file, identify and apply refactoring improvements:
- Extract long functions (>50 lines) into smaller ones
- Remove duplicate code
- Simplify complex conditionals
- Improve naming
- Reduce cyclomatic complexity

Return the COMPLETE refactored file content followed by a JSON summary:
===REFACTORED===
<complete file content>
===SUMMARY===
{"changes": ["...", "..."], "complexity_reduction": "high|medium|low"}
"""


class RefactorAgent(BaseAgent):
    name = "refactor_agent"

    async def run(self, *, event_type: str, payload: dict, installation_id: int) -> AgentResult:
        if event_type != "pull_request":
            return self._skip("only runs on pull_request events")

        action = payload.get("action")
        if action not in ("opened",):
            return self._skip("only runs on newly opened PRs")

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
                f
                for f in changed_files
                if f.endswith(".py") and not f.startswith("test") and "migration" not in f
            ]

            if not python_files:
                return self._skip("no refactorable Python files")

            findings: list[Finding] = []
            actions: list[str] = []
            pr_url = None

            # Analyze first complex file
            for path in python_files[:3]:
                repo_file = await gh.get_file(path, ref=head_sha)
                if not repo_file or len(repo_file.content.splitlines()) < 30:
                    continue

                response = await ask(SYSTEM_PROMPT, repo_file.content, max_tokens=4096)

                if "===REFACTORED===" in response and "===SUMMARY===" in response:
                    parts = response.split("===REFACTORED===")[1].split("===SUMMARY===")
                    refactored_content = parts[0].strip()
                    try:
                        summary_data = json.loads(parts[1].strip())
                        changes = summary_data.get("changes", [])
                    except json.JSONDecodeError:
                        changes = ["Refactoring applied"]

                    if refactored_content and refactored_content != repo_file.content:
                        branch_name = f"agent/refactor-{pr_number}"
                        try:
                            await gh.create_branch(branch_name, from_ref=head_branch)
                        except Exception as exc:
                            logger.debug("Branch may already exist", error=str(exc))

                        await gh.create_or_update_file(
                            path=path,
                            content=refactored_content,
                            message=f"refactor: reduce complexity in {path} [agent]",
                            branch=branch_name,
                            sha=repo_file.sha,
                        )

                        if not pr_url:
                            pr_url = await gh.create_pull_request(
                                title=f"refactor: suggestions for PR #{pr_number}",
                                body="Refactoring suggestions by Refactor Agent.\n\nChanges:\n"
                                + "\n".join(f"- {c}" for c in changes),
                                head=branch_name,
                                base=head_branch,
                            )
                            actions.append("created_refactor_pr")

                        for change in changes:
                            findings.append(
                                Finding(
                                    severity="low",
                                    category="refactor",
                                    message=change,
                                    file=path,
                                )
                            )
                break

            logger.info("Refactor analysis complete", findings=len(findings))
            return self._result(
                AgentStatus.SUCCESS, findings=findings, actions=actions, pr_url=pr_url
            )

        except Exception as exc:
            logger.error("Refactor agent failed", error=str(exc))
            return self._result(AgentStatus.FAILED, error=str(exc))
