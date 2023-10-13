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

    def __init__(self, url: str, creds: dict):
        super().__init__(url, token=creds.get("token"))
        self.issue_api_url = f"{self.url}/api/0/{{repo}}/issue/{{issue}}"
        self.issue_web_url = f"{self.url}/{{repo}}/issue/{{issue}}"
        self.pr_api_url = f"{self.url}/api/0/{{repo}}/pull-request/{{issue}}"
        self.pr_web_url = f"{self.url}/{{repo}}/pull-request/{{issue}}"

    def _to_issue(self, info: Any, **kwargs) -> Issue:
        repo = kwargs.pop("repo")
        is_pr = kwargs.pop("is_pr")
        mark = "!" if is_pr else "#"
        return Issue(
            tag=f'{self.tag}#{repo}{mark}{info["id"]}',
            url=info["full_url"],
            assignee=info["assignee"]["name"] if info["assignee"] else "none",
            creator=info["user"]["name"],
            created=utc_date(info["date_created"]),
            updated=utc_date(info["last_updated"]),
            status=status(info["status"]),
            title=info["title"],
            raw=info,
        )
