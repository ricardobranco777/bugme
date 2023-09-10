# pylint: disable=missing-module-docstring,missing-function-docstring,invalid-name,no-member

from datetime import datetime
from pytz import utc
import pytest
from bugme import dateit, Item, get_item


# Test cases for the dateit function
def test_dateit():
    # Test date formatting with the default format
    dt = datetime(2023, 9, 10, 15, 30, 0, tzinfo=utc)
    formatted_date = dateit(dt)
    assert formatted_date == "Sun Sep 10 17:30:00 CEST 2023"

    # Test date formatting with a custom format
    custom_format = "%Y-%m-%d %H:%M:%S"
    formatted_date = dateit(dt, time_format=custom_format)
    assert formatted_date == "2023-09-10 17:30:00"

    # Test date formatting with a different custom format
    another_format = "%A, %d %B %Y"
    formatted_date = dateit(dt, time_format=another_format)
    assert formatted_date == "Sunday, 10 September 2023"

    # Test date formatting with the default format using a string date
    date_str = "2023-09-10T15:30:00+00:00"
    formatted_date = dateit(date_str)
    assert formatted_date == "Sun Sep 10 17:30:00 CEST 2023"

    # Test date formatting with a custom format using a string date
    formatted_date = dateit(date_str, time_format=custom_format)
    assert formatted_date == "2023-09-10 17:30:00"

    # Test date formatting with a different custom format using a string date
    formatted_date = dateit(date_str, time_format=another_format)
    assert formatted_date == "Sunday, 10 September 2023"


# Test cases for the Item class
def test_Item():
    # Create an Item instance and test its attributes
    item = Item(item_id=123, host="github.com", repo="user/repo")
    assert item.item_id == 123
    assert item.host == "github.com"
    assert item.repo == "user/repo"

    # Test item representation (__repr__ method)
    expected_repr = "Item(item_id=123, host='github.com', repo='user/repo')"
    assert repr(item) == expected_repr

    # Test item dictionary access
    assert item["item_id"] == 123
    assert item["host"] == "github.com"
    assert item["repo"] == "user/repo"

    # Test item dictionary access with a nonexistent key
    with pytest.raises(KeyError):
        _ = item["nonexistent_key"]


# Test cases for the get_item function with supported formats
def test_get_item_with_bsc_format():
    string = "bsc#1213811"
    item = get_item(string)
    expected_item = Item(item_id=1213811, host="bugzilla.suse.com", repo="")
    assert item.__dict__ == expected_item.__dict__


def test_get_item_with_gh_format():
    string = "gh#containers/podman#19529"
    item = get_item(string)
    expected_item = Item(item_id=19529, host="github.com", repo="containers/podman")
    assert item.__dict__ == expected_item.__dict__


def test_get_item_with_gl_format():
    string = "gl#gitlab-org/gitlab#424503"
    item = get_item(string)
    expected_item = Item(item_id=424503, host="gitlab.com", repo="gitlab-org/gitlab")
    assert item.__dict__ == expected_item.__dict__


def test_get_item_with_gsd_format():
    string = "gsd#qac/container-release-bot#7"
    item = get_item(string)
    expected_item = Item(
        item_id=7, host="gitlab.suse.de", repo="qac/container-release-bot"
    )
    assert item.__dict__ == expected_item.__dict__


def test_get_item_with_poo_format():
    string = "poo#133910"
    item = get_item(string)
    expected_item = Item(item_id=133910, host="progress.opensuse.org", repo="")
    assert item.__dict__ == expected_item.__dict__


# Test cases for the get_item function with URLs
def test_get_item_with_bugzilla_url():
    url = "https://bugzilla.suse.com/show_bug.cgi?id=1213811"
    item = get_item(url)
    expected_item = Item(item_id=1213811, host="bugzilla.suse.com", repo="")
    assert item.__dict__ == expected_item.__dict__


def test_get_item_with_github_url():
    url = "https://github.com/containers/podman/issues/19529"
    item = get_item(url)
    expected_item = Item(item_id=19529, host="github.com", repo="containers/podman")
    assert item.__dict__ == expected_item.__dict__


def test_get_item_with_progress_url():
    url = "https://progress.opensuse.org/issues/133910"
    item = get_item(url)
    expected_item = Item(item_id=133910, host="progress.opensuse.org", repo="")
    assert item.__dict__ == expected_item.__dict__


def test_get_item_with_gitlab_url():
    url = "https://gitlab.com/gitlab-org/gitlab/-/issues/424503"
    item = get_item(url)
    expected_item = Item(item_id=424503, host="gitlab.com", repo="gitlab-org/gitlab")
    assert item.__dict__ == expected_item.__dict__


def test_get_item_with_gsd_url():
    url = "https://gitlab.suse.de/qac/container-release-bot/-/issues/7"
    item = get_item(url)
    expected_item = Item(
        item_id=7, host="gitlab.suse.de", repo="qac/container-release-bot"
    )
    assert item.__dict__ == expected_item.__dict__


# Test case for an unsupported format
def test_get_item_with_unsupported_format():
    string = "unsupported#12345"
    item = get_item(string)
    assert item is None


# Test case for an unsupported URL
def test_get_item_with_unsupported_url():
    url = "https://unsupported.com/issue/12345"
    item = get_item(url)
    assert item is None
