"""
Gitlab
"""

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from urllib.parse import urlparse

from gitlab import Gitlab
from gitlab.exceptions import GitlabError
from requests.exceptions import RequestException

from utils import utc_date
from . import Service, Issue, debugme, status


# References:
# https://docs.gitlab.com/ee/api/issues.html
# https://docs.gitlab.com/ee/api/merge_requests.html
class MyGitlab(Service):
    """
    Gitlab
    """

    def __init__(self, url: str, creds: dict):
        super().__init__(url)
        options: dict[str, Any] = {
            "ssl_verify": os.environ.get("REQUESTS_CA_BUNDLE", True),
        }
        options |= creds
        hostname = str(urlparse(self.url).hostname)
        self.tag: str = "gl" if hostname == "gitlab.com" else self.tag
        self.client = Gitlab(url=self.url, **options)
        if os.getenv("DEBUG"):
            self.client.session.hooks["response"].append(debugme)
        try:
            self.client.auth()
        except (GitlabError, RequestException) as exc:
            logging.error("Gitlab: %s: %s", self.url, exc)

    def __del__(self):
        try:
            self.client.__exit__(None, None, None)
        except (AttributeError, GitlabError):
            pass

    def get_assigned(
        self, username: str = "", pull_requests: bool = False, state: str = "Open", **_
    ) -> list[Issue] | None:
        """
        Get assigned issues
        """
        filters = {
            "all": True,  # No pagination
            "state": state,
        }
        issues: list[Any] = []
        try:
            if username:
                user = self.client.users.list(username=username)[0]  # type: ignore
            else:
                user = self.client.user
            if pull_requests:
                issues = list(
                    self.client.mergerequests.list(assignee_id=user.id, **filters)
                )
            else:
                issues = list(self.client.issues.list(assignee_id=user.id, **filters))
        except (GitlabError, RequestException) as exc:
            logging.error("Gitlab: %s: get_assigned(%s): %s", self.url, username, exc)
            return None
        return [self._to_issue(issue) for issue in issues]

    def get_created(
        self, username: str = "", pull_requests: bool = False, state: str = "Open", **_
    ) -> list[Issue] | None:
        """
        Get created issues
        """
        filters = {
            "all": True,  # No pagination
            "state": state,
        }
        issues: list[Any] = []
        try:
            if username:
                user = self.client.users.list(username=username)[0]  # type: ignore
            else:
                user = self.client.user
            if pull_requests:
                issues = list(self.client.mergerequests.list(author=user.id, **filters))
            else:
                issues = list(self.client.issues.list(author=user.id, **filters))
        except (GitlabError, RequestException) as exc:
            logging.error("Gitlab: %s: get_created(%s): %s", self.url, username, exc)
            return None
        return [self._to_issue(issue) for issue in issues]

    def get_user_issues(  # pylint: disable=too-many-arguments
        self,
        username: str = "",
        assigned: bool = False,
        created: bool = False,
        involved: bool = True,
        state: str = "opened",
        **_,
    ) -> list[Issue] | None:
        """
        Get user issues
        """
        if involved:
            assigned = created = True
        issues: list[Issue] = []

        def get_issues(is_pr: bool, is_assigned: bool):
            if is_assigned:
                more = self.get_assigned(username, pull_requests=is_pr, state=state)
            else:
                more = self.get_created(username, pull_requests=is_pr, state=state)
            return more

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            if assigned:
                futures.append(
                    executor.submit(get_issues, False, True)
                )  # Get assigned non-PR issues
                futures.append(
                    executor.submit(get_issues, True, True)
                )  # Get assigned PR issues
            if created:
                futures.append(
                    executor.submit(get_issues, False, False)
                )  # Get created non-PR issues
                futures.append(
                    executor.submit(get_issues, True, False)
                )  # Get created PR issues
            for future in futures:
                more = future.result()
                if more is None:
                    return None
                issues.extend(more)

        return list(set(issues))

    def get_issue(self, issue_id: str = "", **kwargs) -> Issue | None:
        """
        Get Gitlab issue
        """
        repo: str = kwargs.pop("repo")
        is_pr: bool = kwargs.pop("is_pr")
        mark = "!" if is_pr else "#"
        info: Any
        try:
            git_repo = self.client.projects.get(repo, lazy=True)
            if is_pr:
                info = git_repo.mergerequests.get(issue_id)
            else:
                info = git_repo.issues.get(issue_id)
        except (GitlabError, RequestException) as exc:
            if getattr(exc, "response_code", None) == 404:
                issuepr = "merge_requests" if is_pr else "issues"
                return self._not_found(
                    url=f"{self.url}/{repo}/-/{issuepr}/{issue_id}",
                    tag=f"{self.tag}#{repo}{mark}{issue_id}",
                )
            logging.error(
                "Gitlab: %s: get_issue(%s, %s): %s", self.url, repo, issue_id, exc
            )
            return None
        return self._to_issue(info)

    def _to_issue(self, info: Any) -> Issue:
        return Issue(
            tag=f'{self.tag}#{info.references["full"]}',
            url=info.web_url,
            assignee=info.assignee["username"] if info.assignee else "none",
            creator=info.author["username"],
            created=utc_date(info.created_at),
            updated=utc_date(info.updated_at),
            status=status(info.state),
            title=info.title,
            raw=info.asdict(),
        )
