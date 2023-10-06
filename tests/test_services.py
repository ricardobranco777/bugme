# pylint: disable=missing-module-docstring,missing-class-docstring,missing-function-docstring,invalid-name,no-member,use-dict-literal

import pytest
from services import (
    get_urltag,
    Issue,
    Service,
    guess_service,
    MyBugzilla,
    MyGithub,
    MyGitlab,
    MyGitea,
    MyJira,
    MyRedmine,
    MyPagure,
    MyGogs,
    MySourceForge,
    MyBitbucket,
    MyLaunchpad,
)


# Test cases for the Issue class
def test_Issue():
    # Create an Issue instance and test its attributes
    issue = Issue(issue_id="123", host="github.com", repo="user/repo")
    assert issue.issue_id == "123"
    assert issue.host == "github.com"
    assert issue.repo == "user/repo"

    # Test issue representation (__repr__ method)
    expected_repr = "Issue(issue_id='123', host='github.com', repo='user/repo')"
    assert repr(issue) == expected_repr

    # Test issue dictionary access
    assert issue["issue_id"] == "123"
    assert issue["host"] == "github.com"
    assert issue["repo"] == "user/repo"

    # Test issue dictionary access with a nonexistent key
    with pytest.raises(KeyError):
        _ = issue["nonexistent_key"]


# Test cases for the get_urltag function with supported formats
def test_get_urltag_with_bsc_format():
    string = "bsc#1213811"
    issue = get_urltag(string)
    expected_issue = dict(issue_id="1213811", host="bugzilla.suse.com", repo="")
    assert issue == expected_issue


def test_get_urltag_with_gh_format():
    string = "gh#containers/podman#19529"
    issue = get_urltag(string)
    expected_issue = dict(issue_id="19529", host="github.com", repo="containers/podman")
    assert issue == expected_issue


def test_get_urltag_with_gl_format():
    string = "gl#gitlab-org/gitlab#424503"
    issue = get_urltag(string)
    expected_issue = dict(
        issue_id="424503", host="gitlab.com", repo="gitlab-org/gitlab"
    )
    assert issue == expected_issue


def test_get_urltag_with_gsd_format():
    string = "gsd#qac/container-release-bot#7"
    issue = get_urltag(string)
    expected_issue = dict(
        issue_id="7", host="gitlab.suse.de", repo="qac/container-release-bot"
    )
    assert issue == expected_issue


def test_get_urltag_with_poo_format():
    string = "poo#133910"
    issue = get_urltag(string)
    expected_issue = dict(issue_id="133910", host="progress.opensuse.org", repo="")
    assert issue == expected_issue


# Test cases for the get_urltag function with URLs
def test_get_urltag_with_bugzilla_url():
    url = "https://bugzilla.suse.com/show_bug.cgi?id=1213811"
    issue = get_urltag(url)
    expected_issue = dict(issue_id="1213811", host="bugzilla.suse.com", repo="")
    assert issue == expected_issue


def test_get_urltag_with_github_url():
    url = "https://github.com/containers/podman/issues/19529"
    issue = get_urltag(url)
    expected_issue = dict(issue_id="19529", host="github.com", repo="containers/podman")
    assert issue == expected_issue


def test_get_urltag_with_progress_url():
    url = "https://progress.opensuse.org/issues/133910"
    issue = get_urltag(url)
    expected_issue = dict(issue_id="133910", host="progress.opensuse.org", repo="")
    assert issue == expected_issue


def test_get_urltag_with_gitlab_url():
    url = "https://gitlab.com/gitlab-org/gitlab/-/issues/424503"
    issue = get_urltag(url)
    expected_issue = dict(
        issue_id="424503", host="gitlab.com", repo="gitlab-org/gitlab"
    )
    assert issue == expected_issue


def test_get_urltag_with_gsd_url():
    url = "https://gitlab.suse.de/qac/container-release-bot/-/issues/7"
    issue = get_urltag(url)
    expected_issue = dict(
        issue_id="7", host="gitlab.suse.de", repo="qac/container-release-bot"
    )
    assert issue == expected_issue


def test_get_urltag_with_www_prefix():
    url = "https://gitlab.com/gitlab-org/gitlab/-/issues/424503"
    issue = get_urltag(url)
    expected_issue = dict(
        issue_id="424503", host="gitlab.com", repo="gitlab-org/gitlab"
    )
    assert issue == expected_issue


# Test case for an unsupported format
def test_get_urltag_with_unsupported_format():
    string = "unsupported#12345"
    issue = get_urltag(string)
    assert issue is None


# Test case for an unsupported URL
def test_get_urltag_with_unsupported_url():
    url = "bsd#666"
    issue = get_urltag(url)
    assert issue is None


# Mock Service class for testing
class MockService(Service):
    def get_issue(self, issue_id: str = "", **kwargs) -> Issue | None:
        return Issue(issue_id=issue_id, host=self.url, repo="mock_repo")


# Test cases for the Service class
def test_service_initialization():
    url = "example.com"
    service = Service(url)
    assert service.url == f"https://{url}"


def test_service_repr():
    url = "example.com"
    service = Service(url)
    assert repr(service) == f"Service(url='https://{url}')"


def test_mock_service_get_issue():
    url = "https://example.com"
    service = MockService(url)
    issue_id = "123"
    issue = service.get_issue(issue_id)
    expected_issue = Issue(issue_id=issue_id, host=url, repo="mock_repo")
    assert issue.__dict__ == expected_issue.__dict__


def test_mock_service_get_issues():
    url = "https://example.com"
    service = MockService(url)
    issues = [{"issue_id": "1"}, {"issue_id": "2"}, {"issue_id": "3"}]
    expected_issues = [
        Issue(issue_id=i["issue_id"], host=url, repo="mock_repo") for i in issues
    ]

    results = service.get_issues(issues)

    assert len(results) == len(expected_issues)

    for result, expected_issue in zip(results, expected_issues):
        assert result.issue_id == expected_issue.issue_id
        assert result.host == expected_issue.host
        assert result.repo == expected_issue.repo


def test_guess_service():
    assert guess_service("github.com") is MyGithub
    assert guess_service("gitlab.com") is MyGitlab
    assert guess_service("issues.redhat.com") is MyJira
    assert guess_service("progress.opensuse.org") is MyRedmine
    assert guess_service("bugzilla.suse.com") is MyBugzilla
    assert guess_service("jira.suse.com") is MyJira
    assert guess_service("src.opensuse.org") is MyGitea
    assert guess_service("code.opensuse.org") is MyPagure
    assert guess_service("try.gogs.io") is MyGogs
    assert guess_service("sourceforge.net") is MySourceForge
    assert guess_service("bitbucket.org") is MyBitbucket
    assert guess_service("launchpad.net") is MyLaunchpad
