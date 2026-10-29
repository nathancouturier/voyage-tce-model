# Makefile for voyage-tce-model.
#
# make is not installed on every machine, a stock Windows box among them. Every
# target below is a single command you can paste into a shell instead, and the
# help target prints those commands. Recipes use tabs, POSIX sh.

PYTHON ?= python
PORT ?= 8150

.DEFAULT_GOAL := help
.PHONY: help all setup data data-offline data-jobs routes seeds fixtures build serve test lint validate gate browser site note

help:
	@echo "targets"
	@echo "  make all           rebuild every derived file from the committed data, then run the gate:"
	@echo "                     the Baltic seed, the engine's test cases, the site's files and the note"
	@echo "  make setup         install the pinned Python dependencies"
	@echo "                     equivalent: python -m pip install -r requirements-lock.txt"
	@echo "                                 python -m pip install --no-deps -e ."
	@echo "  make data          refresh the EU allowance and dollar rate caches, then rebuild the artifacts"
	@echo "                     equivalent: python scripts/refresh.py"
	@echo "  make data-offline  check the committed caches against their rules and raw files, no network"
	@echo "                     equivalent: python scripts/refresh.py --offline"
	@echo "  make data-jobs     list the refresh jobs and the files each one owns, run nothing"
	@echo "                     equivalent: python scripts/refresh.py --list"
	@echo "  make routes        recompute the sea routes with searoute 1.6.0 and rewrite the seed"
	@echo "                     equivalent: python scripts/routes.py"
	@echo "  make seeds         rewrite data/seed/baltic.json from src/voyage/baltic.py"
	@echo "                     equivalent: python scripts/seeds.py"
	@echo "  make fixtures      rewrite the engine's parity cases from the Python engine"
	@echo "                     equivalent: python scripts/gen_fixtures.py"
	@echo "  make build         rewrite the JSON files the site reads and the content hashes in index.html"
	@echo "                     equivalent: python scripts/export.py"
	@echo "  make serve         serve the site at http://localhost:$(PORT)/voyage-tce-model/"
	@echo "                     equivalent: python scripts/serve.py --port $(PORT)"
	@echo "  make test          the Python suite"
	@echo "                     equivalent: python -m pytest tests"
	@echo "  make lint          ruff, lint and format"
	@echo "                     equivalent: ruff check src scripts tests && ruff format --check src scripts tests"
	@echo "  make validate      the node validators, no network, no Python"
	@echo "                     equivalent: node tools/<each>.mjs, for validate-data, validate-engine,"
	@echo "                                 validate-artifacts, check-paths, check-literals, check-styles, check-dashes"
	@echo "  make gate          everything that must pass before a change lands, as the build workflow runs it"
	@echo "  make browser       every view and the calculator's form in headless Chromium, from a server already running on PORT"
	@echo "                     equivalent: node tools/check-site.mjs"
	@echo "  make site          the README's screenshots, from a server already running on PORT"
	@echo "                     equivalent: node scripts/screenshots.mjs"
	@echo "  make note          the research note, Voyage-Economics-TCE-Research-Note.pdf"
	@echo "                     equivalent: python scripts/note.py"

all:
	$(PYTHON) scripts/seeds.py
	$(PYTHON) scripts/gen_fixtures.py
	$(PYTHON) scripts/export.py
	$(PYTHON) scripts/note.py
	$(MAKE) gate PYTHON="$(PYTHON)"

setup:
	$(PYTHON) -m pip install -r requirements-lock.txt
	$(PYTHON) -m pip install --no-deps -e .

data:
	$(PYTHON) scripts/refresh.py

data-offline:
	$(PYTHON) scripts/refresh.py --offline

data-jobs:
	$(PYTHON) scripts/refresh.py --list

routes:
	$(PYTHON) scripts/routes.py

seeds:
	$(PYTHON) scripts/seeds.py

fixtures:
	$(PYTHON) scripts/gen_fixtures.py

build:
	$(PYTHON) scripts/export.py

serve:
	$(PYTHON) scripts/serve.py --port $(PORT)

test:
	$(PYTHON) -m pytest tests

lint:
	ruff check src scripts tests
	ruff format --check src scripts tests

validate:
	node tools/validate-data.mjs
	node tools/validate-engine.mjs
	node tools/validate-artifacts.mjs
	node tools/check-paths.mjs
	node tools/check-literals.mjs
	node tools/check-styles.mjs
	node tools/check-dashes.mjs

gate:
	$(PYTHON) scripts/refresh.py --offline
	git diff --exit-code -- data/cache data/seed data/raw/manifest.json
	$(PYTHON) scripts/seeds.py --check
	$(PYTHON) scripts/gen_fixtures.py --check
	$(PYTHON) -m pytest tests
	ruff check src scripts tests
	ruff format --check src scripts tests
	$(PYTHON) scripts/export.py --check
	node tools/validate-data.mjs
	node tools/validate-engine.mjs
	node tools/validate-artifacts.mjs
	node tools/check-paths.mjs
	node tools/check-literals.mjs
	node tools/check-styles.mjs
	node tools/check-dashes.mjs

browser:
	node tools/check-site.mjs --base http://localhost:$(PORT)/voyage-tce-model/

site:
	node scripts/screenshots.mjs --base http://localhost:$(PORT)/voyage-tce-model/

note:
	$(PYTHON) scripts/note.py
