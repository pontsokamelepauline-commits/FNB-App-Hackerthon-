import hashlib, hmac, os, secrets, time, base64, json
from dotenv import load_dotenv
load_dotenv()
from typing import Optional

SECRET_KEY = os.getenv("SECRET_KEY", "development-only-change-this-secret-before-deployment")

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return base64.b64encode(salt + digest).decode()

def verify_password(password: str, encoded: str) -> bool:
    try:
        raw = base64.b64decode(encoded.encode())
        salt, expected = raw[:16], raw[16:]
        actual = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False

def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

def create_token(user_id: int, expires_in: int = 60 * 60 * 12) -> str:
    header = _b64(json.dumps({"alg":"HS256","typ":"JWT"}, separators=(",", ":")).encode())
    payload = _b64(json.dumps({"sub":str(user_id),"exp":int(time.time())+expires_in}, separators=(",", ":")).encode())
    msg = f"{header}.{payload}".encode()
    sig = _b64(hmac.new(SECRET_KEY.encode(), msg, hashlib.sha256).digest())
    return f"{header}.{payload}.{sig}"

def read_token(token: str) -> Optional[int]:
    try:
        header, payload, sig = token.split(".")
        msg = f"{header}.{payload}".encode()
        expected = _b64(hmac.new(SECRET_KEY.encode(), msg, hashlib.sha256).digest())
        if not hmac.compare_digest(expected, sig): return None
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        if int(data["exp"]) < int(time.time()): return None
        return int(data["sub"])
    except Exception:
        return None

def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
