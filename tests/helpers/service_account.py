"""A Google service account key file with a freshly generated RSA key."""

import json
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

ACCOUNT = "frame@project.iam.gserviceaccount.com"


def write_key(path: Path, account: str = ACCOUNT) -> Path:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    path.write_text(
        json.dumps(
            {
                "type": "service_account",
                "project_id": "project",
                "private_key_id": "1",
                "private_key": pem.decode(),
                "client_email": account,
                "client_id": "1",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        )
    )
    return path
