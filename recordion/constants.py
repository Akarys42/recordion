import os
import re

DNS_DATABASE_URL = os.getenv("DNS_DATABASE_URL")

SOA_MNAME = os.getenv("SOA_MNAME", "ns.localhost.local")  # Primary nameserver
SOA_RNAME = os.getenv("SOA_RNAME", "admin.localhost.local")  # Email of the administrator
SOA_REFRESH = int(os.getenv("SOA_REFRESH", "3600"))  # Refresh interval of secondary servers
SOA_RETRY = int(os.getenv("SOA_RETRY", "1800"))  # Refresh interval of secondary servers if failed
SOA_EXPIRE = int(os.getenv("SOA_EXPIRE", "43200"))  # Delay before secondary servers stop answering
SOA_TTL = int(os.getenv("SOA_TTL", "3600"))  # Time to live of SOA records

DEFAULT_TTL = int(os.getenv("DEFAULT_TTL", "300"))  # Default TTL for records

DEFAULT_ALLOWED_RECORDS = ("CNAME", "A", "AAAA", "TXT", "NS", "SRV")
ALLOWED_RECORDS = os.getenv("ALLOWED_RECORDS", "").split(",") or DEFAULT_ALLOWED_RECORDS

DOMAIN_RE = re.compile(
    r"^([a-zA-Z0-9]|[a-zA-Z0-9\-]{0,62}[a-zA-Z0-9])"
    r"(\.([a-zA-Z0-9]|[a-zA-Z0-9\-]{0,62}[a-zA-Z0-9]))+$"
)

LOCKED_RECORD_TYPES = ("SOA",)
