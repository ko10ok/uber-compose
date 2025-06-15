# TODO cleanup  no need
#FROM docker:25.0.3-dind-alpine3.19

FROM python:3.10-alpine3.19
#COPY --from=docker:25.0.3-dind-alpine3.19 /usr/local/bin/docker /usr/local/bin/

WORKDIR /tests

ARG TARGETPLATFORM

RUN apk add --no-cache python3 py-pip curl

RUN if [[ "$TARGETPLATFORM" = "linux/amd64" ]] ; then curl -SL https://github.com/docker/compose/releases/download/v2.24.4/docker-compose-linux-x86_64 -o /usr/local/bin/docker-compose ; fi
RUN if [[ "$TARGETPLATFORM" = "linux/arm64" ]] ; then curl -SL https://github.com/docker/compose/releases/download/v2.24.4/docker-compose-linux-aarch64 -o /usr/local/bin/docker-compose ; fi
RUN chmod +x /usr/local/bin/docker-compose

RUN python3 -m venv /venv
RUN /venv/bin/python3 -m pip install --upgrade pip

ADD requirements.txt .
RUN /venv/bin/python3 -m pip install -r requirements.txt

CMD ["sh -c \"trap : TERM INT; sleep 604800 & wait\""]
