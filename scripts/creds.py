"""
Create creds.json
"""

import json
import os

CREDS = {
    "bugzilla.suse.com": {
        "api_key": os.getenv("BUGZILLA_API_KEY"),
    },
    "github.com": {"token": os.getenv("BUGME_GITHUB_TOKEN")},
    "gitlab.com": {"private_token": os.getenv("GITLAB_API_KEY")},
    "jira.suse.com": {
        "token": os.getenv("JIRA_TOKEN"),
    },
    "progress.opensuse.org": {
        "key": os.getenv("REDMINE_API_KEY"),
    },
}


if __name__ == "__main__":
    os.umask(0o077)
    with open("creds.json", "w", encoding="utf-8") as file:
        file.write(json.dumps(CREDS))
