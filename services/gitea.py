"""
Gitea
"""

import logging
from typing import Any

from requests.utils import parse_header_links
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

    def _get_paginated(self, url: str, params: dict[str, str]) -> list[dict]:
        entries: list[dict] = []
        while True:
            got = self.session.get(url, params=params)
            got.raise_for_status()
            entries.extend(got.json())
            # Find the link with "rel" set to "next"
            if "Link" in got.headers:
                links = parse_header_links(got.headers["Link"])
                next_link = next(
                    (link["url"] for link in links if link.get("rel") == "next"), None
                )
                if next_link:
                    url = next_link
                    params = {}
                    continue
            break
        return entries

    # Not possible to filter issues by username because of:
    # https://github.com/go-gitea/gitea/issues/25979

    def _get_issues(  # pylint: disable=too-many-arguments
        self,
        assigned: bool = False,
        created: bool = False,
        closed: bool = False,
        pull_requests: bool = False,
    ) -> list[Issue]:
        params: dict[str, Any] = {
            "state": "closed" if closed else "open",
            "type": "pulls" if pull_requests else "issues",
        }
        # Missing: mentioned, review_requested & reviewed
        if assigned:
            params["assigned"] = True
        if created:
            params["created"] = True
        issues = self._get_paginated(
            f"{self.url}/api/v1/repos/issues/search", params=params
        )
        return [self._to_issue(issue, is_pr=pull_requests) for issue in issues]

    def get_assigned(
        self, username: str = "", pull_requests: bool = False, state: str = "open", **_
    ) -> list[Issue] | None:
        """
        Get assigned issues
        """
        username = ""
        try:
            return self._get_issues(
                assigned=True, closed=bool(state != "open"), pull_requests=pull_requests
            )
        except RequestException as exc:
            logging.error("Gitea: %s: get_assigned(%s): %s", self.url, username, exc)
        return None

    def get_created(
        self, username: str = "", pull_requests: bool = False, state: str = "open", **_
    ) -> list[Issue] | None:
        """
        Get created issues
        """
        username = ""
        try:
            return self._get_issues(
                created=True, closed=bool(state != "open"), pull_requests=pull_requests
            )
        except RequestException as exc:
            logging.error("Gitea: %s: get_created(%s): %s", self.url, username, exc)
        return None

    def get_user_issues(  # pylint: disable=too-many-arguments
        self,
        username: str = "",
        assigned: bool = False,
        created: bool = False,
        involved: bool = True,
        **kwargs,
    ) -> list[Issue] | None:
        """
        Get user issues
        """
        return self._get_user_issues4(
            username=username,
            assigned=assigned,
            created=created,
            involved=involved,
            **kwargs,
        )

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
