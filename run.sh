#!/bin/sh

if [ -z "$HTTPS_CERT" ] || [ -z "$HTTPS_KEY" ]; then
    export HTTPS_CERT=$(pwd)/cert.pem
    export HTTPS_KEY=$(pwd)/key.pem

    if [ -e $HTTPS_CERT ] || [ -e $HTTPS_KEY ]; then
        echo "There is a key or cert in the directory already, please remove it before generating a new one"
        echo "Skiping self signed certificate generation"
    else
        openssl req -x509 -newkey rsa:4096 -keyout $HTTPS_KEY -out $HTTPS_CERT -days 365 -subj "/C=BR/ST=Paraiba/L=Campina Grande/O=Stenio Araujo/OU=Stenio/CN=merge-issues-slash.duckdns.org" -nodes
    fi
    ls -l $HTTPS_CERT $HTTPS_KEY
fi

export FLASK_APP=$(pwd)/app.py
flask run --cert $HTTPS_CERT --key $HTTPS_KEY --host 0.0.0.0 --port 8080 --debugger
