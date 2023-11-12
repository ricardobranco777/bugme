"""
Gitea
"""

import logging
from typing import Any

from requests.exceptions import RequestException

from utils import utc_date
from . import Generic, Issue, status


# Reference: https://try.gitea.io/api/swagger
class MyGitea(Generic):
    """
    Gitea
    """

    def __init__(self, url: str, creds: dict):
        super().__init__(url, token=creds.get("token"))
        self.issue_api_url = f"{self.url}/api/v1/repos/{{repo}}/issues/{{issue}}"
        self.issue_web_url = f"{self.url}/{{repo}}/issues/{{issue}}"
        self.pr_api_url = f"{self.url}/api/v1/repos/{{repo}}/pulls/{{issue}}"
        self.pr_web_url = f"{self.url}/{{repo}}/pulls/{{issue}}"

    def _get_user_issues(self, query: dict[str, Any]) -> list[Issue]:
        query["state"] = "open"
        query["limit"] = 1
        try:
            issues = self._get_paginated(
                f"{self.url}/api/v1/repos/issues/search",
                params=query,
            )
        except RequestException as exc:
            logging.error("Gitea: %s: get_user_issues(): %s", self.url, exc)
            return []
        return [
            self._to_issue(issue, is_pr=bool(issue["pull_request"])) for issue in issues
        ]

    def get_user_issues(self) -> list[Issue]:
        queries = [
            {"assigned": True},
            {"created": True},
            {"mentioned": True},
            {"reviewed": True},
            {"review_requested": True},
        ]
        return self._get_user_issues_x(queries)

    def _to_issue(self, info: Any, **kwargs) -> Issue:
        repo = kwargs.get("repo", info["repository"]["full_name"])
        is_pr = bool(kwargs.get("is_pr"))
        mark = "!" if is_pr else "#"
        return Issue(
            tag=f'{self.tag}#{repo}{mark}{info["number"]}',
            url=info["html_url"],
            assignee=info["assignee"]["login"] if info["assignee"] else "none",
            creator=info["user"]["login"],
            created=utc_date(info["created_at"]),
            updated=utc_date(info["updated_at"]),
            status=status(info["state"]),
            title=info["title"],
            raw=info,
        )
