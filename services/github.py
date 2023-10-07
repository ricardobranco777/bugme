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

    def get_issue(self, issue_id: str = "", **kwargs) -> Issue | None:
        """
        Get Github issue
        """
        repo = kwargs.pop("repo")
        try:
            info = self.client.get_repo(repo, lazy=True).get_issue(int(issue_id))
        except (GithubException, RequestException) as exc:
            if getattr(exc, "status", None) == 404:
                return self._not_found(
                    url=f"{self.url}/{repo}/issues/{issue_id}",
                    tag=f"{self.tag}#{repo}#{issue_id}",
                )
            logging.error("Github: get_issue(%s, %s): %s", repo, issue_id, exc)
            return None
        return self._to_issue(info)

    def _to_issue(self, info: Any) -> Issue:
        return Issue(
            tag=f"{self.tag}#{info.repository.full_name}#{info.number}",
            url=info.html_url,
            assignee=info.assignee.login if info.assignee else "none",
            creator=info.user.login,
            created=utc_date(info.created_at),
            updated=utc_date(info.updated_at),
            status=status(info.state),
            title=info.title,
            raw=info.raw_data,
        )
