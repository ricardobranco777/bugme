"""
Pagure
"""

from typing import Any

from utils import utc_date
from . import Generic, Issue, status


# Reference: https://pagure.io/api/0/
class MyPagure(Generic):
    """
    Pagure
    """

    def __init__(self, url: str, creds: dict, **_):
        super().__init__(url, token=creds.get("token"))
        self.api_url = f"{self.url}/api/0/{{repo}}/issue/{{issue}}"
        self.issue_url = f"{self.url}/{{repo}}/issue/{{issue}}"

    def _to_issue(self, info: Any, **kwargs) -> Issue:
        repo = kwargs.pop("repo")
        return Issue(
            tag=f'{self.tag}#{repo}#{info["id"]}',
            url=info["full_url"],
            assignee=info["assignee"]["name"] if info["assignee"] else "none",
            creator=info["user"]["name"],
            created=utc_date(info["date_created"]),
            updated=utc_date(info["last_updated"]),
            status=status(info["status"]),
            title=info["title"],
            raw=info,
        )
