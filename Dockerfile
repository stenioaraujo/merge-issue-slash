FROM python:3.6

LABEL maintainer="contato@stenioelson.com.br"

# -- Install Pipenv:
RUN pip install flask-api requests

# -- Install Application into container:
RUN mkdir /app

WORKDIR /app

COPY app.py /app
COPY run.sh /app

EXPOSE 8080

ENTRYPOINT ["sh", "run.sh"]
