import base64


def _b64url_uint(n: int) -> str:
    byte_length = (n.bit_length() + 7) // 8
    data = n.to_bytes(byte_length, "big")
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def rsa_public_key_to_jwk(public_key, kid: str) -> dict:
    public_numbers = public_key.public_numbers()
    return {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": kid,
        "n": _b64url_uint(public_numbers.n),
        "e": _b64url_uint(public_numbers.e),
    }