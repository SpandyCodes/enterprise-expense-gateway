import uuid

from app.models.user import User
from app.security.jwt import hash_password


async def make_user(db, role: str, manager_id=None, department: str = "Engineering") -> User:
    tag = uuid.uuid4().hex[:8]
    user = User(
        employee_id=f"{role[:3]}{tag}",
        name=f"Test {role.title()}",
        email=f"{role.lower()}-{tag}@example-local.test",
        department=department,
        role=role,
        manager_id=manager_id,
        hashed_password=hash_password("Password123!"),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user