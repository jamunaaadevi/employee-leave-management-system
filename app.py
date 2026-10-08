# app.py – Employee Leave Management System
import os, sqlite3, json, time
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, jsonify

app = Flask(__name__)
app.secret_key = "change-me-in-production"

# ── Database ──────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(os.environ.get("DB_PATH", "leave.db"))
    conn.row_factory = sqlite3.Row  # access columns by name like a dict
    return conn

def init_db():
    conn = get_db()
    conn.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS leaves (id INTEGER PRIMARY KEY, user_id INTEGER, type TEXT, start_date TEXT, end_date TEXT, reason TEXT, status TEXT DEFAULT 'pending', days INTEGER)")
    for u in [("asha","asha123","employee"), ("vikram","vikram123","employee"),
              ("manager","manager123","manager")]:
        conn.execute("INSERT OR IGNORE INTO users (username,password,role) VALUES (?,?,?)", u)
    conn.commit()
    conn.close()

# ── Logging: one JSON line per request so Cloud Logging can parse it ──────────

@app.before_request
def _start():
    request._t0 = time.time()

@app.after_request
def _log(resp):
    ms = int((time.time() - request._t0) * 1000)
    print(json.dumps({"severity": "INFO", "path": request.path,
                      "status": resp.status_code, "latency_ms": ms}))
    return resp

# ── Health check ──────────────────────────────────────────────────────────────

@app.route("/health")
def health():
    # SIMULATE_FAILURE=true makes the DB appear unavailable (used for demo)
    if os.environ.get("SIMULATE_FAILURE", "false").lower() == "true":
        return jsonify({"status": "unhealthy"}), 503
    try:
        conn = get_db()
        conn.execute("SELECT 1")
        conn.close()
        return jsonify({"status": "healthy"}), 200
    except Exception:
        return jsonify({"status": "unhealthy"}), 503

# ── Auth ──────────────────────────────────────────────────────────────────────

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = get_db().execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (request.form["username"], request.form["password"])).fetchone()
        if user:
            session.update(user_id=user["id"], username=user["username"], role=user["role"])
            return redirect(url_for("employee" if user["role"] == "employee" else "manager_view"))
        return render_template("login.html", error="Invalid credentials")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ── Employee: dashboard + leave application ──────────────────────────────────
def _balance_info(uid):
    conn = get_db()
    leaves = conn.execute(
        "SELECT * FROM leaves WHERE user_id=? ORDER BY id DESC", (uid,)).fetchall()
    used = conn.execute(
        "SELECT COALESCE(SUM(days),0) FROM leaves WHERE user_id=? AND status='approved'",
        (uid,)).fetchone()[0]
    conn.close()
    return leaves, 20 - used  # 20 days annual allowance

@app.route("/employee")
def employee():
    if session.get("role") != "employee":
        return redirect(url_for("login"))
    leaves, balance = _balance_info(session["user_id"])
    return render_template("employee.html", leaves=leaves, balance=balance,
                           username=session["username"])

@app.route("/apply", methods=["POST"])
def apply():
    if session.get("role") != "employee":
        return redirect(url_for("login"))
    start  = request.form["start_date"]
    end    = request.form["end_date"]
    reason = request.form["reason"].strip()
    error, days = None, 0
    if not reason:
        error = "Reason is required."
    elif end < start:
        error = "End date cannot be before start date."
    else:
        days = (datetime.strptime(end, "%Y-%m-%d") - datetime.strptime(start, "%Y-%m-%d")).days + 1
        _, balance = _balance_info(session["user_id"])
        if days > balance:
            error = f"Only {balance} days remaining in your balance."
    if error:
        leaves, balance = _balance_info(session["user_id"])
        return render_template("employee.html", leaves=leaves, balance=balance,
                               username=session["username"], error=error)
    conn = get_db()
    conn.execute(
        "INSERT INTO leaves (user_id,type,start_date,end_date,reason,days) VALUES (?,?,?,?,?,?)",
        (session["user_id"], request.form["type"], start, end, reason, days))
    conn.commit()
    conn.close()
    return redirect(url_for("employee"))

# ── Manager: view all requests + approve / reject ─────────────────────────────

@app.route("/manager")
def manager_view():
    if session.get("role") != "manager":
        return redirect(url_for("login"))
    conn = get_db()
    leaves = conn.execute(
        "SELECT l.*, u.username FROM leaves l JOIN users u ON l.user_id=u.id ORDER BY l.id DESC"
    ).fetchall()
    conn.close()
    return render_template("manager.html", leaves=leaves, username=session["username"])

@app.route("/action/<int:lid>/<act>")
def action(lid, act):
    if session.get("role") != "manager":
        return redirect(url_for("login"))
    if act in ("approved", "rejected"):
        conn = get_db()
        conn.execute("UPDATE leaves SET status=? WHERE id=?", (act, lid))
        conn.commit()
        conn.close()
    return redirect(url_for("manager_view"))

# ── Startup ───────────────────────────────────────────────────────────────────

init_db()  # create tables + seed users; runs when gunicorn imports this file

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
