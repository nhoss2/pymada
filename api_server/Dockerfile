FROM python:3.7

WORKDIR /usr/src

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./api_server/

EXPOSE 8000

WORKDIR /usr/src/api_server

CMD ["python", "control.py"]
