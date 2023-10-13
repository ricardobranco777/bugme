"""
Bitbucket
"""

import logging
import os
from typing import Any

from atlassian import Bitbucket  # type: ignore
from atlassian.errors import ApiError  # type: ignore
from requests.exceptions import RequestException

from utils import utc_date
from . import Service, Issue, debugme, status


class MyBitbucket(Service):
    """
    Bitbucket
    """

    def __init__(self, url: str, creds: dict):
        if url.endswith("bitbucket.org"):
            url = "api.bitbucket.org"
        super().__init__(url)
        self.client = Bitbucket(url=self.url, **creds)
        if os.getenv("DEBUG"):
            self.client.session.hooks["response"].append(debugme)

    def __del__(self):
        try:
            self.client.session.close()
        except AttributeError:
            pass

    def get_issue(self, issue_id: str = "", **kwargs) -> Issue | None:
        """
        Get Bitbucket issue
        """
        repo: str = kwargs.get("repo", "")
        is_pr: bool = kwargs.get("is_pr", False)
        key, repo = repo.split("/", 1)
        info: Any
        try:
            if is_pr:
                info = self.client.get_pull_request(key, repo, issue_id)
            else:
                info = self.client.get_issue(key, repo, issue_id)
        except (ApiError, RequestException) as exc:
            issuepr = "pull-requests" if is_pr else "issues"
            try:
                if exc.response.status_code == 404:  # type: ignore
                    return self._not_found(
                        url=f"{self.url}/{repo}/{issuepr}/{issue_id}",
                        tag=f"{self.tag}#{issue_id}",
                    )
            except AttributeError:
                pass
            logging.error("Bitbucket: %s: get_issue(%s): %s", self.url, issue_id, exc)
            return None
        return self._to_issue(info, repo, is_pr)

    def _to_issue(self, info: Any, repo: str, is_pr: bool) -> Issue:
        if is_pr:
            assignee = creator = info["author"]["nickname"]
            mark = "!"
        else:
            assignee = info["assignee"]["nickname"] if info["assignee"] else "none"
            creator = info["reporter"]["nickname"] if info["reporter"] else "none"
            mark = "#"
        return Issue(
            tag=f'{self.tag}#{repo}{mark}{info["id"]}',
            url=info["links"]["html"]["href"],
            assignee=assignee,
            creator=creator,
            created=utc_date(info["created_on"]),
            updated=utc_date(info["updated_on"]),
            status=status(info["state"]),
            title=info["title"],
            raw=info,
        )
