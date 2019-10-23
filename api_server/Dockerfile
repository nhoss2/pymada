FROM python:3.7-slim

RUN apt-get update && apt-get install -y make --no-install-recommends

WORKDIR /usr/src

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./api_server/

WORKDIR /usr/src/api_server

RUN rm -f db.sqlite3 && python manage.py makemigrations && python manage.py migrate

EXPOSE 8000


CMD ["python", "control.py"]
