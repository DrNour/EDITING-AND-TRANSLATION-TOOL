import streamlit as st
import sqlite3
import time
from datetime import datetime

# Optional packages
try:
    import sacrebleu
except ImportError:
    sacrebleu = None

try:
    from bert_score import score as bert_score
except ImportError:
    bert_score = None

from difflib import SequenceMatcher

# ================= DATABASE =================
def init_db():
    conn = sqlite3.connect("translations.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS exercises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT,
            mt_output TEXT,
            reference TEXT,
            created_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exercise_id INTEGER,
            student_name TEXT,
            student_translation TEXT,
            keystrokes INTEGER,
            time_spent REAL,
            bleu REAL,
            chrf REAL,
            ter REAL,
            bert_f1 REAL,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ================= UTILS =================
def compute_scores(hypothesis, reference):
    results = {}
    if reference.strip() and sacrebleu:
        results["BLEU"] = sacrebleu.corpus_bleu([hypothesis], [[reference]]).score
        results["chrF"] = sacrebleu.corpus_chrf([hypothesis], [[reference]]).score
        results["TER"] = sacrebleu.corpus_ter([hypothesis], [[reference]]).score
    else:
        results.update({"BLEU": None, "chrF": None, "TER": None})
    if bert_score and reference.strip():
        try:
            P, R, F1 = bert_score([hypothesis], [reference], lang="en", rescale_with_baseline=True)
            results["BERT_F1"] = float(F1[0])
        except:
            results["BERT_F1"] = None
    else:
        results["BERT_F1"] = None
    return results

def highlight_diff(reference, hypothesis):
    matcher = SequenceMatcher(None, reference.split(), hypothesis.split())
    result = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            result.append(" ".join(hypothesis.split()[j1:j2]))
        elif tag == "replace":
            result.append(f"**[REP: {' '.join(hypothesis.split()[j1:j2])}]**")
        elif tag == "insert":
            result.append(f"**[INS: {' '.join(hypothesis.split()[j1:j2])}]**")
        elif tag == "delete":
            result.append(f"**[DEL: {' '.join(reference.split()[i1:i2])}]**")
    return " ".join(result)

# ================= APP =================
st.sidebar.title("Navigation")
role = st.sidebar.selectbox("I am a", ["Student", "Instructor"])

# ---------- INSTRUCTOR ----------
if role == "Instructor":
    st.title("📚 Instructor Dashboard")
    menu = st.sidebar.radio("Choose Action", ["Create Exercise", "View Submissions", "Leaderboard"])

    if menu == "Create Exercise":
        st.subheader("Create a New Exercise")
        source = st.text_area("Source Text")
        mt_output = st.text_area("Machine Translation")
        reference = st.text_area("Reference Translation (optional)")
        instructor_name = st.text_input("Instructor Name")
        if st.button("Save Exercise"):
            conn = sqlite3.connect("translations.db")
            c = conn.cursor()
            c.execute("INSERT INTO exercises (source, mt_output, reference, created_by) VALUES (?, ?, ?, ?)",
                      (source, mt_output, reference, instructor_name))
            conn.commit()
            conn.close()
            st.success("Exercise saved!")

    elif menu == "View Submissions":
        st.subheader("Student Submissions")
        conn = sqlite3.connect("translations.db")
        c = conn.cursor()
        c.execute("""
            SELECT s.id, s.student_name, e.source, e.mt_output, e.reference, s.student_translation,
                   s.bleu, s.chrf, s.ter, s.bert_f1, s.time_spent, s.keystrokes, s.submitted_at
            FROM submissions s
            JOIN exercises e ON s.exercise_id = e.id
            ORDER BY s.submitted_at DESC
        """)
        rows = c.fetchall()
        conn.close()
        for r in rows:
            st.markdown(f"""
            **Student:** {r[1]}  
            **Submitted At:** {r[12]}  
            **Source:** {r[2]}  
            **MT Output:** {r[3]}  
            **Student Translation:** {r[5]}  
            **Reference:** {r[4]}  

            📊 **Scores**  
            - BLEU: {r[6]}  
            - chrF: {r[7]}  
            - TER: {r[8]}  
            - BERT F1: {r[9]}  

            ⌛ **Time Spent:** {r[10]} sec  
            ⌨️ **Keystrokes:** {r[11]}  
            """)
            st.markdown("---")

    elif menu == "Leaderboard":
        st.subheader("Leaderboard")
        conn = sqlite3.connect("translations.db")
        c = conn.cursor()
        c.execute("""
            SELECT student_name, SUM(bleu) as total_bleu
            FROM submissions
            GROUP BY student_name
            ORDER BY total_bleu DESC
        """)
        leaderboard = c.fetchall()
        conn.close()
        for i, row in enumerate(leaderboard, 1):
            st.markdown(f"{i}. {row[0]} - Total BLEU: {row[1]}")

# ---------- STUDENT ----------
elif role == "Student":
    st.title("✍️ Student Translation & Editing")
    student_name = st.text_input("Enter Your Name")
    conn = sqlite3.connect("translations.db")
    c = conn.cursor()
    c.execute("SELECT id, source, mt_output, reference FROM exercises ORDER BY created_at DESC")
    exercises = c.fetchall()
    conn.close()

    if not exercises:
        st.warning("No exercises yet. Please wait for your instructor.")
    else:
        choice = st.selectbox("Choose Exercise", [f"Exercise {e[0]}" for e in exercises])
        selected = exercises[int(choice.split()[1])-1]

        st.markdown(f"**Source Text:** {selected[1]}")
        st.markdown(f"**Machine Translation:** {selected[2]}")

        start_time = time.time()
        student_translation = st.text_area("Your Translation / Edit Here", value=selected[2])
        keystrokes = len(student_translation)

        if st.button("Submit"):
            end_time = time.time()
            time_spent = round(end_time - start_time, 2)
            scores = compute_scores(student_translation, selected[3] or "")
            highlighted = highlight_diff(selected[3] or "", student_translation)

            conn = sqlite3.connect("translations.db")
            c = conn.cursor()
            c.execute("""
                INSERT INTO submissions (exercise_id, student_name, student_translation, keystrokes, time_spent,
                                         bleu, chrf, ter, bert_f1)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (selected[0], student_name, student_translation, keystrokes, time_spent,
                  scores.get("BLEU"), scores.get("chrF"), scores.get("TER"), scores.get("BERT_F1")))
            conn.commit()
            conn.close()

            st.success("✅ Submission saved!")
            st.markdown("**Highlighted Differences:**")
            st.markdown(highlighted)
            st.json(scores)
