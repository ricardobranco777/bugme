"""
Gitlab
"""

import logging
import os
from typing import Any
from urllib.parse import urlparse

from gitlab import Gitlab
from gitlab.exceptions import GitlabError
from requests.exceptions import RequestException

from utils import utc_date
from . import Service, Issue, debugme, status, VERSION


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
            "user_agent": f"bugme/{VERSION}",
        }
        options |= creds
        hostname = str(urlparse(self.url).hostname)
        self.tag: str = "gl" if hostname == "gitlab.com" else self.tag
        self.client = Gitlab(url=self.url, **options)
        if os.getenv("DEBUG"):
            self.client.session.hooks["response"].append(debugme)
        try:
            self.client.auth()
        except (GitlabError, RequestException):
            pass

    def close(self):
        try:
            self.client.session.close()
        except (AttributeError, GitlabError):
            pass

    def _get_user_issues(self, query: dict[str, Any]) -> list[Issue]:
        issues: list[Any] = []
        query |= {
            "all": True,  # No pagination
            "state": "opened",
        }
        pull_requests = query.pop("pull_requests")
        try:
            if pull_requests:
                issues = list(self.client.mergerequests.list(**query))
            else:
                issues = list(self.client.issues.list(**query))
        except (GitlabError, RequestException) as exc:
            logging.error("Gitlab: %s: get_user_issues(): %s", self.url, exc)
            return []
        return [self._to_issue(issue) for issue in issues]

    def get_user_issues(self) -> list[Issue]:
        try:
            user = self.client.user
            if user is None:
                return []
        except (GitlabError, RequestException) as exc:
            logging.error("Gitlab: %s: get_user_issues(): %s", self.url, exc)
            return []
        queries = [
            {"assignee_id": user.id, "pull_requests": False},
            {"assignee_id": user.id, "pull_requests": True},
            {"author_id": user.id, "pull_requests": False},
            {"author_id": user.id, "pull_requests": True},
            {"reviewer_id": user.id, "pull_requests": True},
        ]
        return self._get_user_issues_x(queries)

    def get_issue(self, issue_id: str = "", **kwargs) -> Issue | None:
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
