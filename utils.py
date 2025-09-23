# utils.py
import difflib
import Levenshtein
import random

# Optional metrics
try:
    import sacrebleu
except ImportError:
    sacrebleu = None

try:
    from bert_score import score as bert_score
except ImportError:
    bert_score = None

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
    return errors

def generate_exercises(errors, text):
    exercises = [f"Correct this: {e}" for e in errors]
    words = text.split()
    if len(words) > 4:
        sample = random.sample(words, 2)
        masked = " ".join(["____" if w in sample else w for w in words])
        exercises.append(f"Fill in the blanks: {masked}")
    return exercises or ["Rewrite the translation."]

def generate_collocations(text):
    words = text.split()
    collos = [" ".join(words[i:i+2]) for i in range(len(words)-1)]
    return collos[:3]

def generate_idioms():
    idioms = [
        "Break the ice – to start a conversation.",
        "Hit the books – to study hard.",
        "Under the weather – feeling sick."
    ]
    return random.sample(idioms, 2)

def fun_activity():
    activities = [
        "Create a short story using 'break the ice'.",
        "Translate a proverb into English.",
        "Read aloud and record yourself."
    ]
    return random.choice(activities)
