#!/usr/bin/env python3
"""Set login email + password for the Kaggle/bulk import recruiter (rec_kaggle_import).

Auth /auth/login uses Pydantic EmailStr — addresses under .invalid are rejected.
This script aligns email to a validator-safe value and refreshes the password hash.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

backend_root = str((Path(__file__).resolve().parents[1] / "backend"))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from services.shared.auth import password_hash  # noqa: E402
from services.shared.relational import execute  # noqa: E402

BULK_RECRUITER_ID = "rec_kaggle_import"
BULK_IMPORT_EMAIL = "bulk-kaggle-recruiter@example.com"
BULK_IMPORT_LOGIN_PASSWORD = "KaggleImport#2026"


def main() -> None:
    ph = password_hash(BULK_IMPORT_LOGIN_PASSWORD)
    nu = execute(
        "UPDATE users SET email=:em, password_hash=:ph WHERE user_id=:uid",
        {"em": BULK_IMPORT_EMAIL, "ph": ph, "uid": BULK_RECRUITER_ID},
    )
    nr = execute(
        "UPDATE recruiters SET email=:em WHERE recruiter_id=:rid",
        {"em": BULK_IMPORT_EMAIL, "rid": BULK_RECRUITER_ID},
    )
    print(
        f"Bulk import recruiter: user rows={nu}, recruiter rows={nr}. "
        f"Sign in: {BULK_IMPORT_EMAIL} / {BULK_IMPORT_LOGIN_PASSWORD}",
        flush=True,
    )


if __name__ == "__main__":
    main()
