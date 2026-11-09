.PHONY: install lint test notebooks all

# Thin wrapper around run.py, which also works on Windows without make
install:
	python run.py install

lint:
	python run.py lint

test:
	python run.py test

notebooks:
	python run.py notebooks

all:
	python run.py all
