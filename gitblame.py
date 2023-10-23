"""
Module to get Git blame from Github's GraphQL API
"""

import logging
import os
import time
from functools import cache
from datetime import datetime

import requests
from requests import RequestException

from services import debugme
from utils import utc_date


_QUERY = """
query($owner: String!, $repositoryName: String!, $branchName: String!, $filePath: String!) {
  repositoryOwner(login: $owner) {
    repository(name: $repositoryName) {
      object(expression: $branchName) {
        ... on Commit {
          blame(path: $filePath) {
            ranges {
              startingLine
              endingLine
              commit {
                committedDate
                oid
                author {
                  name
                  email
                }
              }
            }
          }
        }
      }
    }
  }
}
"""


class GitBlame:
    """
    Class to get Git blame from Github's GraphQL API
    """

    def __init__(self, repo: str, branch: str, access_token: str) -> None:
        self.owner, self.repo = repo.split("/", 1)
        self.branch = branch
        self.api_url = "https://api.github.com/graphql"
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Bearer {access_token}"
        self.timeout = 30
        if os.getenv("DEBUG"):
            self.session.hooks["response"].append(debugme)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            self.session.close()
        except RequestException:
            pass
        if exc_type is not None:
            logging.error("GitBlame: %s: %s: %s", exc_type, exc_value, traceback)

    @cache  # pylint: disable=method-cache-max-size-none
    def blame_file(self, file: str) -> dict | None:
        """
        Blame file
        """
        variables = {
            "owner": self.owner,
            "repositoryName": self.repo,
            "branchName": self.branch,
            "filePath": file,
        }
        retry = 3
        while retry:
            retry -= 1
            try:
                response = self.session.post(
                    self.api_url,
                    timeout=self.timeout,
                    json={"query": _QUERY, "variables": variables},
                )
                # https://docs.github.com/en/rest/overview/resources-in-the-rest-api?apiVersion=2022-11-28#conditional-requests
                if (
                    "X-RateLimit-Remaining" in response.headers
                    and int(response.headers["X-RateLimit-Remaining"]) == 0
                ):
                    reset_time = int(response.headers["X-RateLimit-Reset"])
                    wait_time = reset_time - time.time()
                    logging.info("GitBlame: Waiting %s seconds for %s", wait_time, file)
                    time.sleep(wait_time)
                    continue
                # https://docs.github.com/en/rest/overview/resources-in-the-rest-api?apiVersion=2022-11-28#secondary-rate-limits
                if "Retry-After" in response.headers:
                    wait_time = int(response.headers["Retry-After"])
                    logging.info("GitBlame: Waiting %s seconds for %s", wait_time, file)
                    time.sleep(wait_time)
                    continue
                response.raise_for_status()
                try:
                    data = response.json()["data"]
                except KeyError:
                    logging.error("%s: %s: %s", file, response.text, response.headers)
                    return None
                return data["repositoryOwner"]["repository"]["object"]["blame"][
                    "ranges"
                ]
            except RequestException as exc:
                logging.error("%s: %s", file, exc)
                return None
        return None

    def blame_line(self, file: str, line: int) -> tuple[str, str, str, datetime]:
        """
        Blame line
        """
        blames = self.blame_file(file)
        if blames is None:
            raise KeyError(f"No blame for {file}")
        commit = {}
        for blame in blames:
            if blame["startingLine"] <= line <= blame["endingLine"]:
                commit = blame["commit"]
        author, email = commit["author"]["name"], commit["author"]["email"]
        # Sometimes these are swapped
        if "@" not in email and "@" in author:
            author, email = email, author
        return author, email, commit["oid"], utc_date(commit["committedDate"])
