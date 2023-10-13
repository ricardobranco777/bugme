"""
Allura
"""

from typing import Any

from utils import utc_date
from . import Generic, Issue, status


# Reference: https://forge-allura.apache.org/docs/api/index.html
class MyAllura(Generic):
    """
    Allura
    """

    def __init__(self, url: str, creds: dict):
        super().__init__(url, token=creds.get("token"))
        self.bugs = "bugs" if "sourceforge" in url else "tickets"
        self.issue_api_url = f"{self.url}/rest/p/{{repo}}/{self.bugs}/{{issue}}"
        self.issue_web_url = f"{self.url}/p/{{repo}}/{self.bugs}/{{issue}}"
        # NOTE: Allura's API doesn't support merge requests:
        # https://forge-allura.apache.org/p/allura/tickets/8235/

    def _to_issue(self, info: Any, **kwargs) -> Issue:
        repo = kwargs.pop("repo")
        info = info["ticket"]
        return Issue(
            tag=f'{self.tag}#{repo}#{info["ticket_num"]}',
            url=f'{self.url}/p/{repo}/{self.bugs}/{info["ticket_num"]}',
            assignee=info.get("assigned_to", "none"),
            creator=info["reported_by"],
            created=utc_date(info["created_date"]),
            updated=utc_date(info["mod_date"]),
            status=status(info["status"]),
            title=info["summary"],
            raw=info,
        )
