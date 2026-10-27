from __future__ import annotations

import os
import shlex
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, abort, render_template, request, send_from_directory, url_for
from werkzeug.utils import secure_filename

from database import get_student, init_db, list_students

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
OUTPUT_DIR = INSTANCE_DIR / "generated"
WORK_DIR = INSTANCE_DIR / "work"
PDF_ENGINE = BASE_DIR / "pdf_engine.py"

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "dev-only-change-me")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024


def prepare_directories() -> None:
    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)


def _download_name(raw_name: str, job_id: str) -> str:
    """Produce a predictable filename for the download route, not the shell.

    Intentionally, this safe name is NOT used to build the vulnerable command.
    """
    # For the intended lab payload, the filename before the first quote is the
    # normal PDF path; the remaining text is interpreted by the shell below.
    prefix = raw_name.split('"', 1)[0]
    name = secure_filename(prefix)
    if not name:
        name = f"resume_{job_id}"
    if not name.lower().endswith(".pdf"):
        name = f"{name}.pdf"
    return name[:120]


def _build_vulnerable_command(html_path: Path, job_dir: Path, raw_filename: str) -> str:
    """Build the intentionally unsafe shell command used by this CTF.

    Do not copy this pattern into a real application. raw_filename is embedded
    into a double-quoted shell argument without escaping it, so a quote can end
    that argument and make shell syntax executable.
    """
    # Normalize the filename prefix so ordinary names match the download path,
    # but preserve everything from the first quote onward. That suffix is what
    # makes the demo exploitable when the shell parses the command string.
    prefix = raw_filename.split('"', 1)[0]
    filename = secure_filename(prefix) or "resume.pdf"
    if not filename.lower().endswith(".pdf"):
        filename = f"{filename}.pdf"
    shell_suffix = raw_filename[len(prefix):]
    output_argument = f"{job_dir.as_posix()}/{filename}{shell_suffix}"
    return (
        f"{shlex.quote(sys.executable)} {shlex.quote(str(PDF_ENGINE))} "
        f"{shlex.quote(str(html_path))} \"{output_argument}\""
    )


@app.get("/")
def index():
    return render_template("index.html", students=list_students())


@app.post("/generate")
def generate():
    try:
        student_id = int(request.form.get("student_id", ""))
    except ValueError:
        abort(400, "Choose a valid student profile.")

    student = get_student(student_id)
    if student is None:
        abort(400, "The selected student profile does not exist.")

    company_name = request.form.get("company_name", "").strip()
    raw_filename = request.form.get("output_filename", "").strip()
    if not company_name or not raw_filename:
        abort(400, "Company name and output filename are required.")
    if len(company_name) > 80 or len(raw_filename) > 120:
        abort(400, "Company name or filename is too long.")

    job_id = uuid.uuid4().hex[:10]
    job_dir = OUTPUT_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    html_path = WORK_DIR / f"{job_id}.html"
    safe_filename = _download_name(raw_filename, job_id)
    expected_pdf = job_dir / safe_filename

    rendered_resume = render_template(
        "resume.html", student=student, company_name=company_name
    )
    html_path.write_text(rendered_resume, encoding="utf-8")

    # Intentional CTF vulnerability: the raw filename is concatenated into a
    # shell command. The captured process output is shown on the result page.
    command = _build_vulnerable_command(html_path, job_dir, raw_filename)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    stdout = ""
    stderr = ""
    return_code = -1
    timed_out = False

    try:
        completed = subprocess.run(
            command,
            shell=True,  # INTENTIONALLY VULNERABLE FOR THIS LOCAL CTF CHALLENGE
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8,
            check=False,
        )
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        return_code = completed.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout = exc.stdout.decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        stderr += "\nPROCESS_TIMEOUT: command exceeded the 8-second lab limit."
    except OSError as exc:
        stderr = f"PROCESS_LAUNCH_ERROR: {type(exc).__name__}: {exc}"

    # The first output path is the safe prefix before the injected quote.
    # Report the downloadable PDF only if that file was created.
    pdf_exists = expected_pdf.is_file()
    success = (return_code == 0) and pdf_exists and not timed_out

    log_text = "\n".join(
        [
            f"[{timestamp}] INFO  job_id={job_id}",
            f"[{timestamp}] INFO  student_id={student_id} roll_no={student['roll_no']}",
            f"[{timestamp}] INFO  target_company={company_name!r}",
            f"[{timestamp}] INFO  requested_filename={raw_filename!r}",
            f"[{timestamp}] INFO  shell_command={command}",
            f"[{timestamp}] INFO  return_code={return_code} timed_out={timed_out}",
            f"[{timestamp}] INFO  pdf_created={pdf_exists} expected_path={expected_pdf}",
            "",
            "========== STDOUT (includes injected command output) ==========",
            stdout.rstrip() or "(no stdout)",
            "",
            "========== STDERR (converter / shell errors) ==========",
            stderr.rstrip() or "(no stderr)",
        ]
    )
    (job_dir / "run.log").write_text(log_text + "\n", encoding="utf-8")
    try:
        html_path.unlink(missing_ok=True)
    except OSError:
        pass

    return render_template(
        "result.html",
        job_id=job_id,
        student=student,
        company_name=company_name,
        requested_filename=raw_filename,
        safe_filename=safe_filename,
        success=success,
        pdf_exists=pdf_exists,
        timed_out=timed_out,
        return_code=return_code,
        stdout=stdout,
        stderr=stderr,
        log_text=log_text,
        download_url=url_for("download_pdf", job_id=job_id, filename=safe_filename) if pdf_exists else None,
    )


@app.get("/download/<job_id>/<path:filename>")
def download_pdf(job_id: str, filename: str):
    # Restrict identifiers and serve only a generated PDF in that job's folder.
    if len(job_id) != 10 or not all(char in "0123456789abcdef" for char in job_id):
        abort(404)
    safe_name = secure_filename(filename)
    if safe_name != filename or not safe_name.lower().endswith(".pdf"):
        abort(404)
    job_dir = OUTPUT_DIR / job_id
    target = job_dir / safe_name
    if not target.is_file():
        abort(404)
    return send_from_directory(job_dir, safe_name, as_attachment=True, download_name=safe_name)


@app.get("/logs/<job_id>")
def view_logs(job_id: str):
    if len(job_id) != 10 or not all(char in "0123456789abcdef" for char in job_id):
        abort(404)
    log_path = OUTPUT_DIR / job_id / "run.log"
    if not log_path.is_file():
        abort(404)
    return render_template("logs.html", job_id=job_id, log_text=log_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    prepare_directories()
    init_db()
    # Local-only by default. In Docker, HOST is explicitly set to 0.0.0.0
    # so the container's port can be published on the host.
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "5000")), debug=False)
