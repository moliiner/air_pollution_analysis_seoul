.PHONY: install test lint notebooks all

install:
	pip install -r requirements.txt

test:
	pytest -q

lint:
	python -m pyflakes src tests

# Execute every notebook in order, in a fresh kernel, and save the outputs
notebooks:
	for nb in notebooks/[0-9]*.ipynb; do \
		jupyter nbconvert --to notebook --execute --inplace "$$nb" || exit 1; \
	done

all: lint test notebooks
