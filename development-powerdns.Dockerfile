FROM debian

EXPOSE 53

RUN apt update && apt install pdns-server pdns-backend-pgsql wait-for-it -y && rm -rf /var/lib/apt/lists/*
COPY development-powerdns.conf /etc/powerdns/pdns.conf

CMD ["wait-for-it", "postgres:5432", "--", "pdns_server", "--daemon=no"]
