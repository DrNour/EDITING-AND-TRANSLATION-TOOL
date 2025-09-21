import streamlit as st
import sqlite3
import time
import difflib
import sacrebleu
from bert_score import score as bert_score
from datetime import datetime
from difflib import SequenceMatcher

# Optional COMET
try:
    from comet import load_from_checkpoint
    COMET_AVAILABLE = True
except ImportError:
    COMET_AVAILABLE = False

# ================= DATABASE =================
def init_db():
    conn = sqlite3.connect("translations.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS editing_exercises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT,
            mt_output TEXT,
            reference TEXT,
            created_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS editing_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exercise_id INTEGER,
            student_name TEXT,
            student_edit TEXT,
            time_spent REAL,
            keystrokes INTEGER,
            edit_distance INTEGER,
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
    if reference.strip():
        results["BLEU"] = sacrebleu.corpus_bleu([hypothesis], [[reference]]).score
        results["chrF"] = sacrebleu.corpus_chrf([hypothesis], [[reference]]).score
        results["TER"] = sacrebleu.corpus_ter([hypothesis], [[reference]]).score
        sm = SequenceMatcher(None, hypothesis.split(), reference.split())
        results["edit_distance"] = int(sum(n for _, n in sm.get_opcodes()))
    else:
        results.update({"BLEU": None, "chrF": None, "TER": None, "edit_distance": None})

    try:
        P, R, F1 = bert_score([hypothesis], [reference], lang="en", rescale_with_baseline=True)
        results["BERT_F1"] = float(F1[0])
    except Exception:
        results["BERT_F1"] = None

    return results

# ================= APP =================
st.sidebar.title("Navigation")
role = st.sidebar.selectbox("I am a", ["Student", "Instructor"])

# --------- INSTRUCTOR ---------
if role == "Instructor":
    st.title("📚 Instructor Dashboard")
    menu = st.sidebar.radio("Choose Action", ["Create Editing Exercise", "View Submissions", "Leaderboard"])

    conn = sqlite3.connect("translations.db")
    c = conn.cursor()

    if menu == "Create Editing Exercise":
        st.subheader("Create a New Editing Exercise")
        source = st.text_area("Source Text")
        mt_output = st.text_area("Machine Translation Output")
        reference = st.text_area("Reference Translation (optional)")
        instructor = st.text_input("Instructor Name")

        if st.button("Save Exercise"):
            c.execute(
                "INSERT INTO editing_exercises (source, mt_output, reference, created_by) VALUES (?, ?, ?, ?)",
                (source, mt_output, reference, instructor)
            )
            conn.commit()
            st.success("✅ Exercise created successfully!")

    elif menu == "View Submissions":
        st.subheader("Student Submissions")
        c.execute("""
            SELECT es.id, e.source, e.mt_output, es.student_name, es.student_edit,
                   es.bleu, es.chrf, es.ter, es.bert_f1, es.time_spent, es.keystrokes, es.edit_distance, es.submitted_at
            FROM editing_submissions es
            JOIN editing_exercises e ON es.exercise_id = e.id
            ORDER BY es.submitted_at DESC
        """)
        rows = c.fetchall()

        for r in rows:
            st.markdown(f"""
            **Student:** {r[3]}  
            **Submitted At:** {r[12]}  
            **Source:** {r[1]}  
            **MT Output:** {r[2]}  
            **Student Edit:** {r[4]}  

            📊 **Scores**  
            - BLEU: {r[5]}  
            - chrF: {r[6]}  
            - TER: {r[7]}  
            - BERT F1: {r[8]}  
            - Edit Distance: {r[11]}  

            ⌛ **Time Spent:** {r[9]} sec  
            ⌨️ **Keystrokes:** {r[10]}  
            """)
            st.markdown("---")

    elif menu == "Leaderboard":
        st.subheader("Leaderboard")
        c.execute("""
            SELECT student_name, SUM(COALESCE(bleu,0)+COALESCE(bert_f1,0)) as points
            FROM editing_submissions
            GROUP BY student_name
            ORDER BY points DESC
        """)
        leaderboard = c.fetchall()
        for i, entry in enumerate(leaderboard, start=1):
            st.write(f"{i}. {entry[0]} - Points: {entry[1]}")

    conn.close()

# --------- STUDENT ---------
elif role == "Student":
    st.title("✍️ Student Editing Exercise")
    student_name = st.text_input("Enter your name")
    conn = sqlite3.connect("translations.db")
    c = conn.cursor()
    c.execute("SELECT id, source, mt_output, reference FROM editing_exercises ORDER BY created_at DESC")
    exercises = c.fetchall()

    if not exercises:
        st.warning("⚠️ No exercises available yet. Please wait for your instructor.")
    else:
        choice = st.selectbox("Choose an Exercise", [f"Exercise {e[0]}" for e in exercises])
        selected = exercises[int(choice.split()[1]) - 1]

        st.markdown(f"**Source Text:** {selected[1]}")
        st.markdown(f"**Machine Translation Output:** {selected[2]}")
        reference = selected[3]

        start_time = time.time()
        student_edit = st.text_area("Edit the Translation Here ✍️", value=selected[2])
        keystrokes = len(student_edit)

        if st.button("Submit"):
            end_time = time.time()
            time_spent = round(end_time - start_time, 2)
            scores = compute_scores(student_edit, reference or "")

            c.execute("""
                INSERT INTO editing_submissions
                (exercise_id, student_name, student_edit, time_spent, keystrokes, edit_distance, bleu, chrf, ter, bert_f1)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                selected[0], student_name, student_edit, time_spent, keystrokes,
                scores.get("edit_distance"), scores.get("BLEU"), scores.get("chrF"),
                scores.get("TER"), scores.get("BERT_F1")
            ))
            conn.commit()
            st.success("✅ Submission saved and evaluated!")
            st.json(scores)

    conn.close()
