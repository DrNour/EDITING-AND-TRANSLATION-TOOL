# app.py  — Full crash-resistant enhanced adaptive translation tool
import streamlit as st
import sqlite3
import time
from datetime import datetime
from difflib import SequenceMatcher
import csv
import io

# optional heavy packages — safe imports
try:
    import sacrebleu
except Exception:
    sacrebleu = None
    st.sidebar.warning("sacrebleu not installed → BLEU/chrF/TER disabled")

try:
    from bert_score import score as bert_score
except Exception:
    bert_score = None
    st.sidebar.warning("bert-score not installed → BERT semantic scoring disabled")

# -------------------------
# DB INIT
# -------------------------
DB_PATH = "translations.db"

def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS exercises (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        source TEXT,
        mt_output TEXT,
        reference TEXT,
        created_by TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        exercise_id INTEGER,
        student_name TEXT,
        submission_type TEXT,
        student_text TEXT,
        keystrokes INTEGER,
        time_spent REAL,
        inserts INTEGER,
        deletes INTEGER,
        replaces INTEGER,
        edit_ops INTEGER,
        bleu REAL,
        chrf REAL,
        ter REAL,
        bert_f1 REAL,
        similarity REAL,
        points INTEGER,
        submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.commit()
    conn.close()

init_db()

# -------------------------
# UTILITIES / SCORING
# -------------------------
def token_opcodes(ref, hyp):
    """Return token-level opcode counts and examples (inserts/deletes/replaces)."""
    ref_tokens = (ref or "").split()
    hyp_tokens = (hyp or "").split()
    sm = SequenceMatcher(None, ref_tokens, hyp_tokens)
    inserts = deletes = replaces = 0
    examples = {"insert": [], "delete": [], "replace": []}
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "insert":
            inserts += (j2 - j1)
            examples["insert"].append(" ".join(hyp_tokens[j1:j2]))
        elif tag == "delete":
            deletes += (i2 - i1)
            examples["delete"].append(" ".join(ref_tokens[i1:i2]))
        elif tag == "replace":
            replaces += max(i2 - i1, j2 - j1)
            examples["replace"].append(( " ".join(ref_tokens[i1:i2]), " ".join(hyp_tokens[j1:j2]) ))
    edit_ops = inserts + deletes + replaces
    return {"inserts": inserts, "deletes": deletes, "replaces": replaces, "edit_ops": edit_ops, "examples": examples}

def highlight_html(ref, hyp):
    """Return HTML string highlighting insert/delete/replace at token level."""
    ref_tokens = (ref or "").split()
    hyp_tokens = (hyp or "").split()
    sm = SequenceMatcher(None, ref_tokens, hyp_tokens)
    parts = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            parts.append(" ".join(hyp_tokens[j1:j2]))
        elif tag == "replace":
            stu = " ".join(hyp_tokens[j1:j2])
            refseg = " ".join(ref_tokens[i1:i2])
            parts.append(f"<span title='Replace: {refseg} → {stu}' style='background:#ffd6d6;color:#800'>{stu}</span>")
        elif tag == "insert":
            stu = " ".join(hyp_tokens[j1:j2])
            parts.append(f"<span title='Insertion' style='background:#d6ffd6;color:#060'>{stu}</span>")
        elif tag == "delete":
            refseg = " ".join(ref_tokens[i1:i2])
            parts.append(f"<span title='Missing (should be present): {refseg}' style='background:#d6e0ff;color:#003;text-decoration:line-through'>{refseg}</span>")
    return " ".join(parts)

def compute_scores(hyp, ref):
    """Compute scores safely; return dict with BLEU/chrF/TER/BERT_F1/similarity."""
    out = {"BLEU": None, "chrF": None, "TER": None, "BERT_F1": None, "similarity": None}
    # lexical metrics
    if ref and sacrebleu:
        try:
            out["BLEU"] = round(sacrebleu.corpus_bleu([hyp], [[ref]]).score, 4)
        except Exception:
            out["BLEU"] = None
        try:
            out["chrF"] = round(sacrebleu.corpus_chrf([hyp], [[ref]]).score, 4)
        except Exception:
            out["chrF"] = None
        try:
            out["TER"] = round(sacrebleu.corpus_ter([hyp], [[ref]]).score, 4)
        except Exception:
            out["TER"] = None
    # semantic/BERT
    if ref and bert_score:
        try:
            P, R, F1 = bert_score([hyp], [ref], lang="en", rescale_with_baseline=True)
            out["BERT_F1"] = round(float(F1[0]), 4)
        except Exception:
            out["BERT_F1"] = None
    # fallback similarity (always available)
    try:
        ratio = SequenceMatcher(None, (ref or ""), (hyp or "")).ratio()
        out["similarity"] = round(ratio, 4)
    except Exception:
        out["similarity"] = None
    return out

def compute_points(scores, time_spent, edit_ops):
    """Simple points formula; tweak weights as you like."""
    bleu = scores.get("BLEU") or 0
    bert = scores.get("BERT_F1") or 0
    sim = scores.get("similarity") or 0
    # Normalize scales: BLEU ~ 0-100 or sacrebleu returns 0-100; adjust if needed
    # Basic formula:
    pts = 10  # base
    pts += int(bleu * 0.2)        # BLEU contributes
    pts += int(bert * 0.4)        # BERT contributes more if available
    pts += int(sim * 5)          # similarity (0-1) scaled
    pts -= int(time_spent / 10)  # time penalty
    pts -= int(edit_ops * 0.5)   # edit penalty
    if pts < 0:
        pts = 0
    return int(pts)

# -------------------------
# SESSION STATE UTILITIES
# -------------------------
if "keystrokes_map" not in st.session_state:
    st.session_state.keystrokes_map = {}   # per exercise id
if "start_time_map" not in st.session_state:
    st.session_state.start_time_map = {}

def start_timer_for(ex_id):
    st.session_state.start_time_map[ex_id] = time.time()

def reset_timer_for(ex_id):
    st.session_state.start_time_map.pop(ex_id, None)
    st.session_state.keystrokes_map[ex_id] = 0

def update_keystrokes(ex_id, area_key):
    prev = st.session_state.get(f"prev_{area_key}", "")
    cur = st.session_state.get(area_key, "")
    if prev is None:
        prev = ""
    if cur is None:
        cur = ""
    delta = abs(len(cur) - len(prev))
    st.session_state.keystrokes_map[ex_id] = st.session_state.keystrokes_map.get(ex_id, 0) + delta
    st.session_state[f"prev_{area_key}"] = cur

# -------------------------
# UI: sidebar + role
# -------------------------
st.set_page_config(page_title="Adaptive Translation Tool", layout="wide")
st.sidebar.title("Adaptive Translation Tool")
role = st.sidebar.radio("You are a:", ["Student", "Instructor"])

# -------------------------
# INSTRUCTOR INTERFACE
# -------------------------
if role == "Instructor":
    st.title("Instructor dashboard")
    tab = st.sidebar.selectbox("Action", ["Create exercise", "View submissions", "Leaderboard", "Export CSV"])
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    if tab == "Create exercise":
        st.header("Create exercise")
        title = st.text_input("Exercise title")
        source = st.text_area("Source text", height=120)
        mt = st.text_area("Machine translation (optional)", height=100)
        ref = st.text_area("Reference translation (optional — hidden from students)", height=120)
        created_by = st.text_input("Your name")
        if st.button("Save exercise"):
            if not source.strip():
                st.error("Provide a source text.")
            else:
                c.execute("INSERT INTO exercises (title, source, mt_output, reference, created_by) VALUES (?,?,?,?,?)",
                          (title or f"Ex {datetime.utcnow().isoformat()}", source, mt, ref, created_by))
                conn.commit()
                st.success("Exercise saved.")
    elif tab == "View submissions":
        st.header("Submissions")
        q = """
        SELECT s.id, s.exercise_id, e.title, e.source, e.mt_output, e.reference,
               s.student_name, s.submission_type, s.student_text, s.keystrokes, s.time_spent,
               s.inserts, s.deletes, s.replaces, s.edit_ops, s.bleu, s.chrf, s.ter, s.bert_f1, s.similarity, s.points, s.submitted_at
        FROM submissions s
        JOIN exercises e ON s.exercise_id = e.id
        ORDER BY s.submitted_at DESC
        """
        rows = c.execute(q).fetchall()
        if not rows:
            st.info("No submissions yet.")
        else:
            # quick dataframe summary
            import pandas as pd
            df = pd.DataFrame(rows, columns=["id","exercise_id","title","source","mt","reference","student","type","text","keystrokes","time",
                                             "inserts","deletes","replaces","edit_ops","bleu","chrf","ter","bert_f1","similarity","points","submitted_at"])
            st.dataframe(df[["submitted_at","student","title","type","bleu","chrf","ter","bert_f1","points"]])

            # detailed view selectable
            sel = st.selectbox("Select submission ID to view details", df["id"].tolist())
            selrow = df[df["id"]==sel].iloc[0]
            st.subheader(f"Submission {selrow['id']} — {selrow['student']}")
            st.write("Source:")
            st.info(selrow["source"])
            st.write("MT output:")
            st.info(selrow["mt"])
            st.write("Reference (instructor only):")
            st.text_area("Reference", selrow["reference"], height=120)
            st.write("Student text:")
            st.text_area("Student text", selrow["text"], height=150)
            st.markdown("**Error categorization**")
            st.write(f"Inserts: {selrow['inserts']}, Deletes: {selrow['deletes']}, Replaces: {selrow['replaces']}, Total edit ops: {selrow['edit_ops']}")
            st.markdown("**Scores**")
            st.write({"BLEU": selrow["bleu"], "chrF": selrow["chrf"], "TER": selrow["ter"], "BERT_F1": selrow["bert_f1"], "similarity": selrow["similarity"]})
            st.markdown("**Highlighted diff (student vs ref)**")
            st.markdown(highlight_html(selrow["reference"], selrow["text"]), unsafe_allow_html=True)
            if st.button("Delete this submission"):
                c.execute("DELETE FROM submissions WHERE id=?", (selrow["id"],))
                conn.commit()
                st.success("Deleted.")
    elif tab == "Leaderboard":
        st.header("Leaderboard")
        q = "SELECT student_name, SUM(points) AS total_points, COUNT(*) as submissions FROM submissions GROUP BY student_name ORDER BY total_points DESC"
        rows = c.execute(q).fetchall()
        if not rows:
            st.info("No points yet.")
        else:
            for i, r in enumerate(rows, start=1):
                st.write(f"{i}. {r[0]} — {r[1]} pts ({r[2]} submissions)")
    elif tab == "Export CSV":
        st.header("Export all submissions")
        q = "SELECT * FROM submissions"
        rows = c.execute(q).fetchall()
        cols = [d[0] for d in c.description]
        if rows:
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(cols)
            writer.writerows(rows)
            st.download_button("Download submissions CSV", data=buf.getvalue(), file_name="submissions.csv", mime="text/csv")
        else:
            st.info("No submissions to export.")
    conn.close()

# -------------------------
# STUDENT INTERFACE
# -------------------------
elif role == "Student":
    st.title("Student — Translate / Post-edit")
    student_name = st.text_input("Your name", value="", key="student_name")
    # get exercises
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    ex_rows = c.execute("SELECT id, title, source, mt_output FROM exercises ORDER BY created_at DESC").fetchall()
    conn.close()

    if not ex_rows:
        st.info("No exercises available yet. Ask your instructor to create one.")
    else:
        choices = [f"{r[0]} — {r[1] or 'Untitled'}" for r in ex_rows]
        sel_idx = st.selectbox("Choose exercise", range(len(choices)), format_func=lambda i: choices[i])
        ex = ex_rows[sel_idx]
        ex_id, ex_title, ex_source, ex_mt = ex[0], ex[1], ex[2], ex[3]

        st.subheader(ex_title or f"Exercise {ex_id}")
        st.markdown("**Source text**")
        st.info(ex_source)
        if ex_mt:
            st.markdown("**Machine translation (you may edit this)**")
            st.info(ex_mt)

        st.markdown("Choose how you want to submit:")
        submission_type = st.radio("", ("Edit MT output", "Submit a new translation"))

        # prepare keys and on_change handlers for keystrokes tracking
        edit_key = f"edit_{ex_id}"
        custom_key = f"custom_{ex_id}"

        def mk_on_change(area_key, exid=ex_id):
            return lambda: update_keystrokes(exid, area_key)

        if submission_type == "Edit MT output":
            default_text = ex_mt or ""
            if edit_key not in st.session_state:
                st.session_state[edit_key] = default_text
                st.session_state[f"prev_{edit_key}"] = default_text
                st.session_state.keystrokes_map[ex_id] = 0
            st.text_area("Edit the machine translation here:", key=edit_key, height=160, on_change=mk_on_change(edit_key))
            student_text = st.session_state.get(edit_key, "")
            keystrokes = st.session_state.keystrokes_map.get(ex_id, 0) or len(student_text)
        else:
            # new translation
            if custom_key not in st.session_state:
                st.session_state[custom_key] = ""
                st.session_state[f"prev_{custom_key}"] = ""
                st.session_state.keystrokes_map[ex_id] = 0
            st.text_area("Write your translation here:", key=custom_key, height=160, on_change=mk_on_change(custom_key))
            student_text = st.session_state.get(custom_key, "")
            keystrokes = st.session_state.keystrokes_map.get(ex_id, 0) or len(student_text)

        # Timer controls
        if st.button("Start timer"):
            start_timer_for(ex_id)
            st.success("Timer started. Work now and submit when ready.")
        if st.button("Reset timer / keystrokes"):
            reset_timer_for(ex_id)
            st.success("Timer reset.")

        # On submit
        if st.button("Submit"):
            if not student_name.strip():
                st.error("Please enter your name before submitting.")
            else:
                start_t = st.session_state.start_time_map.get(ex_id)
                if not start_t:
                    st.warning("Timer not started. Submitting anyway will record zero time.")
                    time_spent = 0.0
                else:
                    time_spent = round(time.time() - start_t, 2)
                # compute token ops vs reference (we need reference from DB)
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                row = c.execute("SELECT reference, mt_output FROM exercises WHERE id=?", (ex_id,)).fetchone()
                conn.close()
                reference = (row[0] or "") if row else ""
                ops = token_opcodes(reference, student_text)
                scores = compute_scores(student_text, reference)
                pts = compute_points(scores, time_spent, ops["edit_ops"])
                # store submission
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("""
                    INSERT INTO submissions (exercise_id, student_name, submission_type, student_text,
                                             keystrokes, time_spent, inserts, deletes, replaces, edit_ops,
                                             bleu, chrf, ter, bert_f1, similarity, points)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (ex_id, student_name, submission_type, student_text, keystrokes, time_spent,
                      ops["inserts"], ops["deletes"], ops["replaces"], ops["edit_ops"],
                      scores.get("BLEU"), scores.get("chrF"), scores.get("TER"), scores.get("BERT_F1"),
                      scores.get("similarity"), pts))
                conn.commit()
                conn.close()
                # reset timer and keystroke map after submission for that exercise
                reset_timer_for(ex_id)
                st.success(f"Submission saved — {pts} points awarded.")
                # show immediate feedback
                st.subheader("Scores")
                st.json(scores)
                st.write(f"Points awarded: **{pts}**")
                st.write(f"Keystrokes recorded (approx): {keystrokes}")
                st.write(f"Time spent: {time_spent} sec")
                st.markdown("### Error categories & examples")
                st.write(f"Inserts: {ops['inserts']}, Deletes: {ops['deletes']}, Replaces: {ops['replaces']}, Total ops: {ops['edit_ops']}")
                st.write("Examples:")
                if ops["examples"]["insert"]:
                    st.write("Insert examples (student added):", ops["examples"]["insert"][:5])
                if ops["examples"]["delete"]:
                    st.write("Delete examples (student missing):", ops["examples"]["delete"][:5])
                if ops["examples"]["replace"]:
                    st.write("Replace examples (ref → student):", ops["examples"]["replace"][:5])
                st.markdown("### Highlighted differences (student vs reference)")
                st.markdown(highlight_html(reference, student_text), unsafe_allow_html=True)

# End of app
