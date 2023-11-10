"""
Module to get Git blame from Github's GraphQL API
"""

import logging
import os
from functools import cache
from datetime import datetime
from typing import Self

import requests
from requests import RequestException

from services import debugme, VERSION
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
        self.session.headers["User-Agent"] = f"bugme/{VERSION}"
        self.timeout = 30
        if os.getenv("DEBUG"):
            self.session.hooks["response"].append(debugme)
        self.blame_file = cache(self._blame_file)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        try:
            self.session.close()
        except RequestException:
            pass
        self.blame_file.cache_clear()
        if exc_type is not None:
            logging.error("GitBlame: %s: %s: %s", exc_type, exc_value, traceback)

    def _blame_file(self, file: str) -> dict | None:
        variables = {
            "owner": self.owner,
            "repositoryName": self.repo,
            "branchName": self.branch,
            "filePath": file,
        }
        try:
            response = self.session.post(
                self.api_url,
                timeout=self.timeout,
                json={"query": _QUERY, "variables": variables},
            )
            response.raise_for_status()
            data = response.json()["data"]
            return data["repositoryOwner"]["repository"]["object"]["blame"]["ranges"]
        except RequestException as exc:
            logging.error("%s: %s", file, exc)
        except KeyError:
            logging.error("%s: %s", file, response.text)
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
