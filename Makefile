TEST_EXAMPLES ?= 1
test:
	TEST_EXAMPLES=$(TEST_EXAMPLES) pytest --cov=src --cov-report= tests
	TEST_EXAMPLES=0 USE_TRIO=1 pytest --cov=src --cov-fail-under=95 --cov-report=xml --cov-report=term --cov-append tests
	black --check src examples
	mypy --ignore-missing-imports src examples/*/src
