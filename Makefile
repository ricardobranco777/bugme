FILES=*.py

.PHONY: all
all: flake8 pylint mypy

.PHONY: flake8
flake8:
	@flake8 --ignore=E501 $(FILES)

.PHONY: pylint
pylint:
	@pylint $(FILES)

.PHONY: mypy
mypy:
	@mypy $(FILES)
