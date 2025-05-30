FROM	registry.opensuse.org/opensuse/bci/python:latest

RUN	zypper addrepo https://download.opensuse.org/repositories/SUSE:/CA/openSUSE_Tumbleweed/SUSE:CA.repo && \
	zypper --gpg-auto-import-keys -n install ca-certificates-suse && \
	zypper -n install \
		python3-python-dateutil \
		python3-pytz \
		python3-atlassian-python-api \
		python3-bugzilla \
		python3-PyGithub \
		python3-python-gitlab \
		python3-python-redmine \
		python3-requests \
		python3-requests-toolbelt && \
	zypper clean -a

RUN	git config --global --add safe.directory /bugme

COPY	services/ /services
COPY	*.py /

ENV	REQUESTS_CA_BUNDLE=/etc/ssl/ca-bundle.pem

WORKDIR	/bugme

ENTRYPOINT ["/usr/bin/python3", "/bugme.py"]
