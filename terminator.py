"""
Plugin for terminator

Copy this file to $HOME/.config/terminator/plugins/

Based on:
https://terminator-gtk3.readthedocs.io/en/latest/plugins.html
"""

import re
import terminatorlib.plugin as plugin

AVAILABLE = ['cve', 'suse_bugzilla', 'suse_jira', 'suse_incident', 'suse_fate', 'suse_progress']


class base(plugin.URLHandler):
    capabilities = ['url_handler']

    def callback(self, line):
        for item in re.findall(self._extract, line):
            return self._url + item


class cve(base):
    handler_name = 'cve'
    match = r'\bCVE-[0-9]+-[0-9]+\b'
    nameopen = "Open CVE item"
    namecopy = "Copy CVE URL"
    _extract = '[0-9]+-[0-9]+'
    _url = 'https://cve.mitre.org/cgi-bin/cvename.cgi?name='


class suse_bugzilla(base):
    handler_name = 'suse_bugzilla'
    match = r'\b(bsc|bnc|boo)#[0-9]+\b'
    nameopen = "Open Bugzilla item"
    namecopy = "Copy Bugzilla URL"
    _extract = '[0-9]+'
    _url = 'https://bugzilla.suse.com/show_bug.cgi?id='


class suse_jira(base):
    handler_name = 'suse_jira'
    match = r'\bjsc#[A-Z]+-[0-9]+\b'
    nameopen = "Open Jira item"
    namecopy = "Copy Jira URL"
    _extract = '[A-Z]+-[0-9]+'
    _url = 'https://jira.suse.com/browse/'


class suse_incident(base):
    handler_name = 'suse_incident'
    match = r'\bS(USE)?:M(aintenance)?:[0-9]+:[0-9]+\b'
    nameopen = "Open Incident item"
    namecopy = "Copy Incident URL"
    _extract = '[0-9]+'
    _url = 'https://smelt.suse.de/incident/'


class suse_fate(base):
    handler_name = 'suse_fate'
    match = r'\bFATE:[0-9]+\b'
    nameopen = "Open FATE item"
    namecopy = "Copy FATE URL"
    _extract = '[0-9]+'
    _url = 'https://fate.suse.com/'


class suse_progress(base):
    handler_name = 'suse_progress'
    match = r'\bpoo#[0-9]+\b'
    nameopen = "Open POO item"
    namecopy = "Copy POO URL"
    _extract = '[0-9]+'
    _url = 'https://progress.opensuse.org/issues/'
