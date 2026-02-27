PYTHON ?= python3

.PHONY: test-unit test-contract test-e2e test-mod-bridge test-all test-e2e-online jarvis-voice

test-unit:
	$(PYTHON) tools/run_tests.py unit

test-contract:
	$(PYTHON) tools/run_tests.py contract

test-e2e:
	$(PYTHON) tools/run_tests.py e2e

test-e2e-online:
	RUN_ONLINE_E2E=1 $(PYTHON) -m unittest tests.e2e.test_voice_online_e2e -v

test-mod-bridge:
	$(PYTHON) tools/run_tests.py mod-bridge

test-all:
	$(PYTHON) tools/run_tests.py all

jarvis-voice:
	$(PYTHON) -m jarvis.cli --voice
