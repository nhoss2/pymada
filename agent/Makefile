test:
	python -m unittest

build-docker:
	docker build . -t nhoss2/pymada_agent

run-server:
	gunicorn "wsgi:app" -b 0.0.0.0:${AGENT_PORT}

run-local-server:
	AGENT_ADDR=127.0.0.1 MASTER_URL=http://localhost:8000 \
	AGENT_PORT=5001 gunicorn "wsgi:app" -b localhost:5001

.PHONY: test build-docker run-agent run-server run-local-server
