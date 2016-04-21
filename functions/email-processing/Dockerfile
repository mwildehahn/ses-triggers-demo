# Use centos since that is roughly what runs on Amazon's ec2 instances
FROM centos:centos7

# Install system libraries
RUN yum update -y && yum install -y zip python-devel python-setuptools gcc libffi-devel openssl-devel && easy_install pip && pip install virtualenv

# Create virtualenv we can use to install the dependencies into a specific repository
RUN virtualenv /venv

# Set up a vendored volume
VOLUME /vendored /vendored

ADD . /src

WORKDIR /src

# Install the requirements
ENTRYPOINT ./bin/build
