# Dorm Laundry Appointment App

A small web application for managing laundry-room availability in a dormitory. The project uses **Flask** for the web layer and **SQLite** to store machines, students, and appointments.

## Features

- View laundry and dryer machines.
- Check whether a machine is occupied at a selected time.
- Track machines that are out of order.
- Store student and appointment records in a relational database.
- Prevent two active appointments from reserving the same machine at the same start time.
- Keep cancelled and completed appointment records for later review.
- Populate the database with sample data for development and testing.

## Tech Stack

- **Python**
- **Flask**
- **SQLite**
- **SQL** (schema, sample queries, and test scenarios)
- **Jinja2** templates

## Project Structure

```text
dorm-laundary-appointment-app/
├── app.py              # App setup: config, CSRF, blueprint registration
├── zaman.py            # Single source of "now" (Europe/Istanbul)
├── kurallar.py         # Pure business rules (durations, hours, quota, validation)
├── servis.py           # Workflows: rules + database + locked transactions
├── db.py               # SQL queries
├── migrations.py       # Applies numbered schema migrations
├── migrations/         # 001_baslangic.sql, 002_..., one file per schema change
├── web/                # Blueprints: auth, randevu, profil, bildirim, yurt
├── templates/          # Jinja templates (base.html + pages)
├── static/             # img/ (logo, icons, photos) and LISANSLAR.md (image licenses)
├── seed.py             # Rebuilds the dev database with sample data
├── sorgular.sql        # Example SQL queries
├── test.sql            # Database constraint scenarios (SQLite CLI)
├── tests/              # pytest suite
├── requirements.txt    # Runtime dependencies
└── requirements-dev.txt  # + pytest
```

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/yasingundogan/dorm-laundary-appointment-app.git
cd dorm-laundary-appointment-app
```

### 2. Create and activate a virtual environment

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows (PowerShell)**

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
python -m pip install -r requirements-dev.txt   # or requirements.txt without pytest
```

### 4. Initialize the database and sample data

Run the seed script from the project root:

```bash
python seed.py
```

This script deletes `camasirhane.db`, rebuilds it by applying the migrations in `migrations/`, and inserts sample dorm blocks, machines, students, and appointments. **It resets the existing project database**, so do not run it against data you want to keep. Every sample student's password is `test1234` (e.g. `ogrenci1@ornek.com`).

### 5. Start the application

```bash
FLASK_DEBUG=1 python app.py      # development (auto-reload, debugger)
SECRET_KEY=... python app.py     # production: always set a fixed secret key; never enable FLASK_DEBUG
```

Open [http://127.0.0.1:5001](http://127.0.0.1:5001) in your browser.

- `/` — basic home route
- `/makineler` — machine listing and availability status
- `/makineler?zaman=2026-10-07%2014:30:00` — check status at a specific date and time

The `zaman` query parameter uses the format `YYYY-MM-DD HH:MM:SS`.

## Database Overview

The SQLite database contains three main tables:

| Table | Purpose |
| --- | --- |
| `machines` | Washing machines and dryers, including out-of-order status |
| `students` | Student names, contact details, and room numbers |
| `appointments` | Reservations, start times, programs, and statuses |

The schema includes foreign-key constraints, unique student email and phone values, validation for machine type and appointment status, and a partial unique index that prevents duplicate active reservations for the same machine and start time.

Machine occupancy is calculated from active appointments. Durations live in one place, `kurallar.SURELER`: colored wash 1 hour, white wash 1 hour, dryer 2 hours. Each appointment's `end_time` is computed from it when the booking is created and stored in the database. All times are Istanbul local time; the app never reads the server clock directly (see `zaman.py`).

## Database Migrations

The schema is defined by numbered files in `migrations/`. Applied migrations are recorded in the `schema_migrations` table, so schema changes no longer require wiping the data.

```bash
python migrations.py            # apply pending migrations (DB_PATH or camasirhane.db)
python migrations.py --durum    # show applied / pending migrations
python migrations.py --sifirdan # dev only: delete the database and rebuild it (DATA IS LOST)
```

To change the schema, add the next numbered file (e.g. `002_student_role.sql`). **Never edit a migration that has already been applied**; it has already run on other machines. Each migration runs in a single transaction: if any statement fails, none of it is applied.

## Tests and CI

```bash
python -m pytest -q
```

Tests run against a temporary database built with the same migrations, with "now" fixed to 25 Nov 2026 12:00 so date-based tests do not break as the calendar moves. A GitHub Actions workflow (`.github/workflows/testler.yml`) is prepared but **not yet in the repository**: pushing workflow files requires a GitHub token with the `workflow` scope. Once added, it runs the suite on Python 3.12 and 3.13 for every push to `main` and every pull request, and checks that the database can be rebuilt from scratch with `seed.py`. Until then, run `python -m pytest -q` before opening a pull request.

## SQL Files

- **`migrations/`** — the schema: tables, constraints, and indexes.
- **`seed.py`** — rebuilds the database from the migrations and generates sample records.
- **`sorgular.sql`** — examples for querying machine availability, student appointments, and cancellations.
- **`test.sql`** — sample inserts and scenarios for checking database constraints.

To run the constraint scenarios with the SQLite CLI (expected output: 6 errors):

```bash
python migrations.py --sifirdan && sqlite3 camasirhane.db < test.sql
```

## Current Scope

Implemented: registration and login (CSRF protection, login rate limiting), dorm/block laundry rooms, machine page with a day timeline, booking with rule checks and a confirmation dialog, cancellation, waitlist, in-app notifications, profile editing, fault reports with photos, and a lost-and-found board.

Not yet implemented: staff/admin panel (confirming fault reports, marking no-shows), password reset, push/e-mail notifications (notifications are currently generated when a page is opened), and a KVKK privacy notice.

## License

No license file is currently included. Unless a license is added, the repository's contents are not explicitly licensed for reuse.
