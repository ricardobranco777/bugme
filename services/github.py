"""
Github
"""

import logging
import os
from typing import Any

from github import Github, GithubException  # , Auth
from requests.exceptions import RequestException

from utils import utc_date
from . import Service, Issue, status


# Reference:
# https://docs.github.com/en/search-github/searching-on-github/searching-issues-and-pull-requests
class MyGithub(Service):
    """
    Github
    """

    def __init__(self, url: str, creds: dict):
        super().__init__(url)
        # NOTE: Uncomment when latest PyGithub is published on Tumbleweed
        # auth = Auth.Token(**creds)
        # self.client = Github(auth=auth)
        self.tag = "gh"
        self.client = Github(**creds)
        if os.getenv("DEBUG"):
            logging.getLogger("github").setLevel(logging.DEBUG)

    def __del__(self):
        try:
            self.client.close()
        except (AttributeError, GithubException):
            pass

    def get_assigned(
        self, username: str = "", state: str = "open", **_
    ) -> list[Issue] | None:
        """
        Get assigned issues
        """
        return self.get_user_issues(
            username, assigned=True, involved=False, state=state
        )

    def get_created(
        self, username: str = "", state: str = "open", **_
    ) -> list[Issue] | None:
        """
        Get created issues
        """
        return self.get_user_issues(username, created=True, involved=False, state=state)

    def get_user_issues(  # pylint: disable=too-many-arguments
        self,
        username: str = "",
        assigned: bool = False,
        created: bool = False,
        involved: bool = True,
        state: str = "open",
        **_,
    ) -> list[Issue] | None:
        """
        Get user issues
        """
        base_filters = f"state:{state} "
        if involved:
            base_filters += "involves"
        elif assigned:
            base_filters += "assignee"
        elif created:
            base_filters += "author"
        issues: list[Issue] = []
        try:
            user = (
                self.client.get_user(username) if username else self.client.get_user()
            )
            base_filters = f"{base_filters}:{user.login}"
            for issue_type in ("pr", "issue"):
                filters = f"{base_filters} type:{issue_type}"
                more = self.client.search_issues(filters)
                issues.extend(
                    self._to_issue(issue, is_pr=bool(issue_type == "pr"))
                    for issue in more
                )
        except (GithubException, RequestException) as exc:
            logging.error("Github: get_user_issues(%s): %s", username, exc)
            return None
        return issues

    def get_issue(self, issue_id: str = "", **kwargs) -> Issue | None:
        """
        Get Github issue
        """
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
