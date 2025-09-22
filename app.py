from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
import pandas as pd
import random
import os
import difflib
import Levenshtein

# Optional ML/NLP imports
try:
    import sacrebleu
except ImportError:
    sacrebleu = None

try:
    from bert_score import score as bert_score
except ImportError:
    bert_score = None

try:
    import language_tool_python
    tool = language_tool_python.LanguageTool('en-US')
except ImportError:
    tool = None

import nltk
from nltk.collocations import BigramCollocationFinder, BigramAssocMeasures
nltk.download('punkt')

app = FastAPI(title="Translation & Writing Assistant")

# -----------------------
# Data Models
# -----------------------
class Submission(BaseModel):
    student_name: str
    reference: str
    mt_output: str
    student_translation: str

# -----------------------
# Helper Functions
# -----------------------
def calculate_metrics(hypothesis, reference):
    results = {}
    if sacrebleu:
        bleu = sacrebleu.corpus_bleu([hypothesis], [[reference]])
        chrf = sacrebleu.corpus_chrf([hypothesis], [[reference]])
        ter = sacrebleu.corpus_ter([hypothesis], [[reference]])
        results["BLEU"] = round(bleu.score, 2)
        results["chrF"] = round(chrf.score, 2)
        results["TER"] = round(ter.score, 2)
    else:
        results["BLEU"] = None
        results["chrF"] = None
        results["TER"] = None

    if bert_score:
        P, R, F1 = bert_score([hypothesis], [reference], lang="en", verbose=False)
        results["BERT_F1"] = round(F1.mean().item() * 100, 2)
    else:
        results["BERT_F1"] = None
    return results

def highlight_differences(original, edited):
    diff = difflib.ndiff(original.split(), edited.split())
    highlighted = []
    for word in diff:
        if word.startswith("+"):
            highlighted.append(f"[+]{word[2:]}")
        elif word.startswith("-"):
            highlighted.append(f"[-]{word[2:]}")
        else:
            highlighted.append(word[2:])
    return " ".join(highlighted)

def classify_errors(hypothesis, reference):
    errors = []
    hyp_words = hypothesis.split()
    ref_words = reference.split()
    for i, word in enumerate(hyp_words):
        if i < len(ref_words) and word != ref_words[i]:
            errors.append(f"Word mismatch: '{word}' vs '{ref_words[i]}'")
    if len(hyp_words) > len(ref_words):
        errors.append("Extra words detected (addition error)")
    elif len(hyp_words) < len(ref_words):
        errors.append("Missing words detected (omission error)")
    return errors

def assess_fluency(text):
    if tool:
        matches = tool.check(text)
        return f"Fluency Issues: {len(matches)} potential grammar/style problems"
    else:
        words = text.split()
        ttr = len(set(words)) / len(words) if words else 0
        return f"Approximate Fluency (Type–Token Ratio): {round(ttr, 2)}"

def suggest_exercises(errors):
    suggestions = []
    for e in errors:
        if "mismatch" in e:
            suggestions.append("Practice synonyms: write 3 alternatives for key terms.")
        elif "order" in e:
            suggestions.append("Rearrange sentences exercise.")
        elif "missing" in e:
            suggestions.append("Complete-the-sentence activity.")
        elif "Extra" in e:
            suggestions.append("Paraphrase exercise: rewrite sentences concisely.")
    return suggestions or ["Try paraphrasing the reference translation."]

def generate_dynamic_exercises(text):
    exercises = []
    words = text.split()
    if len(words) > 5:
        sample_words = random.sample(words, min(2, len(words)))
        masked = " ".join(["____" if w in sample_words else w for w in words])
        exercises.append(f"Fill in the blanks: {masked}")
    if len(words) > 3:
        target_word = random.choice(words)
        exercises.append(f"Find 2 synonyms for the word: '{target_word}'")
    sentences = text.split(". ")
    if len(sentences) > 1:
        shuffled = sentences.copy()
        random.shuffle(shuffled)
        exercises.append("Reorder these sentences: " + " | ".join(shuffled))
    return exercises or ["Rewrite the translation in a simpler style."]

def extract_collocations(text):
    words = text.split()
    finder = BigramCollocationFinder.from_words(words)
    scored = finder.score_ngrams(BigramAssocMeasures.pmi)
    return [" ".join(pair) for pair, score in scored[:3]]

def generate_idioms():
    idioms = [
        "Break the ice – to start a conversation.",
        "Hit the books – to study hard.",
        "Under the weather – feeling sick."
    ]
    return random.sample(idioms, 2)

def fun_activity():
    activities = [
        "Create a short story using the idiom 'break the ice'.",
        "Translate a proverb from your native language into English.",
        "Record yourself reading your sentence aloud and check fluency."
    ]
    return random.choice(activities)

# -----------------------
# Endpoints
# -----------------------
@app.post("/submit/")
def submit_translation(sub: Submission):
    metrics = calculate_metrics(sub.student_translation, sub.reference)
    edit_distance = Levenshtein.distance(sub.student_translation, sub.reference)
    diff_text = highlight_differences(sub.reference, sub.student_translation)
    errors = classify_errors(sub.student_translation, sub.reference)
    fluency = assess_fluency(sub.student_translation)
    suggested = suggest_exercises(errors)
    dynamic_ex = generate_dynamic_exercises(sub.student_translation)
    collos = extract_collocations(sub.student_translation)
    idioms = generate_idioms()
    activity = fun_activity()

    # Save submission
    new_data = {
        "Student": sub.student_name,
        "Reference": sub.reference,
        "MT Output": sub.mt_output,
        "Translation": sub.student_translation,
        "BLEU": metrics.get("BLEU"),
        "chrF": metrics.get("chrF"),
        "TER": metrics.get("TER"),
        "BERT_F1": metrics.get("BERT_F1"),
        "Edit Distance": edit_distance,
        "Fluency": fluency,
        "Errors": "; ".join(errors),
        "Suggested Exercises": "; ".join(suggested),
        "Dynamic Exercises": "; ".join(dynamic_ex),
        "Collocations": "; ".join(collos),
        "Idioms": "; ".join(idioms),
        "Fun Activity": activity
    }

    if os.path.exists("submissions.csv"):
        df = pd.read_csv("submissions.csv")
        df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
    else:
        df = pd.DataFrame([new_data])
    df.to_csv("submissions.csv", index=False)

    return new_data

@app.get("/submissions/")
def get_submissions():
    if not os.path.exists("submissions.csv"):
        return []
    df = pd.read_csv("submissions.csv")
    return df.to_dict(orient="records")
