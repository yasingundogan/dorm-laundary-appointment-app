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
├── app.py              # Flask application and routes
├── db.py               # Database connection and availability queries
├── schema.sql          # Database schema and constraints
├── seed.py              # Creates and populates the sample database
├── sorgular.sql        # Example SQL queries
├── test.sql            # Database constraint test scenarios
├── requirements.txt
└── templates/
    └── makineler.html  # Machine list template
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
python -m pip install -r requirements.txt
```

### 4. Initialize the database and sample data

Run the seed script from the project root:

```bash
python seed.py
```

This script runs `schema.sql` to recreate the tables and inserts sample machines, students, and appointments. **It resets the existing project database**, so do not run it against data you want to keep.

### 5. Start the application

```bash
python app.py
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

Machine occupancy is calculated from active appointments. In the current implementation, washing-machine reservations are treated as one hour and dryer reservations as two hours.

## SQL Files

- **`schema.sql`** — creates the tables, constraints, and index.
- **`seed.py`** — resets the schema and generates sample records.
- **`sorgular.sql`** — examples for querying machine availability, student appointments, and cancellations.
- **`test.sql`** — sample inserts and scenarios for checking database constraints.

To run the schema directly with the SQLite CLI:

```bash
sqlite3 camasirhane.db < schema.sql
```

## Current Scope

This repository currently provides a basic Flask application with a machine-status page and a database foundation. Appointment creation and cancellation workflows, authentication, and a full student-facing booking interface are not exposed as complete web flows yet.

## License

No license file is currently included. Unless a license is added, the repository's contents are not explicitly licensed for reuse.
