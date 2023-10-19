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

    def __init__(self, url: str, creds: dict):
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
                raise
            self._username = response.json()["username"]
        return self._username

    def _get_paginated(
        self, url: str, params: dict[str, str], key: str, next_key: str
    ) -> list[dict]:
        got = self.session.get(url, params=params)
        got.raise_for_status()
        data = got.json()
        entries = data[key]
        while data[next_key]["next"]:
            got = self.session.get(data[next_key]["next"], params=params)
            got.raise_for_status()
            data = got.json()
            entries.extend(data[key])
        return entries

    def _get_issues(self, username: str, **params) -> list[dict]:
        if params["assignee"]:
            key = "issues_assigned"
            next_key = "pagination_issues_assigned"
        else:
            key = "issues_created"
            next_key = "pagination_issues_created"
        url = f"{self.url}/api/0/user/{username}/issues"
        return self._get_paginated(url, params=params, key=key, next_key=next_key)

    def _get_pullrequests(
        self, username: str, created: bool = False, **params
    ) -> list[dict]:
        pr_type = "filed" if created else "actionable"
        url = f"{self.url}/api/0/user/{username}/requests/{pr_type}"
        return self._get_paginated(
            url, params=params, key="requests", next_key="pagination"
        )

    def get_assigned(
        self, username: str = "", pull_requests: bool = False, state: str = "Open", **_
    ) -> list[Issue] | None:
        """
        Get assigned issues
        """
        username = username or self.username
        filters = {
            "status": state,
        }
        try:
            if pull_requests:
                issues = self._get_pullrequests(username, created=False, **filters)
            else:
                issues = self._get_issues(username, assignee=1, author=0, **filters)
        except RequestException as exc:
            logging.error("Pagure: %s: get_assigned(%s): %s", self.url, username, exc)
            return None
        return [self._to_issue(issue, is_pr=pull_requests) for issue in issues]

    def get_created(
        self, username: str = "", pull_requests: bool = False, state: str = "Open", **_
    ) -> list[Issue] | None:
        """
        Get created issues
        """
        username = username or self.username
        filters = {
            "status": state,
        }
        try:
            if pull_requests:
                issues = self._get_pullrequests(username, created=True, **filters)
            else:
                issues = self._get_issues(username, assignee=0, author=1, **filters)
        except RequestException as exc:
            logging.error("Pagure: %s: get_created(%s): %s", self.url, username, exc)
            return None
        return [self._to_issue(issue, is_pr=pull_requests) for issue in issues]

    def get_user_issues(  # pylint: disable=too-many-arguments
        self,
        username: str = "",
        assigned: bool = False,
        created: bool = False,
        involved: bool = True,
        state: str = "Open",
        **_,
    ) -> list[Issue] | None:
        """
        Get user issues
        """
        if involved:
            assigned = created = True
        issues: list[Issue] = []
        if assigned:
            for is_pr in (False, True):
                more = self.get_assigned(username, pull_requests=is_pr, state=state)
                if more is None:
                    return None
                issues.extend(more)
        if created:
            for is_pr in (False, True):
                more = self.get_created(username, pull_requests=is_pr, state=state)
                if more is None:
                    return None
                issues.extend(more)
        return list(set(issues))

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
