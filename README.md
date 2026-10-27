# ResumeForge — Command Injection CTF

A small Flask-based placement portal for a **local, intentionally vulnerable CTF lab**. It uses SQLite demo records, renders a polished resume template to HTML, and invokes a ReportLab-powered PDF renderer. The output filename is deliberately inserted unsafely into a shell command so learners can observe a command-injection flaw.

> **Safety:** Do not run this vulnerable app on a public host or a network containing sensitive systems. The filename field intentionally enables command execution as the app's OS user. Use a disposable VM/container and synthetic data only.

## Features

- Student profiles, skills, and projects stored in SQLite (`instance/resumeforge.db`)
- Resume HTML rendered with Jinja templates
- A styled, one-page A4 PDF renderer (`pdf_engine.py`) with a branded header, contact/skills sidebar, profile and project sections, and footer; `wkhtmltopdf` is not required
- ReportLab is used to draw the PDF layout and is installed through `requirements.txt`
- PDF download when a PDF was created successfully
- Per-job run logs saved to `instance/generated/<job-id>/run.log`
- Result page displays captured `stdout`, `stderr`, command, return code, and PDF status
- A demo flag in `flag.txt`
- Default development bind is `127.0.0.1`

## Run locally (Linux/Kali)

```bash
cd resumeforge_cmdi
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`.

The SQLite database and output folders are created automatically on the first run. The app binds to localhost by default. Use only fake demo data.

**Updating an existing checkout:** stop the running server, extract the updated project, activate the same virtual environment, and run `python -m pip install -r requirements.txt` before starting `python app.py` again. The PDF renderer now needs ReportLab.

## Verify the log-output behaviour

1. Generate a normal resume first. The result page should show the PDF engine's status lines under **STDOUT** and a complete run log below.
2. In the output filename field, enter this lab-only test value:

   ```text
   resume.pdf"; echo"$(command)"; #
   ```

3. Generate the resume. On Linux, the shell closes the quoted output-path argument at the embedded quote, runs the injected `echo`, and then treats the remainder as a comment. The result page should show both the PDF engine output and `INJECTION_PROOF` in **STDOUT**. The full command and output are also stored in that job's `run.log`.
4. The intended flag file is `flag.txt`; challenge builders can decide how much hinting to provide.

This payload is for confirming the intentionally vulnerable lab behaviour. Keep all testing within the local disposable environment.

## Project structure

```text
resumeforge_cmdi/
├── app.py                 # Flask routes and intentionally vulnerable command construction
├── database.py            # SQLite schema and synthetic student records
├── pdf_engine.py          # Styled, vector-based A4 PDF renderer
├── flag.txt               # Demo CTF flag
├── requirements.txt
├── templates/
│   ├── index.html         # Portal form
│   ├── resume.html        # Resume HTML template
│   ├── result.html        # Status + stdout/stderr + complete logs
│   └── logs.html          # Stored run log viewer
├── static/style.css
└── instance/              # Created at runtime; database, work files, PDFs and logs
```

## Vulnerable line and defensive lesson

The intentional flaw is in `app.py`'s `_build_vulnerable_command()`:

- the command is created as a shell string;
- the raw user-controlled filename is embedded inside double quotes without shell escaping;
- `subprocess.run(..., shell=True)` asks the shell to interpret that string.

**Production fix:** do not use a shell string. Call the converter with an argument list (`subprocess.run([executable, input_path, output_path], shell=False, ...)`) and derive the output path only from a strict allowlist such as `secure_filename()`. Never accept a raw shell fragment as a path. In this demo the vulnerable and safe path variables are intentionally separated so normal download handling still works when the demonstration payload is entered.

## Troubleshooting

- **Port already in use:** set `PORT=5050 python app.py`, then browse to `http://127.0.0.1:5050`.
- **No PDF appears:** check the result page's `STDERR` and the stored `run.log`.
- **Database reset:** stop the app and remove `instance/resumeforge.db`; the demo records are seeded on the next start.
- **Command syntax differs on Windows:** the proof payload above uses POSIX shell syntax and is intended for Linux/Kali or the provided Linux container.
