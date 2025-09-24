from fastapi import FastAPI
from pydantic import BaseModel
from typing import List

app = FastAPI(title="Translation Backend API")

# Data storage
submissions = []

class Submission(BaseModel):
    student: str
    translation: str
    score: float
    time_taken: float

@app.post("/submissions/")
def add_submission(sub: Submission):
    submissions.append(sub.dict())
    return {"message": "Submission added successfully"}

@app.get("/submissions/", response_model=List[Submission])
def get_submissions():
    return submissions
