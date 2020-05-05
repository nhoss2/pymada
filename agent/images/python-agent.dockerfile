FROM python:3.7-slim

WORKDIR /usr/src

COPY requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

COPY agent_server.py wsgi.py pymada_client.py __init__.py ./

EXPOSE 5001
ENV AGENT_PORT 5001
ENV AGENT_ADDR "127.0.0.1"
ENV MASTER_URL "http://127.0.0.1:8000"

CMD ["sh", "-c", "gunicorn \"agent_server:gen_flask_app()\" -b 0.0.0.0:$AGENT_PORT"]