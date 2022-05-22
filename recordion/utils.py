from asyncpg import Connection

from recordion.constants import DOMAIN_RE


async def bump_serial(domain_id: int, conn: Connection) -> None:
    """Bump the serial number of a domain."""
    async with conn.transaction():
        # Get the current domain SOA
        soa = await conn.fetchrow(
            "SELECT name, content, id FROM records WHERE domain_id = $1 AND type = 'SOA'", domain_id
        )

        # Get the current serial number
        parts = soa["content"].split()
        serial = int(parts[2])
        new_soa = f"{parts[0]} {parts[1]} {serial + 1} {' '.join(parts[3:])}"

        # Update the SOA serial number
        await conn.execute(
            "UPDATE records SET content = $1 WHERE id = $2",
            new_soa,
            soa["id"],
        )


def validate_domain(domain: str) -> None:
    """Raise ValueError if domain is invalid."""
    if not DOMAIN_RE.match(domain):
        raise ValueError("Invalid domain name")

    if len(domain) > 255:
        raise ValueError("Domain name too long")
