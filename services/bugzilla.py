"""
Bugzilla
"""

import logging
import os
from typing import Any

from bugzilla import Bugzilla  # type: ignore
from bugzilla.exceptions import BugzillaError  # type: ignore
from requests.exceptions import RequestException

from utils import utc_date
from . import Service, Issue, debugme, status, VERSION


# Reference: https://bugzilla.readthedocs.io/en/latest/api/index.html#apis
class MyBugzilla(Service):
    """
    Bugzilla
    """

    def __init__(self, url: str, creds: dict) -> None:
        super().__init__(url)
        options = {
            # "force_rest": True,
            "sslverify": os.environ.get("REQUESTS_CA_BUNDLE", True),
        }
        try:
            path = creds.pop("path")
        except KeyError:
            path = ""
        options |= creds
        try:
            self.client = Bugzilla(f"{self.url}{path}", **options)
        except (BugzillaError, RequestException) as exc:
            logging.error("Bugzilla: %s: %s", self.url, exc)
        self.client._session._session.headers["User-Agent"] = f"bugme/{VERSION}"
        if os.getenv("DEBUG"):
            self.client._session._session.hooks["response"].append(debugme)
        if path:
            self.url = f"{self.url}/bugzilla"

    def close(self) -> None:
        try:
            self.client.disconnect()
        except (AttributeError, BugzillaError):
            pass

    def _get_user_issues(self, query: dict[str, Any]) -> list[Issue]:
        try:
            issues = self.client.query(query)
        except (AttributeError, BugzillaError, RequestException) as exc:
            logging.error("Bugzilla: %s: get_user_issues(): %s", self.url, exc)
            return []
        return [self._to_issue(issue) for issue in issues if issue.is_open]

    def get_user_issues(self) -> list[Issue]:
        try:
            user = self.client.getuser(self.client.user)
        except (AttributeError, BugzillaError, RequestException) as exc:
            logging.error("Bugzilla: %s: get_user_issues(): %s", self.url, exc)
            return []
        queries = [
            {"assigned_to": user.email},
            {"reporter": user.email},
        ]
        return self._get_user_issues_x(queries)

    def get_issue(self, issue_id: str = "", **kwargs) -> Issue | None:
        try:
            return self._to_issue(self.client.getbug(issue_id))
        except IndexError:
            return self._not_found(
                url=f"{self.url}/show_bug.cgi?id={issue_id}",
                tag=f"{self.tag}#{issue_id}",
            )
        except (AttributeError, BugzillaError, RequestException) as exc:
            logging.error("Bugzilla: %s: get_issue(%s): %s", self.url, issue_id, exc)
        return None

    def get_issues(self, issues: list[dict]) -> list[Issue | None]:
        try:
            found = [
                self._to_issue(info)
                for info in self.client.getbugs([issue["issue_id"] for issue in issues])
            ]
        except (AttributeError, BugzillaError, RequestException) as exc:
            logging.error("Bugzilla: %s: get_issues(): %s", self.url, exc)
            return []
        # Bugzilla silently fails on not found issues
        found_ids = {str(issue.raw["id"]) for issue in found}
        not_found = [
            self._not_found(
                tag=f"{self.tag}#{issue['issue_id']}",
                url=f"{self.url}/show_bug.cgi?id={issue['issue_id']}",
            )
            for issue in issues
            if issue["issue_id"] not in found_ids
        ]
        return found + not_found  # type: ignore

    def _to_issue(self, info: Any) -> Issue:
        return Issue(
            tag=f"{self.tag}#{info.id}",
            url=f"{self.url}/show_bug.cgi?id={info.id}",
            assignee=info.assigned_to or "none",
            creator=info.creator,
            created=utc_date(info.creation_time),
            updated=utc_date(info.last_change_time),
            status=status(info.status),
            title=info.summary,
            raw=info.get_raw_data(),
        )
