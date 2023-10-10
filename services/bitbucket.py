"""
Bitbucket
"""

from typing import Any

from utils import utc_date
from . import Generic, Issue, status


# Reference: https://developer.atlassian.com/cloud/bitbucket/rest/api-group-issue-tracker/
class MyBitbucket(Generic):
    """
    Bitbucket
    """

    def __init__(self, url: str, creds: dict):
        super().__init__(url, token=creds.get("token"))
        self.api_url = (
            "https://api.bitbucket.org/2.0/repositories/{repo}/issues/{issue}"
        )
        self.issue_url = f"{self.url}/{{repo}}/issues/{{issue}}"

    def _to_issue(self, info: Any, **kwargs) -> Issue:
        return Issue(
            tag=f'{self.tag}#{info["repository"]["full_name"]}#{info["id"]}',
            url=info["links"]["html"]["href"],
            assignee=info["assignee"]["display_name"] if info["assignee"] else "none",
            creator=info["reporter"]["display_name"] if info["reporter"] else "none",
            created=utc_date(info["created_on"]),
            updated=utc_date(info["updated_on"]),
            status=status(info["state"]),
            title=info["title"],
            raw=info,
        )
