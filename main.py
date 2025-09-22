from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
import time

app = FastAPI()
submissions = []

class Submission(BaseModel):
    student_name: str
    reference: str
    mt_output: str
    student_translation: str
    score: float
    timestamp: float

@app.post("/submit/")
def submit_translation(sub: Submission):
    submissions.append(sub.dict())
    return {"status": "success"}

@app.get("/submissions/", response_model=List[Submission])
def get_submissions():
    return submissions
