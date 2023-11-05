"""
Services
"""

import concurrent.futures
import logging
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from urllib.parse import urlparse, parse_qs
from typing import Any

from datetime import datetime
from pytz import utc

import requests
from requests.exceptions import RequestException
from requests_toolbelt.utils import dump  # type: ignore


TAG_REGEX = "|".join(
    [
        r"(?:bnc|bsc|boo|poo|lp)#[0-9]+",
        r"(?:gh|gl|gsd|coo|soo)#[^#!]+[#!][0-9]+",
        r"jsc#[A-Z]+-[0-9]+",
    ]
)

TAG_TO_HOST = {
    "bnc": "bugzilla.suse.com",
    "bsc": "bugzilla.suse.com",
    "boo": "bugzilla.suse.com",
    "gh": "github.com",
    "gl": "gitlab.com",
    "gsd": "gitlab.suse.de",
    "jsc": "jira.suse.com",
    "poo": "progress.opensuse.org",
    "coo": "code.opensuse.org",
    "soo": "src.opensuse.org",
    "lp": "launchpad.net",
}


def debugme(got, *args, **kwargs):  # pylint: disable=unused-argument
    """
    Print requests response
    """
    got.hook_called = True
    print(dump.dump_all(got).decode("utf-8"))
    return got


def status(string: str) -> str:
    """
    Return status in uppercase with no spaces or single quotes
    """
    return string.upper().replace(" ", "_").replace("'", "")


@dataclass(kw_only=True)
class Issue:  # pylint: disable=too-many-instance-attributes
    """
    Issue class
    """

    tag: str
    url: str
    assignee: str
    creator: str
    created: datetime
    updated: datetime
    status: str
    title: str
    raw: dict

    # The __eq__ & __hash__ methods allows us to use sets

    def __eq__(self, other) -> bool:
        return self.url == other.url  # pylint: disable=no-member

    def __hash__(self) -> int:
        return hash(self.url)  # pylint: disable=no-member

    def sort_key(self) -> tuple[str, int]:
        """
        Key for numeric sort of URL's ending with digits
        """
        base, issue_id, _ = re.split(
            r"([0-9]+)$", self.url, maxsplit=1  # pylint: disable=no-member
        )
        return base, int(issue_id)

    # Allow access this object as a dictionary

    def __getitem__(self, item: str) -> Any:
        try:
            return getattr(self, item)
        except AttributeError as exc:
            raise KeyError(exc) from exc

    def __setitem__(self, item: str, value: Any) -> None:
        setattr(self, item, value)


def get_urltag(string: str) -> dict[str, str | bool] | None:
    """
    Get tag or URL from string
    """
    if "#" not in string:
        # URL
        string = string if string.startswith("https://") else f"https://{string}"
        url = urlparse(string)
        hostname = url.hostname.removeprefix("www.") if url.hostname is not None else ""
        path = url.path.strip("/")
        repo: str = ""
        is_pr: bool = False
        if url.query:  # Bugzilla
            issue_id = parse_qs(url.query)["id"][0]
        elif "/" not in path:
            issue_id = path.rsplit("/", 1)[-1]
        elif path.count("/") == 1:
            issue_id = path.rsplit("/", 1)[-1]
        else:  # Git forges
            path = path.replace("/-/", "/")  # Gitlab
            repo, issue_type, issue_id = path.rsplit("/", 2)
            is_pr = any(s in issue_type for s in ("pull", "merge"))
        return {
            "issue_id": issue_id,
            "host": hostname,
            "repo": repo,
            "is_pr": is_pr,
        }
    # Tag
    if not re.fullmatch(TAG_REGEX, string):
        logging.warning("Skipping unsupported %s", string)
        return None
    is_pr = "!" in string
    try:
        code, repo, issue = re.split(r"[#!]", string)
    except ValueError:
        code, issue = string.split("#", 1)
        repo = ""
    return {
        "issue_id": issue,
        "host": TAG_TO_HOST[code],
        "repo": repo,
        "is_pr": is_pr,
    }


class Service(ABC):
    """
    Service class to abstract methods
    """

    def __init__(self, url: str):
        url = url.rstrip("/")
        self.url = url if url.startswith("https://") else f"https://{url}"
        self.tag = "".join([s[0] for s in str(urlparse(self.url).hostname).split(".")])

    @abstractmethod
    def close(self):
        """
        Close session
        """

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(url='{self.url}')"

    def _not_found(self, url: str, tag: str) -> Issue:
        now = datetime.now(tz=utc)
        return Issue(
            tag=tag,
            url=url,
            assignee="none",
            creator="none",
            created=now,
            updated=now,
            status="ERROR",
            title="NOT FOUND",
            raw={},
        )

    def _get_user_issues2(  # pylint: disable=too-many-arguments
        self,
        username: str = "",
        assigned: bool = False,
        created: bool = False,
        involved: bool = True,
        **kwargs,
    ) -> list[Issue]:
        """
        Get user issues
        """
        if involved:
            assigned = created = True
        issues: list[Issue] = []

        def get_assigned_issues() -> list[Issue]:
            return self.get_assigned(username, **kwargs)

        def get_created_issues() -> list[Issue]:
            return self.get_created(username, **kwargs)

        futures = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            if assigned:
                futures.append(executor.submit(get_assigned_issues))
            if created:
                futures.append(executor.submit(get_created_issues))
        for future in concurrent.futures.as_completed(futures):
            issues.extend(future.result())

        return list(set(issues))

    def _get_user_issues4(  # pylint: disable=too-many-arguments
        self,
        username: str = "",
        assigned: bool = False,
        created: bool = False,
        involved: bool = True,
        **kwargs,
    ) -> list[Issue]:
        """
        Get user issues
        """
        if involved:
            assigned = created = True
        issues: list[Issue] = []

        def get_issues(is_pr: bool, is_assigned: bool) -> list[Issue]:
            if is_assigned:
                return self.get_assigned(username, pull_requests=is_pr, **kwargs)
            return self.get_created(username, pull_requests=is_pr, **kwargs)

        futures = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            if assigned:
                futures.append(executor.submit(get_issues, False, True))
                futures.append(executor.submit(get_issues, True, True))
            if created:
                futures.append(executor.submit(get_issues, False, False))
                futures.append(executor.submit(get_issues, True, False))
        for future in concurrent.futures.as_completed(futures):
            issues.extend(future.result())

        return list(set(issues))

    @abstractmethod
    def get_assigned(
        self, username: str = "", **_  # pylint: disable=unused-argument
    ) -> list[Issue]:
        """
        Get assigned issues
        """

    @abstractmethod
    def get_created(
        self, username: str = "", **_  # pylint: disable=unused-argument
    ) -> list[Issue]:
        """
        Get created issues
        """

    @abstractmethod
    def get_user_issues(self, **_) -> list[Issue]:
        """
        Get user issues
        """

    @abstractmethod
    def get_issue(self, issue_id: str = "", **kwargs) -> Issue | None:
        """
        This method must be overriden if get_issues() isn't overriden
        """

    def get_issues(self, issues: list[dict]) -> list[Issue | None]:
        """
        Multithreaded get_issues()
        """
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(10, len(issues))
        ) as executor:
            return list(executor.map(lambda it: self.get_issue(**it), issues))


class Generic(Service):
    """
    Generic class for services using python requests
    """

    def __init__(self, url: str, token: str | None):
        super().__init__(url)
        self.issue_api_url = self.pr_api_url = "OVERRIDE"
        self.issue_web_url = self.pr_web_url = "OVERRIDE"
        self.session = requests.Session()
        if token is not None:
            self.session.headers["Authorization"] = f"token {token}"
        self.session.headers["Accept"] = "application/json"
        if os.getenv("DEBUG"):
            self.session.hooks["response"].append(debugme)
        self.timeout = 10

    def close(self):
        self.session.close()

    def get_issue(self, issue_id: str = "", **kwargs) -> Issue | None:
        """
        Get Git issue
        """
        repo: str = kwargs.pop("repo")
        is_pr = bool(kwargs.get("is_pr"))
        if is_pr:
            api_url = self.pr_api_url
            web_url = self.pr_web_url
            mark = "!"
        else:
            api_url = self.issue_api_url
            web_url = self.issue_web_url
            mark = "#"
        try:
            got = self.session.get(
                api_url.format(repo=repo, issue=issue_id),
                timeout=self.timeout,
            )
            got.raise_for_status()
            info = got.json()
        except RequestException as exc:
            try:
                if exc.response.status_code == 404:  # type: ignore
                    return self._not_found(
                        url=web_url.format(repo=repo, issue=issue_id),
                        tag=f"{self.tag}#{repo}{mark}{issue_id}",
                    )
            except AttributeError:
                pass
            logging.error(
                "%s: %s: get_issue(%s, %s): %s",
                self.__class__.__name__,
                self.url,
                repo,
                issue_id,
                exc,
            )
            return None
        return self._to_issue(info, repo=repo, is_pr=is_pr)

    def _to_issue(self, info: Any, **kwargs) -> Issue:
        raise NotImplementedError(f"{self.__class__.__name__}: to_issue()")
