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
from . import Service, Issue, debugme, status


# Reference: https://bugzilla.readthedocs.io/en/latest/api/index.html#apis
class MyBugzilla(Service):
    """
    Bugzilla
    """

    def __init__(self, url: str, creds: dict):
        super().__init__(url)
        options = {
            "force_rest": True,
            "sslverify": os.environ.get("REQUESTS_CA_BUNDLE", True),
        }
        options |= creds
        try:
            self.client = Bugzilla(self.url, **options)
        except (BugzillaError, RequestException) as exc:
            logging.error("Bugzilla: %s: %s", self.url, exc)
        if os.getenv("DEBUG"):
            self.client._session._session.hooks["response"].append(debugme)

    def __del__(self):
        try:
            self.client.disconnect()
        except (AttributeError, BugzillaError):
            pass

    def get_user_issues(  # pylint: disable=too-many-arguments
        self,
        username: str = "",
        assigned: bool = True,
        created: bool = True,
        involved: bool = True,
        closed: bool = False,
        **_,
    ) -> list[Issue] | None:
        """
        Get user issues
        """
        if involved:
            assigned = created = True
        username = username or self.client.user
        issues = []
        try:
            user = self.client.getuser(username)
            if assigned:
                issues = self.client.query({"assigned_to": user.email})
            found_ids = {i.id for i in issues}
            if created:
                issues.extend(
                    issue
                    for issue in self.client.query({"reporter": user.email})
                    if issue.id not in found_ids
                )
        except (AttributeError, BugzillaError, RequestException) as exc:
            logging.error(
                "Bugzilla: %s: get_user_issues(%s): %s", self.url, username, exc
            )
            return None
        if not closed:
            issues = [issue for issue in issues if issue.is_open]
        return [self._to_issue(issue) for issue in issues]

    def get_issue(self, issue_id: str = "", **kwargs) -> Issue | None:
        """
        Get Bugzilla issue
        """
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
        """
        Get Bugzilla issues
        """
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
                url=f"{self.url}/show_bug.cgi?id={issue['issue_id']}",
                tag=f"{self.tag}#{issue['issue_id']}",
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
