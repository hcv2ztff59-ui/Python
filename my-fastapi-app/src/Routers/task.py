from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from Models.models import Task
from database import SessionLocal

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/tasks/")
async def create_task(task: Task, db: Session = Depends(get_db)):
    db.add(task)
    db.commit()
    db.refresh(task)
    return task

@router.get("/tasks/")
async def read_tasks(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    tasks = db.query(Task).offset(skip).limit(limit).all()
    return tasks

@router.get("/tasks/{task_id}")
async def read_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id_task == task_id).first()
    return task

@router.put("/tasks/{task_id}")
async def update_task(task_id: int, updated_task: Task, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id_task == task_id).first()
    if task:
        for key, value in updated_task.dict().items():
            setattr(task, key, value)
        db.commit()
        db.refresh(task)
        return task
    return {"error": "Task not found"}

@router.delete("/tasks/{task_id}")
async def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id_task == task_id).first()
    if task:
        db.delete(task)
        db.commit()
        return {"message": "Task deleted"}
    return {"error": "Task not found"}