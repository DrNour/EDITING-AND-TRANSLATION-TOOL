from fastapi import FastAPI
from pydantic import BaseModel
import pandas as pd
import os
from utils import calculate_metrics, highlight_differences, classify_errors, generate_exercises, generate_collocations, generate_idioms, fun_activity

app = FastAPI(title="Translation API")

class TranslationSubmission(BaseModel):
    student_name: str
    reference: str
    mt_output: str
    student_translation: str

@app.post("/submit/")
def submit_translation(submission: TranslationSubmission):
    metrics = calculate_metrics(submission.student_translation, submission.reference)
    edit_distance = Levenshtein.distance(submission.student_translation, submission.reference)
    diff_text = highlight_differences(submission.reference, submission.student_translation)
    errors = classify_errors(submission.student_translation, submission.reference)
    exercises = generate_exercises(errors, submission.student_translation)
    collos = generate_collocations(submission.student_translation)
    idioms = generate_idioms()
    activity = fun_activity()

    result = {
        "metrics": metrics,
        "edit_distance": edit_distance,
        "diff": diff_text,
        "errors": errors,
        "exercises": exercises,
        "collocations": collos,
        "idioms": idioms,
        "fun_activity": activity
    }

    # Save submission
    new_data = {
        "Student": submission.student_name,
        "Reference": submission.reference,
        "MT Output": submission.mt_output,
        "Translation": submission.student_translation,
        "BLEU": metrics.get("BLEU"),
        "Edit Distance": edit_distance,
        "Errors": "; ".join(errors)
    }
    if os.path.exists("submissions.csv"):
        df = pd.read_csv("submissions.csv")
        df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
    else:
        df = pd.DataFrame([new_data])
    df.to_csv("submissions.csv", index=False)

    return result

@app.get("/submissions/")
def get_submissions():
    if os.path.exists("submissions.csv"):
        df = pd.read_csv("submissions.csv")
        return df.to_dict(orient="records")
    return []
