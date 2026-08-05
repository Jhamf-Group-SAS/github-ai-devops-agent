import httpx
import structlog

from agents.base import AgentResult, AgentStatus, BaseAgent
from api.services.github_auth import get_github_auth_service

logger = structlog.get_logger(__name__)

GITHUB_API = "https://api.github.com"
HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


class DeployAgent(BaseAgent):
    name = "deploy_agent"

    async def run(self, *, event_type: str, payload: dict, installation_id: int) -> AgentResult:
        # Only deploy on push to main/master
        if event_type != "push":
            return self._skip("only runs on push events")

        ref = payload.get("ref", "")
        repo = payload.get("repository", {})
        default_branch = repo.get("default_branch", "main")

        if ref != f"refs/heads/{default_branch}":
            return self._skip(f"only deploys on push to {default_branch}")

        owner, repo_name = repo.get("full_name", "/").split("/", 1)

        try:
            auth = get_github_auth_service()
            token = await auth.get_installation_token(installation_id)

            # Trigger the deploy workflow via workflow_dispatch
            workflow_id = "deploy.yml"
            async with httpx.AsyncClient() as client:
                r = await client.post(
                    f"{GITHUB_API}/repos/{owner}/{repo_name}/actions/workflows/{workflow_id}/dispatches",
                    headers={**HEADERS, "Authorization": f"Bearer {token}"},
                    json={"ref": default_branch},
                    timeout=10,
                )
                if r.status_code == 404:
                    return self._skip("deploy.yml workflow not found — skipping")
                r.raise_for_status()

            logger.info(
                "Deploy workflow triggered", repo=repo.get("full_name"), branch=default_branch
            )
            return self._result(AgentStatus.SUCCESS, actions=["triggered_deploy_workflow"])

        except Exception as exc:
            logger.error("Deploy agent failed", error=str(exc))
            return self._result(AgentStatus.FAILED, error=str(exc))
