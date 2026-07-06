"""Create or update a login user. Usage: python scripts/create_user.py <username> <password> [role]"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.auth import hash_password
from app.db import SessionLocal
from app.models import User, UserRole


async def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: python scripts/create_user.py <username> <password> [admin|finance|viewer]")
        sys.exit(1)
    username, password = sys.argv[1], sys.argv[2]
    role = UserRole(sys.argv[3]) if len(sys.argv) > 3 else UserRole.admin

    async with SessionLocal() as session:
        result = await session.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()
        if user:
            user.password_hash = hash_password(password)
            user.role = role
            print(f"Updated existing user '{username}' (role={role.value}).")
        else:
            user = User(username=username, password_hash=hash_password(password), role=role)
            session.add(user)
            print(f"Created user '{username}' (role={role.value}).")
        await session.commit()


if __name__ == "__main__":
    asyncio.run(main())
