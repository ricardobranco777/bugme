"""
Jira
"""

import logging
import os
from typing import Any

from atlassian import Jira  # type: ignore
from atlassian.errors import ApiError  # type: ignore
from requests.exceptions import RequestException

from utils import utc_date
from . import Service, Issue, debugme, status


# References:
# https://support.atlassian.com/jira-service-management-cloud/docs/jql-functions/
class MyJira(Service):
    """
    Jira
    """

    def __init__(self, url: str, creds: dict):
        super().__init__(url)
        self.client = Jira(url=self.url, **creds)
        if os.getenv("DEBUG"):
            self.client.session.hooks["response"].append(debugme)

    def close(self):
        try:
            self.client.session.close()
        except AttributeError:
            pass

    def _get_issues(self, filters: str) -> list[dict]:
        filters = f"{filters} AND resolution IS EMPTY"
        data = self.client.jql(filters)
        issues = data["issues"]
        while len(issues) < data["total"]:
            data = self.client.jql(filters, start=len(issues))
            issues.extend(data["issues"])
        return issues

    def get_user_issues(self) -> list[Issue]:
        filters = "watcher = currentUser()"
        try:
            issues = self._get_issues(filters)
        except (ApiError, RequestException) as exc:
            logging.error("Jira: %s: get_user_issues(): %s", self.url, exc)
            return []
        return [self._to_issue(issue) for issue in issues]

    def get_issue(self, issue_id: str = "", **kwargs) -> Issue | None:
        try:
            info = self.client.issue(issue_id)
        except (ApiError, RequestException) as exc:
            try:
                if exc.response.status_code == 404:  # type: ignore
                    return self._not_found(
                        url=f"{self.url}/browse/{issue_id}",
                        tag=f"{self.tag}#{issue_id}",
                    )
            except AttributeError:
                pass
            logging.error("Jira: %s: get_issue(%s): %s", self.url, issue_id, exc)
            return None
        return self._to_issue(info)

    def _to_issue(self, info: Any) -> Issue:
        return Issue(
            tag=f"{self.tag}#{info['key']}",
            url=f"{self.url}/browse/{info['key']}",
            assignee=info["fields"]["assignee"]["name"]
            if info["fields"].get("assignee")
            else "none",
            creator=info["fields"]["creator"]["name"],
            created=utc_date(info["fields"]["created"]),
            updated=utc_date(info["fields"]["updated"]),
            status=status(info["fields"]["status"]["name"]),
            title=info["fields"]["summary"],
            raw=info,
        )
