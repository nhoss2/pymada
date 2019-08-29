compose-up:
	docker-compose up --force-recreate

master:
	cd api_server; docker build . -t nhoss2/pymada-master

agent:
	cd agent; docker build . -t nhoss2/pymada_agent

node-puppeteer:
	cd agent/images; docker build -f puppeteer.dockerfile .. -t nhoss2/pymada-node-puppeteer

all: master agent node-puppeteer

run-master:
	docker run -ti -p 8000:8000 nhoss2/pymada-master

run-master-testing: build-master
	docker run -ti -p 8000:8000 nhoss2/pymada-master make run-debug-gunicorn


.PHONY: compose-up master run-master run-master-testing agent all node-puppeteer
