FROM python:3.7.2
MAINTAINER Computer Science House <rtp@csh.rit.edu>

RUN apt-get update && \
    apt-get install -y libsndfile-dev libldap-dev libsasl2-dev && \
    apt-get autoremove --yes && \
    apt-get clean autoclean && \
    rm -rf /var/lib/{apt,dpkg,cache,log}/ && \
    mkdir -p /opt/audiophiler-dev-nate /var/lib/audiophiler-dev-nate

WORKDIR /opt/audiophiler-dev-nate
ADD . /opt/audiophiler-dev-nate

RUN pip install \
        --no-warn-script-location \
        --no-cache-dir \
        -r requirements.txt

RUN groupadd -r audiophiler-dev-nate && \
    useradd -l -r -u 1001 -d /var/lib/audiophiler-dev-nate -g audiophiler-dev-nate audiophiler-dev-nate && \
    chown -R audiophiler-dev-nate:audiophiler-dev-nate /opt/audiophiler-dev-nate /var/lib/audiophiler-dev-nate && \
    chmod -R og+rwx /var/lib/audiophiler-dev-nate

USER audiophiler-dev-nate

CMD gunicorn "wsgi:app" \
    --workers 4 \
    --timeout 600 \
    --capture-output \
    --bind=0.0.0.0:8080 \
    --access-logfile=-