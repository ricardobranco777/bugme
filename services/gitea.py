"""
Gitea
"""

import logging
from typing import Any
from urllib.parse import urlparse, parse_qs

from concurrent.futures import ThreadPoolExecutor
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

    def _get_paginated(self, url: str, params: dict[str, str] | None) -> list[dict]:
        if params is None:
            params = {}
        if "limit" not in params:
            params["limit"] = "100"
        try:
            got = self.session.get(url, params=params)
            got.raise_for_status()
        except RequestException as exc:
            logging.error("Gitea: %s: Error while fetching page 1: %s", url, exc)
            raise
        entries: list[dict] = got.json()
        if "Link" in got.headers:
            links = parse_header_links(got.headers["Link"])
            last_link = next(
                (link["url"] for link in links if link.get("rel") == "last"), None
            )
            if last_link is not None:
                last_page = int(parse_qs(urlparse(last_link).query)["page"][0])
                entries.extend(self._get_paginated2(url, params, last_page))
        return entries

    # Get pages 2 to last using threads
    def _get_paginated2(
        self, url: str, params: dict[str, str], last_page: int
    ) -> list[dict]:
        entries: list[dict] = []

        def get_page(page: int) -> list[dict]:
            params["page"] = str(page)
            try:
                got = self.session.get(url, params=params)
                got.raise_for_status()
                return got.json()
            except RequestException as exc:
                logging.error(
                    "Gitea: %s: Error while fetching page %d: %s", url, page, exc
                )
            return []

        if last_page == 2:
            return get_page(2)

        with ThreadPoolExecutor(max_workers=min(10, last_page - 1)) as executor:
            pages_to_fetch = range(2, last_page + 1)
            results = executor.map(get_page, pages_to_fetch)
            for result in results:
                entries.extend(result)

        return entries

    def _get_user_issues(self, query: dict[str, Any], **kwargs) -> list[Issue]:
        query["state"] = "open"
        issues = self._get_paginated(
            f"{self.url}/api/v1/repos/issues/search", params=query
        )
        return [
            self._to_issue(issue, is_pr=bool(issue["pull_request"])) for issue in issues
        ]

    def get_user_issues(self, username: str = "", **kwargs) -> list[Issue]:
        # Not possible to filter issues by username because of:
        # https://github.com/go-gitea/gitea/issues/25979
        _ = username
        queries = [
            {"assigned": True},
            {"created": True},
            {"mentioned": True},
            {"reviewed": True},
            {"review_requested": True},
        ]
        return self._get_user_issues_x(queries, **kwargs)

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
