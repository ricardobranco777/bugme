"""
Redmine
"""

import logging
import os
from typing import Any

from redminelib import Redmine  # type: ignore
from redminelib.exceptions import BaseRedmineError, ResourceNotFoundError  # type: ignore
from requests.exceptions import RequestException

from utils import utc_date
from . import Service, Issue, debugme, status, VERSION


# Reference: https://www.redmine.org/projects/redmine/wiki/Rest_api
class MyRedmine(Service):
    """
    Redmine
    """

    def __init__(self, url: str, creds: dict) -> None:
        super().__init__(url)
        options = {
            "raise_attr_exception": False,
        }
        options |= creds
        self.client = Redmine(url=self.url, **options)
        self.client.engine.session.headers["User-Agent"] = f"bugme/{VERSION}"
        if os.getenv("DEBUG"):
            self.client.engine.session.hooks["response"].append(debugme)

    def close(self) -> None:
        try:
            self.client.engine.session.close()
        except AttributeError:
            pass

    def _get_user_issues(self, query: dict[str, Any]) -> list[Issue]:
        try:
            issues = self.client.issue.filter(**query)
        except (BaseRedmineError, RequestException) as exc:
            logging.error("Redmine: %s: get_user_issues(): %s", self.url, exc)
            return []
        return [self._to_issue(issue) for issue in issues]

    def get_user_issues(self) -> list[Issue]:
        try:
            user = self.client.user.get("me")
        except (BaseRedmineError, RequestException) as exc:
            logging.error("Redmine: %s: get_user_issues(): %s", self.url, exc)
            return []
        queries = [
            {"assigned_to_id": user.id},
            {"author_id": user.id},
        ]
        return self._get_user_issues_x(queries)

    def get_issue(self, issue_id: str = "", **kwargs) -> Issue | None:
        try:
            info = self.client.issue.get(issue_id)
        except ResourceNotFoundError:
            return self._not_found(
                url=f"{self.url}/issues/{issue_id}", tag=f"{self.tag}#{issue_id}"
            )
        except (BaseRedmineError, RequestException) as exc:
            logging.error("Redmine: %s: get_issue(%s): %s", self.url, issue_id, exc)
            return None
        return self._to_issue(info)

    def _to_issue(self, info: Any) -> Issue:
        return Issue(
            tag=f"{self.tag}#{info.id}",
            url=f"{self.url}/issues/{info.id}",
            assignee=info.assigned_to.name if info.assigned_to else "none",
            creator=info.author.name,
            created=utc_date(info.created_on),
            updated=utc_date(info.updated_on),
            status=status(info.status.name),
            title=info.subject,
            raw=info.raw(),
        )
