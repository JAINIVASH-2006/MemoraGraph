"""
MemoraGraph – Create User Account CLI Utility
"""

import asyncio
import os
import sys
import uuid
from getpass import getpass

# Adjust path to import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.config import settings
from app.models.database import init_db, get_session
from app.models.user import User, UserRole
from app.security.auth import hash_password


async def create_user(name: str, email: str, password: str, role_str: str):
    init_db(settings.database_url)
    
    session_gen = get_session()
    session = await anext(session_gen)
    
    # Check if user already exists
    from sqlalchemy import select
    result = await session.execute(select(User).where(User.email == email))
    if result.scalar_one_or_none():
        print(f"Error: User with email '{email}' already exists.")
        return
        
    try:
        role = UserRole(role_str.upper())
    except ValueError:
        print(f"Invalid role '{role_str}'. Allowed: ADMIN, MANAGER, EMPLOYEE")
        return

    # Create user object
    user = User(
        id=str(uuid.uuid4()),
        email=email,
        hashed_password=hash_password(password),
        name=name,
        role=role,
        is_active=True,
    )
    
    session.add(user)
    await session.commit()
    print(f"Success: Created user '{name}' ({email}) with role '{role.value}' in the database.")


def main():
    print("--- MemoraGraph: Create New User ---")
    name = input("Enter Full Name: ").strip()
    if not name:
        print("Name cannot be empty.")
        return
        
    email = input("Enter Email Address: ").strip()
    if not email:
        print("Email cannot be empty.")
        return
        
    password = getpass("Enter Password: ")
    if not password:
        print("Password cannot be empty.")
        return
        
    role = input("Enter Role (ADMIN, MANAGER, EMPLOYEE) [default: EMPLOYEE]: ").strip()
    if not role:
        role = "EMPLOYEE"
        
    asyncio.run(create_user(name, email, password, role))


if __name__ == "__main__":
    main()
