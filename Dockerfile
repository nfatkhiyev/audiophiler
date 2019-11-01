FROM python:3.7-slim-buster
MAINTAINER Computer Science House <rtp@csh.rit.edu>

RUN apt-get update && \
    apt-get install -y --no-install-recommends apt-utils gcc git libsndfile-dev libldap-dev libsasl2-dev python3-dev libpq-dev && \
    apt-get autoremove --yes && \
    apt-get clean all && \
    rm -rf /var/lib/{apt,dpkg,cache,log}/ && \
    mkdir -p /opt/audiophiler /var/lib/audiophiler

WORKDIR /opt/audiophiler

COPY . /opt/audiophiler

RUN mkdir /tmp/numba_cache & chmod 777 /tmp/numba_cache & NUMBA_CACHE_DIR=/tmp/numba_cache
RUN mkdir /tmp/librosa_cache & chmod 777 /tmp/librosa_cache & LIBROSA_CACHE_DIR=/tmp/librosa_cache

RUN pip install \
        --no-warn-script-location \
        --no-cache-dir \
        -r requirements.txt

CMD ["gunicorn", "audiophiler:app", "--bind=0.0.0.0:8080", "--access-logfile=-", "--timeout=600"]
