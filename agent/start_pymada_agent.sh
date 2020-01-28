#!/usr/bin/env bash

cd /home/seluser/src; /home/seluser/.local/bin/gunicorn "agent_server:gen_flask_app()" -b 0.0.0.0:${AGENT_PORT}