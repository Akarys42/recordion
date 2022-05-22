import asyncpg
from asyncpg import Connection, UniqueViolationError
from fastapi import APIRouter, Depends, FastAPI, HTTPException
from jose import jwt
from starlette.requests import Request
from starlette.responses import Response

from recordion.auth import JWTBearer, check_auth
from recordion.constants import (
    ALLOWED_RECORDS,
    DEFAULT_TTL,
    DNS_DATABASE_URL,
    LOCKED_RECORD_TYPES,
    SECRET_KEY,
    SOA_EXPIRE,
    SOA_MNAME,
    SOA_REFRESH,
    SOA_RETRY,
    SOA_RNAME,
    SOA_TTL,
)
from recordion.models import Domain, NewDomain, NewRecord, Record, TokenRequest, UpdateRecord
from recordion.utils import bump_serial

app = FastAPI()
app.state.conn: Connection

require_auth = APIRouter(dependencies=[Depends(JWTBearer())])


@app.on_event("startup")
async def startup() -> None:
    """Create asyncpg connection on startup."""
    app.state.conn = await asyncpg.connect(DNS_DATABASE_URL)


@app.get("/", include_in_schema=False)
async def index() -> Response:
    """Index page redirecting to /docs."""
    return Response(status_code=302, headers={"Location": "/docs"})


@require_auth.get("/domains")
async def get_domains(request: Request) -> list[Domain]:
    """Return all the currently registered domains."""
    domains = []

    async with app.state.conn.transaction():
        async for record in app.state.conn.cursor("SELECT (id, name) FROM domains"):
            id_, name = record["row"]

            if check_auth(request, name, do_raise=False):
                domains.append(Domain(id=id_, name=name))

    return domains


@require_auth.post("/domains")
async def create_domain(request: Request, domain: NewDomain) -> Domain:
    """Create a new domain."""
    check_auth(request, domain.name)

    async with app.state.conn.transaction():
        # Create the new domain
        try:
            id_ = await app.state.conn.fetchval(
                "INSERT INTO domains (name, type) VALUES ($1, 'NATIVE') RETURNING id", domain.name
            )
        except UniqueViolationError:
            raise HTTPException(status_code=409, detail="Domain already exists")

        # Add the SOA record
        soa_record = f"{SOA_MNAME} {SOA_RNAME} 1 {SOA_REFRESH} {SOA_RETRY} {SOA_EXPIRE}"

        await app.state.conn.execute(
            "INSERT INTO records (domain_id, name, content, type, ttl, prio) "
            "VALUES ($1, $2, $3, 'SOA', $4, NULL)",
            id_,
            domain.name,
            soa_record,
            SOA_TTL,
        )

    return Domain(id=id_, name=domain.name)


@require_auth.delete("/domains/{domain}")
async def delete_domain(request: Request, domain: str) -> None:
    """Delete a domain."""
    check_auth(request, domain)

    async with app.state.conn.transaction():
        await app.state.conn.execute(
            "DELETE FROM records WHERE domain_id = (SELECT id FROM domains WHERE name = $1)", domain
        )
        response = await app.state.conn.execute("DELETE FROM domains WHERE name = $1", domain)

        if response == "DELETE 0":
            raise HTTPException(status_code=404, detail="Domain not found")


@require_auth.get("/records/{domain}")
async def get_records(request: Request, domain: str) -> list[Record]:
    """Return all the records for a domain."""
    check_auth(request, domain)

    records = []

    domain_id = await app.state.conn.fetchval("SELECT id FROM domains WHERE name = $1", domain)
    if not domain_id:
        raise HTTPException(status_code=404, detail="Domain not found")

    async with app.state.conn.transaction():
        async for record in app.state.conn.cursor(
            "SELECT (id, name, content, type, ttl, prio) FROM records WHERE domain_id = $1",
            domain_id,
        ):
            id_, name, content, type_, ttl, prio = record["row"]
            records.append(
                Record(
                    id=id_,
                    domain=domain,
                    name=name,
                    content=content,
                    type=type_,
                    ttl=ttl,
                    prio=prio,
                    can_edit=type_ not in LOCKED_RECORD_TYPES,
                )
            )

    return records


@require_auth.post("/records/{domain}")
async def create_record(request: Request, domain: str, record: NewRecord) -> Record:
    """Create a new record on the selected domain."""
    check_auth(request, domain)

    domain_id = await app.state.conn.fetchval("SELECT id FROM domains WHERE name = $1", domain)
    if not domain_id:
        raise HTTPException(status_code=404, detail="Domain not found")

    # Check the record is part of the domain
    if not record.name.endswith(domain):
        raise HTTPException(status_code=400, detail="Record name must be part of the domain")

    # Check the record type is valid
    if record.type not in ALLOWED_RECORDS:
        raise HTTPException(
            status_code=400,
            detail=f"Record type is not allowed (must be one of {', '.join(ALLOWED_RECORDS)}).",
        )

    # Check that record doesn't already exist
    record_id = await app.state.conn.fetchval(
        "SELECT id FROM records WHERE domain_id = $1 AND name = $2 AND type = $3",
        domain_id,
        record.name,
        record.type,
    )
    if record_id:
        raise HTTPException(status_code=409, detail=f"Record already exists ({record_id})")

    async with app.state.conn.transaction():
        try:
            id_ = await app.state.conn.fetchval(
                "INSERT INTO records (domain_id, name, content, type, ttl, prio) "
                "VALUES ($1, $2, $3, $4, $5, $6) RETURNING id",
                domain_id,
                record.name,
                record.content,
                record.type,
                record.ttl or DEFAULT_TTL,
                record.prio,
            )
        except UniqueViolationError:
            raise HTTPException(status_code=409, detail="Record already exists")

    await bump_serial(domain_id, app.state.conn)

    return Record(
        id=id_,
        domain=domain,
        name=record.name,
        content=record.content,
        type=record.type,
        ttl=record.ttl or DEFAULT_TTL,
        prio=record.prio,
        can_edit=record.type not in LOCKED_RECORD_TYPES,
    )


@require_auth.patch("/records/{domain}/{record_id}")
async def update_record(
    request: Request, domain: str, record_id: int, update_data: UpdateRecord
) -> Record:
    """Modify an existing record by ID."""
    check_auth(request, domain)

    domain_id = await app.state.conn.fetchval("SELECT id FROM domains WHERE name = $1", domain)
    if not domain_id:
        raise HTTPException(status_code=404, detail="Domain not found")

    record = await app.state.conn.fetch(
        "SELECT * FROM records WHERE domain_id = $1 AND id = $2", domain_id, record_id
    )
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    record = record[0]

    # Check if that record can be updated
    if record["type"] in LOCKED_RECORD_TYPES:
        raise HTTPException(status_code=400, detail="Record cannot be edited")

    # Update the record
    new_content = update_data.content or record["content"]
    new_ttl = update_data.ttl or record["ttl"]
    new_prio = update_data.prio or record["prio"]

    async with app.state.conn.transaction():
        await app.state.conn.execute(
            "UPDATE records SET content = $1, ttl = $2, prio = $3 WHERE id = $4",
            new_content,
            new_ttl,
            new_prio,
            record_id,
        )

    await bump_serial(domain_id, app.state.conn)

    return Record(
        id=record_id,
        domain=domain,
        name=record["name"],
        content=new_content,
        type=record["type"],
        ttl=new_ttl,
        prio=new_prio,
        can_edit=record["type"] not in LOCKED_RECORD_TYPES,
    )


@require_auth.delete("/records/{domain}/{record_id}")
async def delete_record(request: Request, domain: str, record_id: int) -> None:
    """Delete a record by ID."""
    check_auth(request, domain)

    domain_id = await app.state.conn.fetchval("SELECT id FROM domains WHERE name = $1", domain)
    if not domain_id:
        raise HTTPException(status_code=404, detail="Domain not found")

    record = await app.state.conn.fetch(
        "SELECT * FROM records WHERE domain_id = $1 AND id = $2", domain_id, record_id
    )
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    record = record[0]

    # Check if that record can be deleted
    if record["type"] in LOCKED_RECORD_TYPES:
        raise HTTPException(status_code=400, detail="Record cannot be deleted")

    await bump_serial(domain_id, app.state.conn)

    async with app.state.conn.transaction():
        await app.state.conn.execute("DELETE FROM records WHERE id = $1", record_id)


@require_auth.post("/generate-token")
async def generate_token(request: Request, token_req: TokenRequest) -> str:
    """Generate a new JWT for the provided namespace."""
    if request.state.auth_namespace != "*":
        raise HTTPException(status_code=403, detail="Require wildcard token")

    return jwt.encode({"n": token_req.namespace}, SECRET_KEY, algorithm="HS256")


if SECRET_KEY == "development":

    @app.get("/dev-token")
    async def dev_token() -> str:
        """Generate a developer token."""
        return jwt.encode({"n": "*"}, SECRET_KEY, algorithm="HS256")


app.include_router(require_auth)
