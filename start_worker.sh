#!/bin/sh

/opt/app-root/bin/rq worker -u "$REDIS_URL"
