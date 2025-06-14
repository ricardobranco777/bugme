"""
Services
"""

import concurrent.futures
import logging
import os
import re
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import reduce
from operator import getitem
from urllib.parse import urlparse, urlsplit, parse_qs
from typing import Any, Callable

from datetime import datetime
from pytz import utc

import requests
from requests.utils import parse_header_links
from requests.exceptions import RequestException
from requests_toolbelt.utils import dump  # type: ignore


VERSION = "2.4.7"

TAG_REGEX = "|".join(
    [
        r"(?:bnc|bsc|boo|poo|lp)#[0-9]+",
        r"(?:gh|gl|gsd|coo|soo|ssd)#[^#!]+[#!][0-9]+",
        r"jsc#[A-Z]+-[0-9]+",
    ]
)

TAG_TO_HOST = {
    "bnc": "bugzilla.suse.com",
    "boo": "bugzilla.suse.com",
    "bsc": "bugzilla.suse.com",
    "coo": "code.opensuse.org",
    "poo": "progress.opensuse.org",
    "gh": "github.com",
    "gl": "gitlab.com",
    "gsd": "gitlab.suse.de",
    "jsc": "jira.suse.com",
    "lp": "launchpad.net",
    "soo": "src.opensuse.org",
    "ssd": "src.suse.de",
}


def debugme(got, *args, **kwargs):  # pylint: disable=unused-argument
    """
    Print requests response
    """
    got.hook_called = True
    print(dump.dump_all(got).decode("utf-8"), file=sys.stderr)
    return got


def status(string: str) -> str:
    """
    Return status in uppercase with no spaces or single quotes
    """
    return string.upper().replace(" ", "_").replace("'", "")


def xgetitem(*keys: str | int) -> Callable[[Any], Any]:
    """
    Return callable to get nested item
    """
    return lambda item: reduce(getitem, keys, item)


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
        return self.url == other.url

    def __hash__(self) -> int:
        return hash(self.url)

    def sort_key(self) -> tuple[str, int]:
        """
        Key for numeric sort of URL's ending with digits
        """
        base, issue_id, _ = re.split(r"([0-9]+)$", self.url, maxsplit=1)
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
        hostname = url.hostname if url.hostname is not None else ""
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

    def __init__(self, url: str) -> None:
        url = url.rstrip("/")
        self.url = url if url.startswith("https://") else f"https://{url}"
        self.tag = "".join([s[0] for s in str(urlparse(self.url).hostname).split(".")])

    @abstractmethod
    def close(self) -> None:
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

    def _get_user_issues_x(self, queries: list[Any]) -> list[Issue]:
        issues = []
        futures = []
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=len(queries)
        ) as executor:
            for query in queries:
                futures.append(executor.submit(self._get_user_issues, query))
        for future in concurrent.futures.as_completed(futures):
            issues.extend(future.result())
        return list(set(issues))

    def _get_user_issues(self, query: dict[str, Any]) -> list[Issue]:
        raise NotImplementedError("_get_user_issues()")

    @abstractmethod
    def get_user_issues(self) -> list[Issue]:
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

    def __init__(self, url: str, token: str | None) -> None:
        super().__init__(url)
        self.issue_api_url = self.pr_api_url = "OVERRIDE"
        self.issue_web_url = self.pr_web_url = "OVERRIDE"
        self.session = requests.Session()
        if token is not None:
            self.session.headers["Authorization"] = f"token {token}"
        self.session.headers["Accept"] = "application/json"
        self.session.headers["User-Agent"] = f"bugme/{VERSION}"
        if os.getenv("DEBUG"):
            self.session.hooks["response"].append(debugme)
        self.timeout = 10

    def _get_paginated(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
        self,
        url: str,
        headers: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        param_page: str = "page",
        data_key: str | None = None,
        next_key: str | None = None,
        last_key: str | None = None,
    ) -> list[Any]:
        """
        Get all paginated responses
        """
        entries: list[dict[str, Any]] = []

        if headers is None:
            headers = {}
        if params is None:
            params = {}

        base_url = "://".join(urlsplit(url)[:2])
        response = self.session.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        entries = data if data_key is None else data[data_key]

        next_link = last_link = None
        if "Link" in response.headers:
            links = parse_header_links(response.headers["Link"])
            next_link = next((x["url"] for x in links if x.get("rel") == "next"), None)
            last_link = next((x["url"] for x in links if x.get("rel") == "last"), None)
        elif next_key is not None and last_key is not None:
            next_link = xgetitem(*next_key.split("."))(data)
            last_link = xgetitem(*last_key.split("."))(data)

        if next_link and last_link:
            if last_link.startswith("/"):
                last_link = f"{base_url}{last_link}"
            last_page = int(parse_qs(urlparse(last_link).query)[param_page][0])

            def get_page(page: int) -> list[dict[str, Any]]:
                nonlocal params
                xparams = dict(params)
                xparams[param_page] = page
                response = self.session.get(url, params=xparams)
                response.raise_for_status()
                data = response.json()
                return data if data_key is None else data[data_key]

            if last_page == 2:
                entries.extend(get_page(2))
                return entries

            with concurrent.futures.ThreadPoolExecutor(
                max_workers=min(10, last_page - 1)
            ) as executor:
                pages_to_fetch = range(2, last_page + 1)
                results = executor.map(get_page, pages_to_fetch)
                for result in results:
                    entries.extend(result)
        else:
            while next_link is not None:
                if next_link.startswith("/"):
                    next_link = f"{base_url}{next_link}"
                response = self.session.get(next_link, params=params)
                response.raise_for_status()
                data = response.json()
                entries.extend(data if data_key is None else data[data_key])
                if "Link" not in response.headers:
                    break
                links = parse_header_links(response.headers["Link"])
                next_link = next(
                    (x["url"] for x in links if x.get("rel") == "next"), None
                )
        return entries

    def close(self) -> None:
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
