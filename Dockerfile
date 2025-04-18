FROM python:3.9-alpine

COPY ./requirements.txt /app/requirements.txt

WORKDIR /app

RUN echo 'http://dl-cdn.alpinelinux.org/alpine/v3.9/main' >> /etc/apk/repositories
RUN echo 'http://dl-cdn.alpinelinux.org/alpine/v3.9/community' >> /etc/apk/repositories
RUN apk add --update --no-cache --virtual .tmp-build-deps \
    gcc libc-dev linux-headers postgresql-dev mongodb mongodb-tools openssh \
    nginx supervisor && apk add libffi-dev

RUN pip3 install --upgrade pip
RUN pip3 install uwsgi
RUN pip install -r requirements.txt

RUN rm -r /root/.cache

COPY nginx.conf /etc/nginx/
COPY flask-site-nginx.conf /etc/nginx/conf.d/
COPY uwsgi.ini /etc/uwsgi/
COPY supervisord.conf /etc/

RUN mkdir -p /data/db && \
    chown -R mongodb /data/db
VOLUME /data/db
EXPOSE 27017

COPY *.py *.sh /app/

CMD ["/usr/bin/supervisord"]