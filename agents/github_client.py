"""
GitHub API helpers for agents.
All operations require an installation access token.
"""
import base64
import json
import structlog
import httpx
from dataclasses import dataclass

logger = structlog.get_logger(__name__)

GITHUB_API = "https://api.github.com"
HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


@dataclass
class RepoFile:
    path: str
    content: str
    sha: str


class GitHubRepoClient:
    def __init__(self, token: str, owner: str, repo: str) -> None:
        self._token = token
        self._owner = owner
        self._repo = repo
        self._base = f"{GITHUB_API}/repos/{owner}/{repo}"

    def _headers(self) -> dict:
        return {**HEADERS, "Authorization": f"Bearer {self._token}"}

    async def get_default_branch(self) -> str:
        async with httpx.AsyncClient() as client:
            r = await client.get(self._base, headers=self._headers(), timeout=10)
            r.raise_for_status()
        return r.json().get("default_branch", "main")

    async def get_file(self, path: str, ref: str = "HEAD") -> RepoFile | None:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{self._base}/contents/{path}",
                headers=self._headers(),
                params={"ref": ref},
                timeout=10,
            )
        if r.status_code == 404:
            return None
        r.raise_for_status()
        data = r.json()
        content = base64.b64decode(data["content"]).decode(errors="replace")
        return RepoFile(path=path, content=content, sha=data["sha"])

    async def list_files(self, ref: str = "HEAD", max_files: int = 100) -> list[str]:
        """Return flat list of file paths via git tree."""
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{self._base}/git/trees/{ref}",
                headers=self._headers(),
                params={"recursive": "1"},
                timeout=15,
            )
            r.raise_for_status()
        tree = r.json().get("tree", [])
        return [item["path"] for item in tree if item["type"] == "blob"][:max_files]

    async def get_pr_files(self, pr_number: int) -> list[str]:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{self._base}/pulls/{pr_number}/files",
                headers=self._headers(),
                timeout=10,
            )
            r.raise_for_status()
        return [f["filename"] for f in r.json()]

    async def create_branch(self, branch: str, from_ref: str = "HEAD") -> None:
        # Get SHA of from_ref
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{self._base}/git/ref/heads/{from_ref.lstrip('refs/heads/')}",
                headers=self._headers(),
                timeout=10,
            )
            if r.status_code == 404:
                # Try as SHA directly
                sha = from_ref
            else:
                r.raise_for_status()
                sha = r.json()["object"]["sha"]

            r2 = await client.post(
                f"{self._base}/git/refs",
                headers=self._headers(),
                json={"ref": f"refs/heads/{branch}", "sha": sha},
                timeout=10,
            )
            r2.raise_for_status()

    async def create_or_update_file(
        self, path: str, content: str, message: str, branch: str, sha: str | None = None
    ) -> None:
        body: dict = {
            "message": message,
            "content": base64.b64encode(content.encode()).decode(),
            "branch": branch,
        }
        if sha:
            body["sha"] = sha
        async with httpx.AsyncClient() as client:
            r = await client.put(
                f"{self._base}/contents/{path}",
                headers=self._headers(),
                json=body,
                timeout=10,
            )
            r.raise_for_status()

    async def create_pull_request(
        self, title: str, body: str, head: str, base: str
    ) -> str:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self._base}/pulls",
                headers=self._headers(),
                json={"title": title, "body": body, "head": head, "base": base},
                timeout=10,
            )
            r.raise_for_status()
        pr_url = r.json()["html_url"]
        logger.info("Pull request created", url=pr_url)
        return pr_url

    async def post_check_run(
        self,
        name: str,
        head_sha: str,
        conclusion: str,
        summary: str,
        details: str = "",
    ) -> None:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self._base}/check-runs",
                headers=self._headers(),
                json={
                    "name": name,
                    "head_sha": head_sha,
                    "status": "completed",
                    "conclusion": conclusion,
                    "output": {"title": name, "summary": summary, "text": details},
                },
                timeout=10,
            )
            r.raise_for_status()
