# Recordion
REST API capable of managing DNS records

## Development environment

This project comes with a Docker compose environment, that will start a PowerDNS instance on port 8053.

You can query this server using commands such as `dig @localhost -p 8053 example.com`.

The API will be started on port 8000 by default.
