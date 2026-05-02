#!/usr/bin/env python3
from __future__ import annotations
import argparse, os, re, sys
from pathlib import Path

REQUIRED = {
    'owner1': ['PUBLIC_BASE_URL', 'JWT_ISSUER', 'JWT_AUDIENCE'],
    'owner2': ['PUBLIC_BASE_URL', 'OWNER1_JWKS_URL'],
    'owner3': ['PUBLIC_BASE_URL', 'OWNER1_JWKS_URL'],
    'owner4': ['PUBLIC_BASE_URL', 'OWNER1_JWKS_URL', 'KAFKA_BOOTSTRAP_SERVERS'],
    'owner5': ['PUBLIC_BASE_URL', 'OWNER1_JWKS_URL', 'KAFKA_BOOTSTRAP_SERVERS'],
    'owner6': ['PUBLIC_BASE_URL', 'OWNER1_JWKS_URL', 'KAFKA_BOOTSTRAP_SERVERS'],
    'owner7': ['PUBLIC_BASE_URL', 'OWNER1_JWKS_URL', 'KAFKA_BOOTSTRAP_SERVERS'],
    'owner8': ['PUBLIC_BASE_URL', 'OWNER1_JWKS_URL', 'KAFKA_BOOTSTRAP_SERVERS'],
    'owner9': ['PUBLIC_FRONTEND_URL', 'VITE_OWNER1_URL', 'VITE_OWNER8_URL'],
}
URL_KEYS = {'PUBLIC_BASE_URL','OWNER1_JWKS_URL','PUBLIC_FRONTEND_URL','VITE_OWNER1_URL','VITE_OWNER2_URL','VITE_OWNER3_URL','VITE_OWNER4_URL','VITE_OWNER5_URL','VITE_OWNER6_URL','VITE_OWNER7_URL','VITE_OWNER8_URL'}


def parse_env(path: Path) -> dict[str,str]:
    data={}
    for line in path.read_text().splitlines():
        line=line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k,v=line.split('=',1)
        data[k.strip()]=v.strip()
    return data


def validate_url(url: str) -> bool:
    return bool(re.match(r'^https?://[A-Za-z0-9._:-]+(?:/[A-Za-z0-9._~:/?#\[\]@!$&\'()*+,;=-]*)?$', url))


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument('--env-dir', default='deploy/aws_accounts/env')
    args=parser.parse_args()
    env_dir=Path(args.env_dir)
    errors=[]
    for owner, keys in REQUIRED.items():
        path=env_dir/f'{owner}.env'
        if not path.exists():
            errors.append(f'missing {path}')
            continue
        data=parse_env(path)
        for key in keys:
            if not data.get(key):
                errors.append(f'{owner}: missing {key}')
        for k,v in data.items():
            if k in URL_KEYS and v and not validate_url(v):
                errors.append(f'{owner}: invalid URL for {k}: {v}')
    if errors:
        print('CROSS_ACCOUNT_VALIDATION_FAILED')
        for e in errors:
            print('-', e)
        return 1
    print('CROSS_ACCOUNT_VALIDATION_OK')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
