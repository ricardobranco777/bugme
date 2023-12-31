"""
Launchpad
"""

import logging
from typing import Any
from urllib.parse import urlparse

from requests.exceptions import RequestException

from utils import utc_date
from . import Generic, Issue, status


def user(string: str) -> str:
    """
    Return user
    """
    return string.rsplit("~", 1)[1]


# Reference: https://launchpad.net/+apidoc/1.0.html
class MyLaunchpad(Generic):
    """
    Launchpad
    """

    def __init__(self, url: str, creds: dict):
        super().__init__(url, token=creds.get("token"))
        self.issue_api_url = "https://api.launchpad.net/1.0/{repo}/+bug/{issue}"
        self.issue_web_url = f"{self.url}/{{repo}}/+bug/{{issue}}"
        self.tag = "lp"
        self.username = creds.get("username", "")

    def _get_user_issues(self, query: dict[str, Any]) -> list[Issue]:
        query["ws.op"] = "searchTasks"
        try:
            got = self.session.get("https://api.launchpad.net/1.0/bugs", params=query)
            got.raise_for_status()
            issues = got.json()["entries"]
        except RequestException as exc:
            logging.error("Launchpad: get_user_issues(): %s", exc)
            return []
        return [self._to_issue(issue) for issue in issues]

    def get_user_issues(self) -> list[Issue]:
        user_url = f"https://api.launchpad.net/1.0/~{self.username}"
        queries = [
            {"assignee": user_url},
            {"bug_reporter": user_url},
        ]
        return self._get_user_issues_x(queries)

    def get_issue(self, issue_id: str = "", **kwargs) -> Issue | None:
        if not kwargs.get("repo"):
            try:
                response = self.session.head(
                    f"{self.url}/bugs/{issue_id}", allow_redirects=True
                )
                response.raise_for_status()
            except RequestException as exc:
                try:
                    if exc.response.status_code == 404:  # type: ignore
                        return self._not_found(
                            url=f"{self.url}/bugs/{issue_id}",
                            tag=f"{self.tag}#{issue_id}",
                        )
                except AttributeError:
                    pass
                logging.error("Launchpad: get_issue(%s): %s", issue_id, exc)
                return None
            url = urlparse(response.url)
            kwargs["repo"], *_ = url.path.rsplit("/", 2)
        return super().get_issue(issue_id, **kwargs)

    def _extra(self, issue_id: str) -> dict:
        try:
            got = self.session.get(f"https://api.launchpad.net/1.0/bugs/{issue_id}")
            got.raise_for_status()
        except RequestException as exc:
            logging.error("Launchpad: %s: %s", issue_id, exc)
            return {}
        return got.json()

    def _to_issue(self, info: Any, **kwargs) -> Issue:
        issue_id = info["web_link"].rsplit("/", 1)[-1]
        extra = self._extra(issue_id)
        info["extra"] = extra
        return Issue(
            tag=f"{self.tag}#{issue_id}",
            url=info["web_link"],
            assignee=user(info["assignee_link"]) if info["assignee_link"] else "none",
            creator=user(info["owner_link"]),
            created=utc_date(info["date_created"]),
            updated=utc_date(info["extra"].get("date_last_updated")),
            status=status(info["status"]),
            title=info["title"],
            raw=info,
        )
