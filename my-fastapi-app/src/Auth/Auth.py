from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from Models.models import User  # Assuming you have a User model defined in models.py
from database import SessionLocal

def get_current_user(db: Session = Depends(SessionLocal)):
    # Logic to retrieve the current user from the database
    # This is a placeholder implementation
    user = db.query(User).filter(User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not authenticated")
    return user