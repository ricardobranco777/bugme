"""
Github
"""

import logging
import os
from typing import Any

from github import Auth, Github, GithubException
from requests.exceptions import RequestException

from utils import utc_date
from . import Service, Issue, status, VERSION


# Reference:
# https://docs.github.com/en/search-github/searching-on-github/searching-issues-and-pull-requests
class MyGithub(Service):
    """
    Github
    """

    def __init__(self, url: str, creds: dict) -> None:
        super().__init__(url)
        token = None
        for key in ("login_or_token", "token"):
            if key in creds:
                token = creds.pop(key)
        options: dict[str, Any] = {
            "auth": Auth.Token(token=token),
            "user_agent": f"bugme/{VERSION}",
        }
        options |= creds
        self.client = Github(**options)
        self.tag = "gh"
        if os.getenv("DEBUG"):
            logging.getLogger("github").setLevel(logging.DEBUG)

    def close(self) -> None:
        try:
            self.client.close()
        except (AttributeError, GithubException):
            pass

    def get_user_issues(self) -> list[Issue]:
        try:
            user = self.client.get_user()
            filters = f"state:open involves:{user.login}"
            issues = self.client.search_issues(filters)
        except (GithubException, RequestException) as exc:
            logging.error("Github: get_user_issues(): %s", exc)
            return []

        return [
            self._to_issue(
                issue, is_pr=bool(issue.html_url.rsplit("/", 2)[1] == "pull")
            )
            for issue in issues
        ]

    def get_issue(self, issue_id: str = "", **kwargs) -> Issue | None:
        repo: str = kwargs.pop("repo")
        is_pr: bool = kwargs.pop("is_pr")
        mark = "!" if is_pr else "#"
        info: Any
        try:
            git_repo = self.client.get_repo(repo, lazy=True)
            if is_pr:
                info = git_repo.get_pull(int(issue_id))
            else:
                info = git_repo.get_issue(int(issue_id))
        except (GithubException, RequestException) as exc:
            if getattr(exc, "status", None) == 404:
                issuepr = "pull" if is_pr else "issues"
                return self._not_found(
                    url=f"{self.url}/{repo}/{issuepr}/{issue_id}",
                    tag=f"{self.tag}#{repo}{mark}{issue_id}",
                )
            logging.error("Github: get_issue(%s, %s): %s", repo, issue_id, exc)
            return None
        return self._to_issue(info, repo, is_pr)

    def _to_issue(self, info: Any, repo: str = "", is_pr: bool = False) -> Issue:
        repo = repo or info.repository.full_name
        mark = "!" if is_pr else "#"
        return Issue(
            tag=f"{self.tag}#{repo}{mark}{info.number}",
            url=info.html_url,
            assignee=info.assignee.login if info.assignee else "none",
            creator=info.user.login,
            created=utc_date(info.created_at),
            updated=utc_date(info.updated_at),
            status=status(info.state),
            title=info.title,
            raw=info.raw_data,
        )
