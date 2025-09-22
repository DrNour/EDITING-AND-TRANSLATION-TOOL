# backend/main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
import pandas as pd
import os

app = FastAPI(title="Translation Training Backend")

# CSV file to store submissions
CSV_FILE = "submissions.csv"

# -------------------------
# Data model
# -------------------------
class Submission(BaseModel):
    student_name: str
    reference: str
    mt_output: str
    student_translation: str
    score: float
    timestamp: float

# -------------------------
# Helper function
# -------------------------
def save_submission(submission: Submission):
    df = pd.DataFrame([submission.dict()])
    if os.path.exists(CSV_FILE):
        df.to_csv(CSV_FILE, mode="a", header=False, index=False)
    else:
        df.to_csv(CSV_FILE, index=False)

def load_submissions():
    if os.path.exists(CSV_FILE):
        return pd.read_csv(CSV_FILE).to_dict(orient="records")
    else:
        return []

# -------------------------
# API endpoints
# -------------------------
@app.post("/submit/")
def submit_translation(submission: Submission):
    try:
        save_submission(submission)
        return {"status": "success", "message": "Submission saved."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/submissions/", response_model=List[Submission])
def get_submissions():
    try:
        return load_submissions()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
