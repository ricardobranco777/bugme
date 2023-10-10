"""
Gitea
"""

from typing import Any

from utils import utc_date
from . import Generic, Issue, status


# Reference: https://try.gitea.io/api/swagger
class MyGitea(Generic):
    """
    Gitea
    """

    def __init__(self, url: str, creds: dict):
        super().__init__(url, token=creds.get("token"))
        self.api_url = f"{self.url}/api/v1/repos/{{repo}}/issues/{{issue}}"
        self.issue_url = f"{self.url}/{{repo}}/issues/{{issue}}"

    def _to_issue(self, info: Any, **kwargs) -> Issue:
        return Issue(
            tag=f'{self.tag}#{info["repository"]["full_name"]}#{info["number"]}',
            url=info["html_url"],
            assignee=info["assignee"]["login"] if info["assignee"] else "none",
            creator=info["user"]["login"],
            created=utc_date(info["created_at"]),
            updated=utc_date(info["updated_at"]),
            status=status(info["state"]),
            title=info["title"],
            raw=info,
        )
