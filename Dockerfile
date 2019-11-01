FROM python:3.7-slim-buster
MAINTAINER Computer Science House <rtp@csh.rit.edu>

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libsndfile-dev libldap-dev libsasl2-dev python3-dev libpq-dev && \
    apt-get autoremove --yes && \
    apt-get clean all && \
    rm -rf /var/lib/{apt,dpkg,cache,log}/ && \
    mkdir -p /opt/audiophiler /var/lib/audiophiler

WORKDIR /opt/audiophiler

ADD . /opt/audiophiler

RUN pip install \
        --no-warn-script-location \
        --no-cache-dir \
        -r requirements.txt

CMD ["gunicorn", "audiophiler:app", "--bind=0.0.0.0:8080", "--access-logfile=-", "--timeout=600"]
