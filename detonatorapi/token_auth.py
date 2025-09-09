from dataclasses import dataclass
from typing import Optional

from .settings import AUTH_TOKEN


@dataclass
class TokenPermissions:
    is_anonymous: bool = True


#if token and not db.query(Profile).filter(Profile.token == token).first():
#    raise HTTPException(status_code=403, detail="Invalid or missing token")


class TokenAuth():
    def get_permissions(self, token: Optional[str]) -> TokenPermissions:
        # Implement logic to retrieve permissions based on the token
        if not token or token == "":  # its disabled, so never anonymous
            return TokenPermissions(False)
        
        if token == AUTH_TOKEN:
            return TokenPermissions(False)
        else:
            return TokenPermissions(True)

tokenAuth: TokenAuth = TokenAuth()
