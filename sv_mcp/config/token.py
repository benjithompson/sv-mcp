import json
import base64
from pathlib import Path
from typing import Optional, Union
from functools import lru_cache


class BzmTokenError(Exception):
    """Error when constructing or loading BzmToken."""
    pass


class BzmToken:
    __slots__ = ("id", "secret", "source")

    def __init__(self, token_id: str, token_secret: str, source: Optional[str] = None):
        # Messages never include the values: they are printed at startup.
        if not token_id or not isinstance(token_id, str):
            raise BzmTokenError("Invalid Token ID: it must be a non-empty string")
        if not token_secret or not isinstance(token_secret, str):
            raise BzmTokenError("Invalid Token secret: it must be a non-empty string")

        self.id = token_id
        self.secret = token_secret
        # Where the key came from (e.g. "key file /path/api-key.json"), named in 401 errors
        self.source = source

    @classmethod
    @lru_cache(maxsize=1)
    def from_file(cls, path: Union[str, Path]) -> "BzmToken":
        p = Path(path)
        if not p.exists() or not p.is_file():
            raise BzmTokenError(f"File does not exist: {p!r}")

        try:
            raw = p.read_text(encoding="utf-8")
            data = json.loads(raw)
        except Exception as e:
            # Name the error, not its text: a decode error can quote the file content.
            detail = (f"invalid JSON at line {e.lineno}, column {e.colno}" if isinstance(e, json.JSONDecodeError)
                      else type(e).__name__)
            raise BzmTokenError(f"Error reading/parsing JSON from {p!r}: {detail}") from e

        try:
            id_val = data["id"]
            secret_val = data["secret"]
        except KeyError as e:
            raise BzmTokenError(f"Missing field {e.args[0]!r} in {p!r}") from e

        return cls(token_id=id_val, token_secret=secret_val, source=f"key file {p}")

    def as_basic_auth(self) -> str:
        """
        Returns the HTTP Basic Authentication header:
            "Basic <base64(id:secret)>"
        """
        combo = f"{self.id}:{self.secret}".encode("utf-8")
        token_b64 = base64.b64encode(combo).decode("utf-8")
        return f"Basic {token_b64}"

    def __repr__(self):
        return f"<BzmToken id={self.id!r} secret={'*'*8}>" 

