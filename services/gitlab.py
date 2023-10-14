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
from . import Service, Issue, debugme, status


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
