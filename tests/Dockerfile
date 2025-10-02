ARG PYTHON_VERSION=3.10
FROM python:${PYTHON_VERSION}-alpine3.21

WORKDIR /tests

ARG TARGETPLATFORM

RUN apk add --no-cache python3 py-pip curl docker-cli docker-cli-compose

RUN python3 -m venv /venv
RUN /venv/bin/python3 -m pip install --upgrade pip

ADD requirements.txt .
RUN /venv/bin/python3 -m pip install -r requirements.txt

CMD ["sh -c \"trap : TERM INT; sleep 604800 & wait\""]
