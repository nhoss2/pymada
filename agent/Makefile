test:
	python -m unittest

build-docker:
	docker build . -t pymada/agent

run-local-server:
	AGENT_ADDR=127.0.0.1 MASTER_URL=http://localhost:8000 \
	AGENT_PORT=5001 gunicorn "wsgi:app" -b localhost:5001

.PHONY: test build-docker run-local-server
