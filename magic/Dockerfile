FROM mageai/mageai:0.9.79

COPY default_repo /home/src/default_repo

ENV PYTHONPATH="/home/src"

WORKDIR /home/src

RUN addgroup --system magegroup && adduser --system --ingroup magegroup mageuser
USER mageuser
