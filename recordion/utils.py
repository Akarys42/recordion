from recordion.constants import DOMAIN_RE


def validate_domain(domain: str) -> None:
    """Raise ValueError if domain is invalid."""
    if not DOMAIN_RE.match(domain):
        raise ValueError("Invalid domain name")

    if len(domain) > 255:
        raise ValueError("Domain name too long")
