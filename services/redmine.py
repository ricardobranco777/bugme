"""
Redmine
"""

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from redminelib import Redmine  # type: ignore
from redminelib.exceptions import BaseRedmineError, ResourceNotFoundError  # type: ignore
from requests.exceptions import RequestException

from utils import utc_date
from . import Service, Issue, debugme, status


# Reference: https://www.redmine.org/projects/redmine/wiki/Rest_api
class MyRedmine(Service):
    """
    Redmine
    """

    def __init__(self, url: str, creds: dict):
        super().__init__(url)
        options = {
            "raise_attr_exception": False,
        }
        options |= creds
        self.client = Redmine(url=self.url, **options)
        if os.getenv("DEBUG"):
            self.client.engine.session.hooks["response"].append(debugme)

    def __del__(self):
        try:
            self.client.engine.session.close()
        except AttributeError:
            pass

    def get_assigned(self, username: str = "me", **_) -> list[Issue] | None:
        """
        Get assigned issues
        """
        try:
            user = self.client.user.get(username)
            issues = self.client.issue.filter(assigned_to_id=user.id)
        except (BaseRedmineError, RequestException) as exc:
            logging.error("Redmine: %s: get_assigned(%s): %s", self.url, username, exc)
            return None
        return [self._to_issue(issue) for issue in issues]

    def get_created(self, username: str = "me", **_) -> list[Issue] | None:
        """
        Get created issues
        """
        try:
            user = self.client.user.get(username)
            issues = self.client.issue.filter(author_id=user.id)
        except (BaseRedmineError, RequestException) as exc:
            logging.error("Redmine: %s: get_created(%s): %s", self.url, username, exc)
            return None
        return [self._to_issue(issue) for issue in issues]

    def get_user_issues(  # pylint: disable=too-many-arguments
        self,
        username: str = "me",
        assigned: bool = False,
        created: bool = False,
        involved: bool = True,
        **_,
    ) -> list[Issue] | None:
        """
        Get user issues
        """
        if involved:
            assigned = created = True
        all_issues: list[Issue] = []

        def get_assigned_issues() -> list[Issue] | None:
            return self.get_assigned(username)

        def get_created_issues() -> list[Issue] | None:
            return self.get_created(username)

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = []
            if assigned:
                futures.append(executor.submit(get_assigned_issues))
            if created:
                futures.append(executor.submit(get_created_issues))
            for future in futures:
                issues = future.result()
                if issues is None:
                    return None
                all_issues.extend(issues)

        return list(set(all_issues))

    def get_issue(self, issue_id: str = "", **kwargs) -> Issue | None:
        """
        Get Redmine ticket
        """
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
