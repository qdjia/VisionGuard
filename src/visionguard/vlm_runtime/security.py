import hmac

from fastapi import Header, HTTPException, Request


class SessionSecurity:
    def __init__(self, token: str) -> None:
        if len(token) < 24:
            raise ValueError("VLM session token must contain at least 24 characters")
        self._token = token

    def authorize(self, request: Request, supplied: str | None) -> None:
        host = request.client.host if request.client else ""
        if (
            host not in {"127.0.0.1", "::1"}
            or not supplied
            or not hmac.compare_digest(self._token, supplied)
        ):
            raise HTTPException(status_code=404)

    async def dependency(
        self, request: Request, x_visionguard_session: str | None = Header(default=None)
    ) -> None:
        self.authorize(request, x_visionguard_session)
