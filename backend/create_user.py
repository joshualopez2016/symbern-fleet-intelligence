"""Create or update a user (admin utility).

Usage:
    py backend/create_user.py <email> <password> [role]

role defaults to 'administrator'; must be one of viewer|engineer|supervisor|administrator.
Passwords are stored only as bcrypt hashes.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from app import auth  # noqa: E402
from app.db import pool, query_one  # noqa: E402


def main() -> None:
    if len(sys.argv) < 3:
        sys.exit("usage: create_user.py <email> <password> [role]")
    email = sys.argv[1].lower().strip()
    password = sys.argv[2]
    role = sys.argv[3] if len(sys.argv) > 3 else "administrator"
    if role not in auth.ROLES:
        sys.exit(f"role must be one of {auth.ROLES}")

    pool.open()
    try:
        row = query_one(
            """
            INSERT INTO users (email, password_hash, role)
            VALUES (%s, %s, %s)
            ON CONFLICT (email) DO UPDATE
                SET password_hash = EXCLUDED.password_hash, role = EXCLUDED.role
            RETURNING id, email, role
            """,
            (email, auth.hash_password(password), role),
        )
        print(f"OK: user {row['email']} (role={row['role']}, id={row['id']})")
    finally:
        pool.close()


if __name__ == "__main__":
    main()
