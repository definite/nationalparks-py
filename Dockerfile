FROM registry.access.redhat.com/ubi9/python-312:latest

ENV APP_MODULE=wsgi:application

USER root

COPY . /tmp/src

RUN rm -rf /tmp/src/.git* && \
    chown -R 1001 /tmp/src && \
    chgrp -R 0 /tmp/src && \
    chmod -R g+w /tmp/src

USER 1001

RUN /usr/libexec/s2i/assemble

CMD [ "/usr/libexec/s2i/run" ]
