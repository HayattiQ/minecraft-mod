PYTHON ?= python3

.PHONY: test-unit test-contract test-e2e test-mod-bridge test-all

test-unit:
	$(PYTHON) tools/run_tests.py unit

test-contract:
	$(PYTHON) tools/run_tests.py contract

test-e2e:
	$(PYTHON) tools/run_tests.py e2e

test-mod-bridge:
	$(PYTHON) tools/run_tests.py mod-bridge

test-all:
	$(PYTHON) tools/run_tests.py all
