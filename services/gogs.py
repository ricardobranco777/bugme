"""
Gogs
"""

from typing import Any

from utils import utc_date
from . import Generic, Issue, status


# Reference: https://github.com/gogs/docs-api/tree/master/Issues
class MyGogs(Generic):
    """
    Gogs
    """

    def __init__(self, url: str, creds: dict):
        super().__init__(url, token=creds.get("token"))
        self.issue_api_url = f"{self.url}/api/v1/repos/{{repo}}/issues/{{issue}}"
        self.issue_web_url = f"{self.url}/{{repo}}/issues/{{issue}}"
        # NOTE: Gogs' API doesn't support pull requests:
        # https://github.com/gogs/gogs/issues/2253

    def _to_issue(self, info: Any, **kwargs) -> Issue:
        repo = kwargs.pop("repo")
        return Issue(
            tag=f'{self.tag}#{repo}#{info["number"]}',
            url=f'{self.url}/{repo}/issues/{info["number"]}',
            assignee=info["assignee"]["username"] if info["assignee"] else "none",
            creator=info["user"]["username"],
            created=utc_date(info["created_at"]),
            updated=utc_date(info["updated_at"]),
            status=status(info["state"]),
            title=info["title"],
            raw=info,
        )
