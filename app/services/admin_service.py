from fastapi import HTTPException

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"


def login(payload):

    if payload.username != ADMIN_USERNAME:
        raise HTTPException(
            status_code=401,
            detail="Invalid Username"
        )

    if payload.password != ADMIN_PASSWORD:
        raise HTTPException(
            status_code=401,
            detail="Invalid Password"
        )

    return {
        "message": "Admin Login Successful"
    }