FROM centos:centos7

RUN yum update -y && yum install -y zip python-devel python-setuptools gcc libffi-devel openssl-devel && easy_install pip && pip install virtualenv
RUN virtualenv /venv
VOLUME /vendored /vendored

ADD . /src

WORKDIR /src

ENTRYPOINT ./bin/build
