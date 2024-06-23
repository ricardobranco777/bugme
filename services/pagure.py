"""
Pagure
"""

import logging
from typing import Any

from requests.exceptions import RequestException

from utils import utc_date
from . import Generic, Issue, status


# Reference: https://pagure.io/api/0/
class MyPagure(Generic):
    """
    Pagure
    """

    def __init__(self, url: str, creds: dict) -> None:
        super().__init__(url, token=creds.get("token"))
        self.issue_api_url = f"{self.url}/api/0/{{repo}}/issue/{{issue}}"
        self.issue_web_url = f"{self.url}/{{repo}}/issue/{{issue}}"
        self.pr_api_url = f"{self.url}/api/0/{{repo}}/pull-request/{{issue}}"
        self.pr_web_url = f"{self.url}/{{repo}}/pull-request/{{issue}}"
        self._username: str | None = None

    @property
    def username(self) -> str:
        """
        Get username
        """
        if self._username is None:
            try:
                response = self.session.post(f"{self.url}/api/0/-/whoami", timeout=10)
                response.raise_for_status()
            except RequestException as exc:
                logging.error("Pagure: %s: whoami(): %s", self.url, exc)
                return ""
            self._username = response.json()["username"]
        return self._username

    def _get_issues(self, **params) -> list[dict]:
        if params["assignee"]:
            data_key = "issues_assigned"
            next_key = "pagination_issues_assigned.next"
            last_key = "pagination_issues_assigned.last"
        else:
            data_key = "issues_created"
            next_key = "pagination_issues_created.next"
            last_key = "pagination_issues_created.last"
        url = f"{self.url}/api/0/user/{self.username}/issues"
        return self._get_paginated(
            url, params=params, data_key=data_key, next_key=next_key, last_key=last_key
        )

    def _get_pullrequests(self, created: bool = False, **params) -> list[dict]:
        pr_type = "filed" if created else "actionable"
        url = f"{self.url}/api/0/user/{self.username}/requests/{pr_type}"
        data_key = "requests"
        next_key = "pagination.next"
        last_key = "pagination.last"
        return self._get_paginated(
            url, params=params, data_key=data_key, next_key=next_key, last_key=last_key
        )

    def _get_user_issues(self, query: dict[str, Any]) -> list[Issue]:
        query["per_page"] = 100
        pull_requests = query.pop("pull_requests")
        try:
            if pull_requests:
                issues = self._get_pullrequests(**query)
            else:
                issues = self._get_issues(**query)
        except RequestException as exc:
            logging.error("Pagure: %s: get_user_issues(): %s", self.url, exc)
            return []
        return [self._to_issue(issue, is_pr=pull_requests) for issue in issues]

    def get_user_issues(self) -> list[Issue]:
        queries = [
            {"pull_requests": False, "assignee": 0, "author": 1},
            {"pull_requests": False, "assignee": 1, "author": 0},
            {"pull_requests": True, "created": True},
            {"pull_requests": True, "created": False},
        ]
        return self._get_user_issues_x(queries)

    def _to_issue(self, info: Any, **kwargs) -> Issue:
        repo = kwargs.get("repo", "") or info["project"]["fullname"]
        is_pr = bool(kwargs.get("is_pr"))
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
