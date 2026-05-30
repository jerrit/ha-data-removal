"""
app.py — Flask web server + APScheduler (Home Assistant addon edition)

Serves the web dashboard via HA Ingress at port 8099.
Personal info and the secret key are passed in via environment variables
set by /usr/bin/run.sh, which reads /data/options.json at startup.
"""

import asyncio
import json
import os
import threading
from collections import defaultdict
from datetime import datetime

from flask import (
    Flask, jsonify, redirect, render_template, request,
    url_for, flash, session,
)
from apscheduler.schedulers.background import BackgroundScheduler

import db
from opt_out_db import ALL_SITES as OPT_OUT_SITES

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me")

WEB_PASSWORD        = os.environ.get("WEB_PASSWORD", "")
SCAN_INTERVAL_DAYS  = int(os.environ.get("SCAN_INTERVAL", "0") or "0")


# ── HA Ingress middleware ─────────────────────────────────────────────────── #
# HA's ingress proxy forwards requests to the addon at port 8099 and adds the
# X-Ingress-Path header with the URL prefix (e.g. /api/hassio_ingress/TOKEN).
# Without this middleware, url_for() generates /dashboard but the browser
# would need /api/hassio_ingress/TOKEN/dashboard.

class _IngressMiddleware:
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        ingress_path = environ.get("HTTP_X_INGRESS_PATH", "").rstrip("/")
        if ingress_path:
            environ["SCRIPT_NAME"] = ingress_path
            path_info = environ.get("PATH_INFO", "")
            if path_info.startswith(ingress_path):
                environ["PATH_INFO"] = path_info[len(ingress_path):] or "/"
        return self.wsgi_app(environ, start_response)


app.wsgi_app = _IngressMiddleware(app.wsgi_app)


# ── Shared state: track whether a scan is currently running ─────────────── #
_scan_state = {
    "running": False,
    "started_at": None,
    "last_completed": None,
    "last_results": [],
    "progress": {},
}
_state_lock = threading.Lock()


# ── Active user helpers ──────────────────────────────────────────────────── #

def get_current_user() -> dict | None:
    user_id = session.get("current_user_id")
    if user_id:
        user = db.get_user(user_id)
        if user:
            return user
    return db.get_default_user()


@app.context_processor
def inject_user_context():
    return {
        "current_user": get_current_user(),
        "all_users": db.get_all_users(),
        "web_password_enabled": bool(WEB_PASSWORD),
    }


# ── Password gate ────────────────────────────────────────────────────────── #

@app.before_request
def require_password():
    if not WEB_PASSWORD:
        return
    if request.endpoint in ("login", "logout", "static"):
        return
    if session.get("web_authenticated"):
        return
    next_url = request.full_path if request.path != "/" else ""
    return redirect(url_for("login", next=next_url or ""))


@app.route("/login", methods=["GET", "POST"])
def login():
    if not WEB_PASSWORD:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        if request.form.get("password") == WEB_PASSWORD:
            session["web_authenticated"] = True
            next_url = request.form.get("next") or url_for("dashboard")
            return redirect(next_url)
        flash("Incorrect password.", "danger")
    return render_template("login.html", next=request.args.get("next", ""))


@app.route("/logout", methods=["POST"])
def logout():
    session.pop("web_authenticated", None)
    return redirect(url_for("login"))


# ── Startup ──────────────────────────────────────────────────────────────── #

def startup():
    db.init_db()
    db.seed_sites(OPT_OUT_SITES)
    db.seed_default_user()
    print("[App] Database ready.")


# ── Background helpers ───────────────────────────────────────────────────── #

def _run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _scan_thread(site_ids=None, user=None):
    from bots.scanner import run_all_scans
    with _state_lock:
        _scan_state["running"]    = True
        _scan_state["started_at"] = datetime.utcnow().isoformat()
        _scan_state["progress"]   = {}

    def _on_progress(current, total, site_name):
        with _state_lock:
            _scan_state["progress"] = {
                "current":      current,
                "total":        total,
                "current_site": site_name,
            }

    try:
        results = _run_async(run_all_scans(site_ids, user=user, progress_callback=_on_progress))
        with _state_lock:
            _scan_state["last_results"]   = results
            _scan_state["last_completed"] = datetime.utcnow().isoformat()
            _scan_state["progress"]       = {}
        user_id = user["id"] if user else None
        db.record_snapshot(user_id)
    except Exception as e:
        print(f"[App] Scan thread error: {e}")
    finally:
        with _state_lock:
            _scan_state["running"] = False
            _scan_state["progress"] = {}


def _request_thread(scan_id: int, user=None):
    from bots.requester import submit_removal_request
    try:
        _run_async(submit_removal_request(scan_id, user=user))
    except Exception as e:
        print(f"[App] Request thread error: {e}")


# ── APScheduler ──────────────────────────────────────────────────────────── #

def scheduled_rescan():
    with _state_lock:
        if _scan_state["running"]:
            print("[Scheduler] Skipping rescan — a scan is already running.")
            return

    due = db.get_scans_due_for_rescan()
    if not due:
        return

    print(f"[Scheduler] {len(due)} site(s) due for rescan...")

    by_user = defaultdict(list)
    for scan in due:
        db.update_scan_status(scan["id"], "rescanning")
        by_user[scan.get("user_id")].append(scan["site_id"])

    for user_id, site_ids in by_user.items():
        user = db.get_user(user_id) if user_id else None
        thread = threading.Thread(
            target=_scan_thread,
            kwargs={"site_ids": list(set(site_ids)), "user": user},
            daemon=True,
        )
        thread.start()


def scheduled_prune():
    count = db.prune_old_scans(keep_per_site=10)
    if count:
        print(f"[Scheduler] Pruned {count} old scan record(s).")


def scheduled_full_scan():
    with _state_lock:
        if _scan_state["running"]:
            print("[Scheduler] Skipping scheduled scan — already running.")
            return
    users = db.get_all_users()
    if not users:
        return
    print(f"[Scheduler] Running scheduled full scan for {len(users)} user(s)...")

    def _scan_all_users():
        for user in users:
            _scan_thread(user=user)

    threading.Thread(target=_scan_all_users, daemon=True).start()


scheduler = BackgroundScheduler()
scheduler.add_job(scheduled_rescan, "interval", hours=1,  id="rescan_check")
scheduler.add_job(scheduled_prune,  "interval", days=30,  id="prune_old_scans")
if SCAN_INTERVAL_DAYS > 0:
    scheduler.add_job(
        scheduled_full_scan, "interval", days=SCAN_INTERVAL_DAYS, id="scheduled_full_scan"
    )
    print(f"[App] Scheduled full scan every {SCAN_INTERVAL_DAYS} day(s).")


# ── Flask routes ─────────────────────────────────────────────────────────── #

@app.route("/")
def dashboard():
    current = get_current_user()
    user_id = current["id"] if current else None

    stats = db.get_dashboard_stats(user_id=user_id)
    scans = db.get_all_scans(user_id=user_id)
    sites = db.get_all_sites()

    for scan in scans:
        if scan.get("data_fields_json"):
            try:
                scan["data_fields"] = json.loads(scan["data_fields_json"])
            except (json.JSONDecodeError, TypeError):
                scan["data_fields"] = {}
        else:
            scan["data_fields"] = {}

        if scan.get("next_rescan_date"):
            try:
                rescan_dt = datetime.fromisoformat(scan["next_rescan_date"])
                delta     = rescan_dt - datetime.utcnow()
                scan["days_until_rescan"] = max(0, delta.days)
            except (ValueError, TypeError):
                scan["days_until_rescan"] = None
        else:
            scan["days_until_rescan"] = None

    with _state_lock:
        scan_running = _scan_state["running"]
        last_scan    = _scan_state.get("last_completed")

    return render_template(
        "dashboard.html",
        stats=stats,
        scans=scans,
        sites=sites,
        scan_running=scan_running,
        last_scan=last_scan,
    )


@app.route("/scan", methods=["POST"])
def trigger_scan():
    with _state_lock:
        if _scan_state["running"]:
            flash("A scan is already running. Please wait for it to finish.", "warning")
            return redirect(url_for("dashboard"))

    user = get_current_user()
    threading.Thread(target=_scan_thread, kwargs={"user": user}, daemon=True).start()
    flash("Scan started! Refresh the page in a few minutes to see results.", "info")
    return redirect(url_for("dashboard"))


@app.route("/scan/<int:site_id>", methods=["POST"])
def trigger_site_scan(site_id):
    site = db.get_site(site_id)
    if not site:
        flash(f"Site ID {site_id} not found.", "danger")
        return redirect(url_for("dashboard"))

    with _state_lock:
        if _scan_state["running"]:
            flash("A scan is already running. Please wait.", "warning")
            return redirect(url_for("site_detail", site_id=site_id))

    user = get_current_user()
    threading.Thread(
        target=_scan_thread,
        kwargs={"site_ids": [site_id], "user": user},
        daemon=True,
    ).start()
    flash(f"Scanning {site['name']}...", "info")
    return redirect(url_for("site_detail", site_id=site_id))


@app.route("/request/<int:scan_id>", methods=["POST"])
def trigger_request(scan_id):
    scan = db.get_scan(scan_id)
    if not scan:
        flash(f"Scan #{scan_id} not found.", "danger")
        return redirect(url_for("dashboard"))

    if scan["status"] not in ("found", "rescanning"):
        flash(
            f"Can only request removal for scans in 'found' or 'rescanning' status "
            f"(this one is '{scan['status']}').",
            "warning",
        )
        return redirect(url_for("site_detail", site_id=scan["site_id"]))

    user = get_current_user()
    threading.Thread(
        target=_request_thread,
        kwargs={"scan_id": scan_id, "user": user},
        daemon=True,
    ).start()
    flash(
        f"Opt-out request submitted for {scan['site_name']}. "
        "Check the site detail for next steps.",
        "success",
    )
    return redirect(url_for("site_detail", site_id=scan["site_id"]))


@app.route("/site/<int:site_id>")
def site_detail(site_id):
    site = db.get_site(site_id)
    if not site:
        flash(f"Site ID {site_id} not found.", "danger")
        return redirect(url_for("dashboard"))

    current = get_current_user()
    user_id = current["id"] if current else None
    scans   = db.get_scans_for_site(site_id, user_id=user_id)

    for scan in scans:
        if scan.get("data_fields_json"):
            try:
                scan["data_fields"] = json.loads(scan["data_fields_json"])
            except (json.JSONDecodeError, TypeError):
                scan["data_fields"] = {}
        else:
            scan["data_fields"] = {}

        if scan.get("next_rescan_date"):
            try:
                rescan_dt = datetime.fromisoformat(scan["next_rescan_date"])
                delta     = rescan_dt - datetime.utcnow()
                scan["days_until_rescan"] = max(0, delta.days)
            except (ValueError, TypeError):
                scan["days_until_rescan"] = None
        else:
            scan["days_until_rescan"] = None

    latest_request = None
    for scan in scans:
        reqs = db.get_requests_for_scan(scan["id"])
        if reqs:
            latest_request = reqs[0]
            latest_request["scan_id"] = scan["id"]
            break

    first_actionable = next(
        (s for s in scans if s["status"] in ("found", "rescanning")), None
    )

    return render_template(
        "site_detail.html",
        site=site,
        scans=scans,
        latest_request=latest_request,
        first_actionable=first_actionable,
    )


@app.route("/site/add", methods=["GET", "POST"])
def add_site():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        url  = request.form.get("url", "").strip()

        if not name or not url:
            flash("Site name and URL are required.", "danger")
            return redirect(url_for("add_site"))

        existing = db.get_site_by_name(name)
        if existing:
            flash(f"A site named '{name}' already exists.", "warning")
            return redirect(url_for("site_detail", site_id=existing["id"]))

        new_site = {
            "name":                 name,
            "url":                  url,
            "search_url_template":  request.form.get("search_url_template", "").strip(),
            "opt_out_url":          request.form.get("opt_out_url", "").strip(),
            "opt_out_method":       request.form.get("opt_out_method", "form"),
            "opt_out_instructions": request.form.get("opt_out_instructions", "").strip(),
            "estimated_days":       int(request.form.get("estimated_days") or 30),
        }
        db.seed_sites([new_site])
        site = db.get_site_by_name(name)
        flash(f"Site '{name}' added. Run a scan to check it.", "success")
        return redirect(url_for("site_detail", site_id=site["id"]))

    return render_template("add_site.html")


# ── User management ──────────────────────────────────────────────────────── #

@app.route("/users")
def users_list():
    users   = db.get_all_users()
    counts  = db.get_user_scan_counts()
    current = get_current_user()
    return render_template("users.html", users=users, counts=counts, current=current)


@app.route("/users/add", methods=["GET", "POST"])
def add_user():
    if request.method == "POST":
        display_name = request.form.get("display_name", "").strip()
        first_name   = request.form.get("first_name", "").strip()
        last_name    = request.form.get("last_name", "").strip()

        if not display_name or not first_name or not last_name:
            flash("Display name, first name, and last name are required.", "danger")
            return redirect(url_for("add_user"))

        db.create_user(
            display_name = display_name,
            first_name   = first_name,
            last_name    = last_name,
            city         = request.form.get("city", "").strip(),
            state        = request.form.get("state", "").strip(),
            state_full   = request.form.get("state_full", "").strip(),
            email        = request.form.get("email", "").strip(),
            phone        = request.form.get("phone", "").strip(),
            notes        = request.form.get("notes", "").strip(),
        )
        flash(f"User '{display_name}' created.", "success")
        return redirect(url_for("users_list"))

    return render_template("add_edit_user.html", editing=False, user=None)


@app.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
def edit_user(user_id):
    user = db.get_user(user_id)
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for("users_list"))

    if request.method == "POST":
        display_name = request.form.get("display_name", "").strip()
        first_name   = request.form.get("first_name", "").strip()
        last_name    = request.form.get("last_name", "").strip()

        if not display_name or not first_name or not last_name:
            flash("Display name, first name, and last name are required.", "danger")
            return redirect(url_for("edit_user", user_id=user_id))

        db.update_user(
            user_id,
            display_name = display_name,
            first_name   = first_name,
            last_name    = last_name,
            city         = request.form.get("city", "").strip(),
            state        = request.form.get("state", "").strip(),
            state_full   = request.form.get("state_full", "").strip(),
            email        = request.form.get("email", "").strip(),
            phone        = request.form.get("phone", "").strip(),
            notes        = request.form.get("notes", "").strip(),
        )
        flash(f"User '{display_name}' updated.", "success")
        return redirect(url_for("users_list"))

    return render_template("add_edit_user.html", editing=True, user=user)


@app.route("/users/<int:user_id>/delete", methods=["POST"])
def delete_user_route(user_id):
    all_users = db.get_all_users()
    if len(all_users) <= 1:
        flash("Cannot delete the only user profile.", "danger")
        return redirect(url_for("users_list"))

    user = db.get_user(user_id)
    if user:
        db.delete_user(user_id)
        if session.get("current_user_id") == user_id:
            session.pop("current_user_id", None)
        flash(f"Deleted user '{user['display_name']}' and all their scan history.", "success")
    else:
        flash("User not found.", "danger")
    return redirect(url_for("users_list"))


@app.route("/users/<int:user_id>/select", methods=["POST"])
def select_user(user_id):
    user = db.get_user(user_id)
    if user:
        session["current_user_id"] = user_id
        flash(f"Switched to {user['display_name']}.", "success")
    else:
        flash("User not found.", "danger")
    return redirect(request.referrer or url_for("dashboard"))


# ── Site management ──────────────────────────────────────────────────────── #

@app.route("/site/<int:site_id>/edit", methods=["GET", "POST"])
def edit_site(site_id):
    site = db.get_site(site_id)
    if not site:
        flash("Site not found.", "danger")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        db.update_site(
            site_id,
            url                  = request.form.get("url", "").strip(),
            search_url_template  = request.form.get("search_url_template", "").strip(),
            opt_out_url          = request.form.get("opt_out_url", "").strip(),
            opt_out_method       = request.form.get("opt_out_method", "form"),
            opt_out_instructions = request.form.get("opt_out_instructions", "").strip(),
            estimated_days       = int(request.form.get("estimated_days") or 30),
        )
        flash(f"'{site['name']}' updated.", "success")
        return redirect(url_for("site_detail", site_id=site_id))

    return render_template("edit_site.html", site=site)


@app.route("/site/<int:site_id>/toggle", methods=["POST"])
def toggle_site(site_id):
    site = db.get_site(site_id)
    if not site:
        flash("Site not found.", "danger")
        return redirect(url_for("dashboard"))
    new_val = db.toggle_site_enabled(site_id)
    state = "enabled" if new_val else "disabled"
    flash(f"'{site['name']}' is now {state}.", "success" if new_val else "warning")
    return redirect(url_for("site_detail", site_id=site_id))


@app.route("/site/<int:site_id>/test_url")
def test_site_url(site_id):
    site = db.get_site(site_id)
    if not site or not site.get("search_url_template"):
        flash("No search URL template configured for this site.", "warning")
        return redirect(url_for("site_detail", site_id=site_id))

    current    = get_current_user()
    if not current:
        flash("Add a user profile first before testing a search URL.", "warning")
        return redirect(url_for("site_detail", site_id=site_id))
    first      = current.get("first_name", "")
    last       = current.get("last_name",  "")
    city       = current.get("city",       "")
    state      = current.get("state",      "")
    state_full = current.get("state_full", "")

    subs = {
        "first":      first,
        "last":       last,
        "city":       city.replace(" ", "+"),
        "state":      state,
        "state_full": state_full,
        "first_last": f"{first}-{last}".lower().replace(" ", "-"),
        "name":       f"{first}+{last}",
    }
    try:
        resolved = site["search_url_template"].format_map(subs)
        return redirect(resolved)
    except (KeyError, ValueError) as e:
        flash(f"Unknown placeholder in search URL template: {e}", "danger")
        return redirect(url_for("site_detail", site_id=site_id))


# ── API endpoints ─────────────────────────────────────────────────────────── #

@app.route("/api/scan_status")
def api_scan_status():
    with _state_lock:
        return jsonify({
            "running":        _scan_state["running"],
            "started_at":     _scan_state.get("started_at"),
            "last_completed": _scan_state.get("last_completed"),
            "progress":       _scan_state.get("progress", {}),
        })


@app.route("/api/stats")
def api_stats():
    current = get_current_user()
    user_id = current["id"] if current else None
    return jsonify(db.get_dashboard_stats(user_id=user_id))


@app.route("/mark_removed/<int:scan_id>", methods=["POST"])
def mark_removed(scan_id):
    scan = db.get_scan(scan_id)
    if scan:
        db.update_scan_status(scan_id, "removed")
        flash(f"Marked {scan['site_name']} as removed.", "success")
        return redirect(url_for("site_detail", site_id=scan["site_id"]))
    flash("Scan not found.", "danger")
    return redirect(url_for("dashboard"))


@app.route("/mark_awaiting_verification/<int:scan_id>", methods=["POST"])
def mark_awaiting_verification(scan_id):
    scan = db.get_scan(scan_id)
    if scan:
        db.update_scan_status(scan_id, "awaiting_verification")
        flash(f"Marked {scan['site_name']} as awaiting email verification.", "info")
        return redirect(url_for("site_detail", site_id=scan["site_id"]))
    flash("Scan not found.", "danger")
    return redirect(url_for("dashboard"))


@app.route("/api/scan_history")
def api_scan_history():
    current = get_current_user()
    user_id = current["id"] if current else None
    rows = db.get_scan_history(user_id=user_id, days=30)
    return jsonify({
        "labels":  [r["snapshot_date"] for r in rows],
        "found":   [r["found"]   for r in rows],
        "pending": [r["pending"] for r in rows],
        "removed": [r["removed"] for r in rows],
    })


@app.route("/export/csv")
def export_csv():
    import csv
    import io as _io
    current = get_current_user()
    user_id = current["id"] if current else None
    scans   = db.get_all_scans(user_id=user_id)

    buf = _io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Site", "Status", "Data Found", "Scan Date",
                     "Request Date", "Next Rescan", "Profile URL"])
    for s in scans:
        writer.writerow([
            s.get("site_name", ""),
            s.get("status", ""),
            "Yes" if s.get("profile_found") else "No",
            (s.get("scan_date") or "")[:10],
            (s.get("request_date") or "")[:10],
            (s.get("next_rescan_date") or "")[:10],
            s.get("profile_url") or "",
        ])

    from flask import Response
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=data-removal-export.csv"},
    )


# ── Main ─────────────────────────────────────────────────────────────────── #

if __name__ == "__main__":
    startup()
    scheduler.start()
    print("[App] Scheduler started.")
    port = int(os.environ.get("PORT", 8099))
    print(f"[App] Listening on port {port}")
    try:
        app.run(debug=False, use_reloader=False, host="0.0.0.0", port=port)
    finally:
        scheduler.shutdown()
