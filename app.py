# app.py - StudyBuddy main Flask application and routes
from datetime import date, datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash
from database import get_db, init_db

app = Flask(__name__)
app.secret_key = "studybuddy-change-this-key"  # needed for flash messages
init_db()  # create database + tables on first run

STATUSES = ["Pending", "Ongoing", "Completed"]
PRIORITIES = ["Low", "Medium", "High"]
TYPES = ["Assignment", "Project", "Quiz", "Exam", "Other"]

# Reusable SQL: every task together with its subject name
TASK_SELECT = ("SELECT t.*, s.subject_name FROM tasks t "
               "JOIN subjects s ON t.subject_id = s.subject_id ")


@app.context_processor
def inject_common():
    """Values available in every template."""
    today = date.today()
    return {"today": today.isoformat(),
            "soon": (today + timedelta(days=3)).isoformat(),
            "STATUSES": STATUSES, "PRIORITIES": PRIORITIES, "TYPES": TYPES}


def valid_date(text):
    """True only for real dates written as YYYY-MM-DD."""
    try:
        datetime.strptime(text, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def valid_time(text):
    """True only for times written as HH:MM."""
    try:
        datetime.strptime(text, "%H:%M")
        return True
    except ValueError:
        return False


def back(default):
    """Go back to the page the user came from (keeps search/filter settings)."""
    return redirect(request.referrer or url_for(default))


# ---------------------------------------------------------------- Dashboard
@app.route("/")
def home():
    """First visit (no subjects yet) shows the Get Started page; otherwise the dashboard."""
    conn = get_db()
    n = conn.execute("SELECT COUNT(*) FROM subjects").fetchone()[0]
    conn.close()
    if n:
        return redirect(url_for("dashboard"))
    return render_template("welcome.html")


@app.route("/welcome")
def welcome():
    return render_template("welcome.html")


@app.route("/dashboard")
def dashboard():
    conn = get_db()
    # Statistics are calculated with SQL COUNT()
    count = lambda sql: conn.execute(sql).fetchone()[0]
    subjects = count("SELECT COUNT(*) FROM subjects")
    total = count("SELECT COUNT(*) FROM tasks")
    done = count("SELECT COUNT(*) FROM tasks WHERE status='Completed'")
    ongoing = count("SELECT COUNT(*) FROM tasks WHERE status='Ongoing'")
    pending = count("SELECT COUNT(*) FROM tasks WHERE status='Pending'")
    percent = round(done / total * 100) if total else 0
    upcoming = conn.execute(TASK_SELECT + "WHERE t.status != 'Completed' "
                            "ORDER BY t.deadline LIMIT 5").fetchall()
    recent = conn.execute(TASK_SELECT + "ORDER BY t.task_id DESC LIMIT 5").fetchall()
    sessions = conn.execute(
        "SELECT ss.*, s.subject_name FROM study_sessions ss JOIN subjects s "
        "ON ss.subject_id = s.subject_id WHERE ss.study_date >= ? "
        "ORDER BY ss.study_date, ss.start_time LIMIT 4", (date.today().isoformat(),)).fetchall()
    conn.close()
    return render_template("dashboard.html", title="Dashboard", subjects=subjects, total=total,
                           done=done, ongoing=ongoing, pending=pending, percent=percent,
                           upcoming=upcoming, recent=recent, sessions=sessions)


# ----------------------------------------------------------------- Subjects
@app.route("/subjects")
def subjects():
    conn = get_db()
    # GROUP BY summary: number of tasks and completed tasks per subject
    rows = conn.execute("""
        SELECT s.subject_id, s.subject_name, s.description,
               COUNT(t.task_id) AS total,
               COALESCE(SUM(CASE WHEN t.status='Completed' THEN 1 ELSE 0 END), 0) AS done
        FROM subjects s LEFT JOIN tasks t ON s.subject_id = t.subject_id
        GROUP BY s.subject_id ORDER BY s.subject_name""").fetchall()
    conn.close()
    return render_template("subjects.html", title="My Subjects", subject_list=rows)


def save_subject(subject_id=None):
    """Shared code for adding (subject_id=None) and editing a subject."""
    name = request.form.get("subject_name", "").strip()
    description = request.form.get("description", "").strip()
    if not name:
        flash("Subject name is required.", "danger")
        return redirect(url_for("subjects"))
    conn = get_db()
    dup = conn.execute("SELECT 1 FROM subjects WHERE LOWER(subject_name)=LOWER(?) "
                       "AND subject_id != ?", (name, subject_id or 0)).fetchone()
    if dup:
        flash("A subject with that name already exists.", "danger")
    elif subject_id is None:
        conn.execute("INSERT INTO subjects (subject_name, description) VALUES (?, ?)",
                     (name, description))
        flash("Subject added successfully!", "success")
    else:
        conn.execute("UPDATE subjects SET subject_name=?, description=? WHERE subject_id=?",
                     (name, description, subject_id))
        flash("Subject updated successfully!", "success")
    conn.commit()
    conn.close()
    return redirect(url_for("subjects"))


@app.route("/subjects/add", methods=["POST"])
def add_subject():
    return save_subject()


@app.route("/subjects/<int:subject_id>/edit", methods=["POST"])
def edit_subject(subject_id):
    return save_subject(subject_id)


@app.route("/subjects/<int:subject_id>/delete", methods=["POST"])
def delete_subject(subject_id):
    conn = get_db()
    tasks_n = conn.execute("SELECT COUNT(*) FROM tasks WHERE subject_id=?", (subject_id,)).fetchone()[0]
    sess_n = conn.execute("SELECT COUNT(*) FROM study_sessions WHERE subject_id=?", (subject_id,)).fetchone()[0]
    if tasks_n or sess_n:  # a subject that is still in use cannot be deleted
        flash(f"Cannot delete: this subject still has {tasks_n} task(s) and {sess_n} study session(s). "
              "Delete them first.", "warning")
    else:
        conn.execute("DELETE FROM subjects WHERE subject_id=?", (subject_id,))
        conn.commit()
        flash("Subject deleted.", "success")
    conn.close()
    return redirect(url_for("subjects"))


# -------------------------------------------------------------------- Tasks
@app.route("/tasks")
def tasks():
    f = {key: request.args.get(key, "").strip()
         for key in ("q", "status", "subject", "priority", "type", "sort")}
    # Only these fixed strings are ever placed in the SQL (safe)
    orders = {"deadline": "t.deadline ASC",
              "priority": "CASE t.priority WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END, t.deadline",
              "newest": "t.task_id DESC"}
    conditions, params = [], []
    if f["q"]:  # search in title, description and subject name
        conditions.append("(t.task_title LIKE ? OR t.task_description LIKE ? OR s.subject_name LIKE ?)")
        params += ["%" + f["q"] + "%"] * 3
    if f["status"] in STATUSES:
        conditions.append("t.status = ?"); params.append(f["status"])
    if f["subject"].isdigit():
        conditions.append("t.subject_id = ?"); params.append(f["subject"])
    if f["priority"] in PRIORITIES:
        conditions.append("t.priority = ?"); params.append(f["priority"])
    if f["type"] in TYPES:
        conditions.append("t.task_type = ?"); params.append(f["type"])
    where = "WHERE " + " AND ".join(conditions) + " " if conditions else ""
    conn = get_db()
    task_list = conn.execute(TASK_SELECT + where + "ORDER BY " +
                             orders.get(f["sort"], orders["deadline"]), params).fetchall()
    subject_list = conn.execute("SELECT * FROM subjects ORDER BY subject_name").fetchall()
    conn.close()
    return render_template("tasks.html", title="My Tasks", task_list=task_list,
                           subject_list=subject_list, f=f)


def save_task(task_id=None):
    """Shared code for adding (task_id=None) and editing a task."""
    form = request.form
    title = form.get("task_title", "").strip()
    desc = form.get("task_description", "").strip()
    subject_id = form.get("subject_id", "").strip()
    deadline = form.get("deadline", "").strip()
    priority = form.get("priority", "Medium")
    status = form.get("status", "Pending")
    task_type = form.get("task_type", "Assignment")

    error = None  # ---- validation
    if not title:
        error = "Task title is required."
    elif not subject_id.isdigit():
        error = "Please select a subject."
    elif not deadline:
        error = "Deadline is required."
    elif not valid_date(deadline):
        error = "Deadline must be a valid date."
    elif priority not in PRIORITIES or status not in STATUSES or task_type not in TYPES:
        error = "Invalid priority, status or task type."

    conn = get_db()
    if not error and not conn.execute("SELECT 1 FROM subjects WHERE subject_id=?",
                                      (subject_id,)).fetchone():
        error = "The selected subject does not exist."
    if error:
        flash(error, "danger")
    elif task_id is None:
        conn.execute("INSERT INTO tasks (subject_id, task_title, task_description, task_type, "
                     "deadline, priority, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                     (subject_id, title, desc, task_type, deadline, priority, status,
                      datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        flash("Task added successfully!", "success")
    else:
        conn.execute("UPDATE tasks SET subject_id=?, task_title=?, task_description=?, task_type=?, "
                     "deadline=?, priority=?, status=? WHERE task_id=?",
                     (subject_id, title, desc, task_type, deadline, priority, status, task_id))
        flash("Task updated successfully!", "success")
    conn.commit()
    conn.close()
    return back("tasks")


@app.route("/tasks/add", methods=["POST"])
def add_task():
    return save_task()


@app.route("/tasks/<int:task_id>/edit", methods=["POST"])
def edit_task(task_id):
    return save_task(task_id)


@app.route("/tasks/<int:task_id>/status", methods=["POST"])
def set_status(task_id):
    """Change a task to Pending, Ongoing or Completed."""
    status = request.form.get("status")
    if status in STATUSES:
        conn = get_db()
        conn.execute("UPDATE tasks SET status=? WHERE task_id=?", (status, task_id))
        conn.commit()
        conn.close()
        flash("Task marked as " + status + ".", "success")
    else:
        flash("Invalid status.", "danger")
    return back("tasks")


@app.route("/tasks/<int:task_id>/delete", methods=["POST"])
def delete_task(task_id):
    conn = get_db()
    conn.execute("DELETE FROM tasks WHERE task_id=?", (task_id,))
    conn.commit()
    conn.close()
    flash("Task deleted.", "success")
    return back("tasks")


@app.route("/completed")
def completed():
    conn = get_db()
    task_list = conn.execute(TASK_SELECT + "WHERE t.status='Completed' "
                             "ORDER BY t.deadline DESC").fetchall()
    conn.close()
    return render_template("completed.html", title="Completed Tasks", task_list=task_list)


# --------------------------------------------------------- Study schedule
@app.route("/schedule")
def schedule():
    conn = get_db()
    rows = conn.execute("SELECT ss.*, s.subject_name FROM study_sessions ss JOIN subjects s "
                        "ON ss.subject_id = s.subject_id ORDER BY ss.study_date, ss.start_time").fetchall()
    subject_list = conn.execute("SELECT * FROM subjects ORDER BY subject_name").fetchall()
    conn.close()
    today = date.today().isoformat()
    upcoming = [r for r in rows if r["study_date"] >= today]
    past = [r for r in rows if r["study_date"] < today][::-1]  # newest first
    return render_template("schedule.html", title="Study Schedule", upcoming=upcoming,
                           past=past, subject_list=subject_list)


def save_session(session_id=None):
    """Shared code for adding/editing a study session."""
    form = request.form
    subject_id = form.get("subject_id", "").strip()
    topic = form.get("topic", "").strip()
    study_date = form.get("study_date", "").strip()
    start, end = form.get("start_time", "").strip(), form.get("end_time", "").strip()
    notes = form.get("notes", "").strip()

    error = None
    if not topic:
        error = "Topic is required."
    elif not subject_id.isdigit():
        error = "Please select a subject."
    elif not valid_date(study_date):
        error = "Please enter a valid study date."
    elif not (valid_time(start) and valid_time(end)):
        error = "Please enter a valid start and end time."
    elif end <= start:
        error = "End time must be after the start time."

    conn = get_db()
    if not error and not conn.execute("SELECT 1 FROM subjects WHERE subject_id=?",
                                      (subject_id,)).fetchone():
        error = "The selected subject does not exist."
    if error:
        flash(error, "danger")
    elif session_id is None:
        conn.execute("INSERT INTO study_sessions (subject_id, topic, study_date, start_time, "
                     "end_time, notes) VALUES (?, ?, ?, ?, ?, ?)",
                     (subject_id, topic, study_date, start, end, notes))
        flash("Study session added!", "success")
    else:
        conn.execute("UPDATE study_sessions SET subject_id=?, topic=?, study_date=?, start_time=?, "
                     "end_time=?, notes=? WHERE session_id=?",
                     (subject_id, topic, study_date, start, end, notes, session_id))
        flash("Study session updated!", "success")
    conn.commit()
    conn.close()
    return redirect(url_for("schedule"))


@app.route("/schedule/add", methods=["POST"])
def add_session():
    return save_session()


@app.route("/schedule/<int:session_id>/edit", methods=["POST"])
def edit_session(session_id):
    return save_session(session_id)


@app.route("/schedule/<int:session_id>/delete", methods=["POST"])
def delete_session(session_id):
    conn = get_db()
    conn.execute("DELETE FROM study_sessions WHERE session_id=?", (session_id,))
    conn.commit()
    conn.close()
    flash("Study session deleted.", "success")
    return redirect(url_for("schedule"))


if __name__ == "__main__":
    app.run(debug=True)
