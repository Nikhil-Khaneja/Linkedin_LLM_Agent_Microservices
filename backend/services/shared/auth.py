from __future__ import annotations

import base64
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
import requests
from cryptography.hazmat.primitives import serialization

DEFAULT_KID = os.environ.get('JWT_KID', 'kid_dev_2026_04')
DEFAULT_ISSUER = os.environ.get('JWT_ISSUER', 'owner1-auth')
DEFAULT_AUDIENCE = os.environ.get('JWT_AUDIENCE', 'linkedin-clone')
_ACCESS_TTL_SECONDS = int(os.environ.get('JWT_ACCESS_TTL_SECONDS', '3600'))
_JWKS_CACHE_TTL_SECONDS = int(os.environ.get('JWKS_CACHE_TTL_SECONDS', '300'))
_APP_ENV = os.environ.get('APP_ENV', 'dev').lower()

_DEFAULT_PRIVATE_KEY = """-----BEGIN PRIVATE KEY-----
MIIEvwIBADANBgkqhkiG9w0BAQEFAASCBKkwggSlAgEAAoIBAQC7hgdombf3Bnu0
TgRK0OVJ6POo4Sx/7O7EkgRuZM5xO5NpIL4+gHGVDa9SdU6kvR4AL8Dj9WapGPJ9
o3Kg+PUJ1YR5j1LYWrOEUyIwj71Dj1Vpkl9PofkB3olCuM1Al4RE1TLp+XB3lAYG
kyAKP7n3S1lq5ZdG5T1S4/KmhRfXpRvgZO0M8tfXnIajVpKvdri6ZcHC0mVRyIFu
lgWJTJxNeMbyehaTAAPru4zwN3ZH259kTNPOafJApTFdmhUEdzxTdxetf/m9wNek
N2U2d6I8b4mwDrYWRrnfz9RgDHhEu4b4EgAuVyAlgq7CjZ96cNcVUziSVbnrg1sa
2M3cIjphAgMBAAECggEACjn28XdglvIdkOmoRkQ6HNu9XfpZqOhM5R9panPI5lfv
ZA5LEbGDgDNs2jxXe5hsqGnyRPw/Cv23S668M5cgFdc1EEQGqpHXtGGsPaW5FpQc
flNjKz6UC8wNBDx7xQf+SJqv2h6mSX8jDPy9BJIRHDFZwQCgTVd3DqwrsXUUpcfd
UDCLWgzzrB8O2IRIDs4lpO82z09GW4+Nuzut/hg+TnT76IGgdEgJyCJFt2Nbq1DW
YH21dE2qSY6B1wBIw6dHFu2wwD2g6gGxGqW0B0dM0QADtlHer5jLtjgD+FTD/C8k
BdMTKfwaoAI4th7jo6aUgOq3bqxwB+ppN2AmlMBH2QKBgQDuMlPitWyhK9PeweJ4
GltOfTnDeYfp38qjLV3615BHpxCYIBWQSFr6l3nx1z1ncxFzJivnmtptqgFDQX46
mqdOikKDrUae7N48lhWKdE56fJov2Cktd2kPdB+VF8FUkluFFwIG04ZCQBhL3OYa
fDi5WyCZVT4FY7dVXIdT4dew9wKBgQDJih6KFZq4GS4DKm8MdybX5W/qVgjk9zoW
Njr2XjM0gqTBH6Q0f51LybkXwV6xF8wzT3TgBhFo2jNfmr0tXQ8x9iHVnhDfpCVI
qIFbwzYvUgoEuY5ciSDCakaClpoxz6l7uLqFq6pJeVbaD/GZugNi9Nh9Cz+flvNW
ROG9PmtxZwKBgQCf6Y3DoAVD1sawv/2ooBk4gn2rLAYBD0tdbXGwm9OzJwfO+YtA
iDL8FYG6yMPila/bXH8RSDbodL/QRUHXWkiEQ/IPsN6+h0tT5XaksxyUwt5IzJgo
fAg+ZblmQMJ8Yp2qph2oM43pIFqvY6fflBII7pLeHgo7WAyW9D2uJOrHVQKBgQCJ
GUIpIQU9EzPvx1//lNaBq3x0Zs5qI5wKHB4EFpSyteSp04J6jA1OzwzwkgR+Z/fr
N7QD6VzSfQzRjov+Xf3GOO9PR9WmrR0HzkkhSSyFCEP0bt3fKRF176HDl/uQwvlC
Rqnr4JlYnghtEseBkb5YBMN4XLyNLbyfBQCjIeEpJQKBgQDefvQlFc1aE4M/Da0H
E4k8ukPwoE3sGqEH7ifSfJ4cYkHIOtCh52wo/MXfLRTJ2l3gcxNk35A8uZz7Iaj7
RNFw5nUX7OnYNxSmr6a9JPn+eNwvMpUisbWSqlGGd21rFpZ2PeQ1uqqOeMaWmyh7
GDZ4SB0lgnyTw9GbfRiXvp8qmw==
-----END PRIVATE KEY-----"""

_DEFAULT_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAu4YHaJm39wZ7tE4EStDl
SejzqOEsf+zuxJIEbmTOcTuTaSC+PoBxlQ2vUnVOpL0eAC/A4/VmqRjyfaNyoPj1
CdWEeY9S2FqzhFMiMI+9Q49VaZJfT6H5Ad6JQrjNQJeERNUy6flwd5QGBpMgCj+5
90tZauWXRuU9UuPypoUX16Ub4GTtDPLX15yGo1aSr3a4umXBwtJlUciBbpYFiUyc
TXjG8noWkwAD67uM8Dd2R9ufZEzTzmnyQKUxXZoVBHc8U3cXrX/5vcDXpDdlNnei
PG+JsA62Fka538/UYAx4RLuG+BIALlcgJYKuwo2fenDXFVM4klW564NbGtjN3CI6
YQIDAQAB
-----END PUBLIC KEY-----"""

_DEFAULT_N = "u4YHaJm39wZ7tE4EStDlSejzqOEsf-zuxJIEbmTOcTuTaSC-PoBxlQ2vUnVOpL0eAC_A4_VmqRjyfaNyoPj1CdWEeY9S2FqzhFMiMI-9Q49VaZJfT6H5Ad6JQrjNQJeERNUy6flwd5QGBpMgCj-590tZauWXRuU9UuPypoUX16Ub4GTtDPLX15yGo1aSr3a4umXBwtJlUciBbpYFiUycTXjG8noWkwAD67uM8Dd2R9ufZEzTzmnyQKUxXZoVBHc8U3cXrX_5vcDXpDdlNneiPG-JsA62Fka538_UYAx4RLuG-BIALlcgJYKuwo2fenDXFVM4klW564NbGtjN3CI6YQ"
_DEFAULT_E = "AQAB"

_JWKS_CACHE: dict[str, Any] = {"expires_at": 0.0, "keys": None}


def _b64url_to_int(value: str) -> int:
    padding = '=' * ((4 - len(value) % 4) % 4)
    return int.from_bytes(base64.urlsafe_b64decode(value + padding), 'big')


def _jwt_private_key() -> str:
    return os.environ.get('JWT_PRIVATE_KEY_PEM') or _DEFAULT_PRIVATE_KEY


def _jwt_public_key() -> str:
    return os.environ.get('JWT_PUBLIC_KEY_PEM') or _DEFAULT_PUBLIC_KEY


def _build_default_jwks() -> dict[str, Any]:
    return {
        'keys': [
            {
                'kty': 'RSA',
                'kid': DEFAULT_KID,
                'use': 'sig',
                'alg': 'RS256',
                'n': os.environ.get('JWT_PUBLIC_N') or _DEFAULT_N,
                'e': os.environ.get('JWT_PUBLIC_E') or _DEFAULT_E,
            }
        ]
    }


def current_jwks() -> dict[str, Any]:
    return _build_default_jwks()


def issue_access_token(*, sub: str, role: str, email: str, expires_in: int | None = None, extra_claims: dict[str, Any] | None = None) -> str:
    now = datetime.now(timezone.utc)
    ttl = expires_in or _ACCESS_TTL_SECONDS
    payload = {
        'iss': DEFAULT_ISSUER,
        'aud': DEFAULT_AUDIENCE,
        'sub': sub,
        'role': role,
        'email': email,
        'iat': int(now.timestamp()),
        'nbf': int(now.timestamp()) - 1,
        'exp': int((now + timedelta(seconds=ttl)).timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, _jwt_private_key(), algorithm='RS256', headers={'kid': DEFAULT_KID})


def issue_machine_token(service_name: str) -> str:
    return issue_access_token(sub=service_name, role='internal_service', email=f'{service_name}@internal.local')


def _public_key_from_jwk(jwk: dict[str, Any]) -> str:
    public_numbers = serialization.load_pem_public_key(_jwt_public_key().encode()).public_numbers()
    if jwk.get('n') and jwk.get('e'):
        from cryptography.hazmat.primitives.asymmetric import rsa
        key = rsa.RSAPublicNumbers(_b64url_to_int(jwk['e']), _b64url_to_int(jwk['n'])).public_key()
        return key.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    # fallback should never be needed, but keeps local/dev stable
    return _jwt_public_key()


def _fetch_remote_jwks() -> dict[str, Any] | None:
    url = os.environ.get('OWNER1_JWKS_URL')
    if not url:
        return None
    now = time.time()
    if _JWKS_CACHE['keys'] and _JWKS_CACHE['expires_at'] > now:
        return _JWKS_CACHE['keys']
    try:
        response = requests.get(url, timeout=2.5)
        response.raise_for_status()
        body = response.json()
        keys = body.get('data') or body
        if keys and keys.get('keys'):
            _JWKS_CACHE['keys'] = keys
            _JWKS_CACHE['expires_at'] = now + _JWKS_CACHE_TTL_SECONDS
            return keys
    except Exception:
        return None
    return None


def resolve_verification_key(token: str) -> str:
    header = jwt.get_unverified_header(token)
    kid = header.get('kid', DEFAULT_KID)
    keys = _fetch_remote_jwks() or _build_default_jwks()
    for jwk in keys.get('keys', []):
        if jwk.get('kid') == kid:
            return _public_key_from_jwk(jwk)
    return _jwt_public_key()


def verify_bearer_token(token: str) -> dict[str, Any]:
    public_key = resolve_verification_key(token)
    payload = jwt.decode(
        token,
        public_key,
        algorithms=['RS256'],
        issuer=DEFAULT_ISSUER,
        audience=DEFAULT_AUDIENCE,
        options={'require': ['exp', 'iat', 'sub', 'aud', 'iss']},
    )
    return {
        'sub': payload['sub'],
        'role': payload.get('role', 'member'),
        'email': payload.get('email', ''),
        'claims': payload,
    }


def password_hash(password: str) -> str:
    import hashlib
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def password_matches(password: str, hashed_value: str) -> bool:
    import hashlib, hmac
    return hmac.compare_digest(hashlib.sha256(password.encode('utf-8')).hexdigest(), hashed_value)
