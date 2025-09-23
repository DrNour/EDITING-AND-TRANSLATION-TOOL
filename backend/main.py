from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Translation Backend API")

# Allow CORS for your frontend domain
origins = [
    "*",  # For testing you can allow all, later replace with your frontend URL
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# Data storage (in-memory)
# -------------------------
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
