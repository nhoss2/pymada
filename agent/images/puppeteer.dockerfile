FROM node:12-buster-slim

RUN apt-get update && apt-get upgrade -y && apt-get install wget gnupg2 ca-certificates -y --no-install-recommends

RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list' \
    && apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y google-chrome-unstable fonts-ipafont-gothic fonts-wqy-zenhei fonts-thai-tlwg fonts-kacst fonts-freefont-ttf python3-pip make \
      --no-install-recommends \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m pip install -U pip setuptools

WORKDIR /usr/src

COPY requirements.txt package.json ./

RUN python3 -m pip install --no-cache-dir -r requirements.txt
RUN npm install
RUN npm install request@^2.88.0
RUN npm install request-promise@^4.2.4

COPY agent_server.py wsgi.py pymada_client.js __init__.py ./

EXPOSE 5001
ENV AGENT_PORT 5001
ENV AGENT_ADDR "127.0.0.1"
ENV MASTER_URL "http://127.0.0.1:8000"

CMD ["sh", "-c", "gunicorn \"agent_server:gen_flask_app()\" -b 0.0.0.0:$AGENT_PORT"]
