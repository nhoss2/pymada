FROM selenium/standalone-chrome:3.141.59-zinc

USER seluser

WORKDIR /home/seluser
RUN mkdir src
WORKDIR /home/seluser/src/

COPY requirements.txt package.json ./

RUN sudo apt-get update && sudo apt-get install -y python3-pip --no-install-recommends \
    && python3 -m pip install -U pip setuptools \
    && python3 -m pip install --no-cache-dir -r requirements.txt \
    && rm requirements.txt

COPY agent_server.py wsgi.py pymada_client.py __init__.py ./
COPY selenium.conf /etc/supervisor/conf.d/selenium.conf
COPY start_pymada_agent.sh /opt/bin/start_pymada_agent.sh

EXPOSE 5001
ENV AGENT_PORT 5001
ENV AGENT_ADDR "127.0.0.1"
ENV MASTER_URL "http://127.0.0.1:8000"

CMD ["/bin/bash", "/opt/bin/entry_point.sh"]