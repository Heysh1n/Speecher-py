# Makefile
.PHONY: build clean install dev test

# Build executable for current platform
build:
	python build.py all

# Clean build artifacts
clean:
	python build.py clean
	rm -rf __pycache__ fc/__pycache__ *.egg-info

# Install as Python package (editable, for dev)
dev:
	pip install -e .

# Install globally via pip
install:
	pip install .

# Test run
test:
	python -m fc tree -s
	@echo ""
	python -m fc find "*.py"