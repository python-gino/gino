test:
	pytest --cov=src --cov-report=
	USE_TRIO=1 pytest --cov=src --cov-fail-under=95 --cov-report=xml --cov-report=term --cov-append
