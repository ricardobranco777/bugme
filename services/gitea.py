"""
Gitea
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from requests.utils import parse_header_links
from requests.exceptions import RequestException

from utils import utc_date
from . import Generic, Issue, status


# Reference: https://try.gitea.io/api/swagger
# Not possible to filter issues because of:
# https://github.com/go-gitea/gitea/issues/25979
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

    def _get_issues(  # pylint: disable=too-many-arguments
        self,
        issue_type: str = "issues",
        assigned: bool = False,
        created: bool = False,
        involved: bool = False,
        closed: bool = False,
    ) -> list[Issue]:
        params: dict[str, Any] = {
            "state": "closed" if closed else "open",
            "type": issue_type,
        }
        # Missing: review_requested & reviewed
        if assigned:
            params["assigned"] = True
        if created:
            params["created"] = True
        if involved:
            params["mentioned"] = True
        issues = self._get_paginated(
            f"{self.url}/api/v1/repos/issues/search", params=params
        )
        return [
            self._to_issue(issue, is_pr=bool(issue_type == "pulls")) for issue in issues
        ]

    def get_assigned(
        self, username: str = "", state: str = "open", **_
    ) -> list[Issue] | None:
        """
        Get assigned issues
        """
        return self.get_user_issues(
            username, assigned=True, involved=False, state=state
        )

    def get_created(
        self, username: str = "", state: str = "open", **_
    ) -> list[Issue] | None:
        """
        Get created issues
        """
        return self.get_user_issues(username, created=True, involved=False, state=state)

    def get_user_issues(  # pylint: disable=too-many-arguments
        self,
        username: str = "",
        assigned: bool = False,
        created: bool = False,
        involved: bool = True,
        closed: bool = False,
        **_,
    ) -> list[Issue] | None:
        """
        Get user issues
        """
        kwargs = {"closed": closed}
        if assigned:
            kwargs["assigned"] = True
        elif created:
            kwargs["created"] = True
        elif involved:
            kwargs["assigned"] = True
            kwargs["created"] = True
            # kwargs["involved"] = True
        all_issues: list[Issue] = []

        def get_issues(issue_type: str) -> list[Issue] | None:
            try:
                return self._get_issues(issue_type=issue_type, **kwargs)
            except RequestException as exc:
                logging.error(
                    "Gitea: %s: get_user_issues(%s): %s", self.url, username, exc
                )
            return None

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = executor.map(get_issues, ("issues", "pulls"))
            for result in results:
                if result is None:
                    return None
                all_issues.extend(result)

        return all_issues

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
