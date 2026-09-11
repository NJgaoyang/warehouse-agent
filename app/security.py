import base64
import hashlib
from cryptography.fernet import Fernet
from app.config import settings


class SecretBox:
    def __init__(self):
        raw = hashlib.sha256(settings().app_secret_key.encode()).digest()
        self.fernet = Fernet(base64.urlsafe_b64encode(raw))

    def encrypt(self, value: str | None) -> str | None:
        return self.fernet.encrypt(value.encode()).decode() if value else None

    def decrypt(self, value: str | None) -> str | None:
        return self.fernet.decrypt(value.encode()).decode() if value else None
