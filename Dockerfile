FROM python:2.7

MAINTAINER Michael Hahn <mwhahn@gmail.com>

ADD requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

ADD . /app
WORKDIR /app
