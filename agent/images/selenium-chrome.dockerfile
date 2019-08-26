FROM selenium/standalone-chrome@sha256:5769d4e039d56e9db79827628c47531e473e199c136291c305d12fa4f7cfec21

WORKDIR /usr/src

COPY requirements.txt package.json ./

USER root
RUN apt-get update && apt-get install -y python3-pip --no-install-recommends \
    && python3 -m pip install -U pip setuptools \
    && python3 -m pip install --no-cache-dir -r requirements.txt
USER seluser

COPY agent_server.py client.py wsgi.py Makefile pymada_client.js __init__.py ./

EXPOSE 5001
ENV AGENT_PORT 5001
ENV AGENT_ADDR "127.0.0.1"
ENV MASTER_URL "http://127.0.0.1:8000"

CMD ["sh", "-c", "gunicorn \"agent_server:gen_flask_app()\" -b $AGENT_ADDR:$AGENT_PORT"]