compose-up:
	docker-compose up --force-recreate

master:
	cd api_server; docker build . -t pymada/master

node-puppeteer:
	cd agent/images; docker build -f puppeteer.dockerfile .. -t pymada/node-puppeteer

selenium-firefox:
	cd agent/images; docker build -f selenium-firefox.dockerfile .. -t pymada/selenium-firefox

selenium-chrome:
	cd agent/images; docker build -f selenium-chrome.dockerfile .. -t pymada/selenium-chrome

python-agent:
	cd agent/images; docker build -f python-agent.dockerfile .. -t pymada/python-agent

all: master node-puppeteer selenium-firefox selenium-chrome


push-images:
	docker push pymada/master
	docker push pymada/node-puppeteer
	docker push pymada/selenium-firefox
	docker push pymada/selenium-chrome
	docker push pymada/python-agent

run-master:
	docker run -ti -p 8000:8000 pymada/master

run-master-testing: build-master
	docker run -ti -p 8000:8000 pymada/master make run-debug-gunicorn


.PHONY: compose-up master run-master run-master-testing agent all node-puppeteer selenium-firefox selenium-chrome push-images
