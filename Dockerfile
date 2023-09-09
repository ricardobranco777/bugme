FROM	registry.opensuse.org/opensuse/bci/python:3.11

RUN	zypper addrepo -G -cf https://download.opensuse.org/repositories/SUSE:/CA/openSUSE_Tumbleweed/SUSE:CA.repo && \
	zypper -n install ca-certificates-suse \
		python3-python-dateutil \
		python3-pytz \
		python3-Jinja2 \
		python3-bugzilla \
		python3-PyGithub \
		python3-python-gitlab \
		python3-python-redmine

COPY	bugme.py /

ENV	REQUESTS_CA_BUNDLE=/etc/ssl/ca-bundle.pem

ENTRYPOINT ["/usr/bin/python3", "/bugme.py"]
