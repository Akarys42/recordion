from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt
from starlette.requests import Request

from recordion.constants import SECRET_KEY


class JWTBearer(HTTPBearer):
    """Custom authentication capable of parsing our JWTs."""

    async def __call__(self, request: Request) -> str:
        """Parse the JWT from the request."""
        credentials: HTTPAuthorizationCredentials = await super().__call__(request)
        token = credentials.credentials

        if not token:
            raise HTTPException(status_code=401, detail="Missing JWT")

        try:
            token_data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        except jwt.JWTError:
            raise HTTPException(status_code=403, detail="Invalid JWT")

        if "n" not in token_data:
            raise HTTPException(status_code=403, detail="Invalid JWT")

        request.state.auth_namespace = token_data["n"]
        return token


def check_auth(request: Request, domain: str, do_raise: bool = True) -> bool:
    """Check if the client is authorized to modify this domain."""
    request.state.auth_namespace: str

    if request.state.auth_namespace == "*":
        return True

    namespace_parts = request.state.auth_namespace.count(".") + 1
    domain_suffix = ".".join(domain.split(".")[-namespace_parts:])

    if request.state.auth_namespace != domain_suffix:
        if do_raise:
            raise HTTPException(status_code=403, detail="Authorization for this domain invalid")
        else:
            return False
    return True
