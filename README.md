# Employee Compensation Service

A production-minded HTTP API built with Python Azure Functions and Azure SQL Database for managing employee compensation data.

## Architecture

Client -> Azure Functions HTTP API -> Azure SQL Database

All employee reads and writes are performed through HTTP-triggered Azure Functions. The client does not access the database directly.

## Technology Stack

- Python 3.12
- Azure Functions v4
- Azure Functions Python v2 programming model
- Azure SQL Database
- pyodbc
- Microsoft ODBC Driver 18 for SQL Server

## Database

### Department

| Column | Type | Description |
|---|---|---|
| DepartmentID | INT | Primary key |
| DepartmentName | VARCHAR(100) | Department name |
| Location | VARCHAR(100) | Optional location |

### Employee

| Column | Type | Description |
|---|---|---|
| EmployeeID | INT IDENTITY | Primary key |
| FirstName | VARCHAR(50) | Employee first name |
| LastName | VARCHAR(50) | Employee last name |
| DepartmentID | INT | Foreign key to Department |
| Salary | DECIMAL(12,2) | Base salary |
| Bonus | DECIMAL(12,2) | Nullable bonus |
| HireDate | DATE | Hire date |

`Bonus = NULL` represents an employee who has not received a bonus.

## API Endpoints

### Employee CRUD

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/employees` | Create employee |
| GET | `/api/employees/{employee_id}` | Get employee |
| GET | `/api/employees` | List employees |
| GET | `/api/employees?departmentId={id}` | List employees by department |
| PUT | `/api/employees/{employee_id}` | Update employee |
| DELETE | `/api/employees/{employee_id}` | Delete employee |

### Reports

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/reports/total-bonus` | Total bonus |
| GET | `/api/reports/no-bonus` | Employees with no bonus |
| GET | `/api/reports/bonus-percentage` | Bonus as percentage of salary |
| GET | `/api/reports/department-bonus` | Departments where total bonus exceeds average salary |
| GET | `/api/reports/bonus-ranking` | Employees ranked by bonus |
| GET | `/api/reports/highest-salary` | Highest base salary and total compensation comparison |

## Configuration

The SQL connection string is not hardcoded in the application.

For local development, configure `local.settings.json` with:

`SQL_CONNECTION_STRING`

For Azure deployment, configure the same setting as an Azure Function App Application Setting.

`local.settings.json` is excluded from source control because it may contain secrets.

## Error Handling

The API uses appropriate HTTP status codes:

- `200 OK` - successful request
- `201 Created` - employee created
- `400 Bad Request` - invalid input
- `404 Not Found` - employee does not exist
- `500 Internal Server Error` - unexpected/database error

Database errors are logged while the API returns a generic error message rather than exposing database details.

## Validation

The API validates:

- Required first and last names
- Numeric and non-negative salary
- Numeric and non-negative bonus
- Valid employee IDs
- Valid department IDs
- Supported update fields

SQL values are parameterized to prevent SQL injection.

## Default Bonus Decision

The optional 5% default bonus is applied at read time as `EffectiveBonus`.

The stored `Bonus` value remains `NULL` when the employee has not actually received a bonus.

This preserves the distinction required by the no-bonus report and avoids modifying stored historical compensation data.

## SQL Scripts

The `sql` directory contains:

- `01_schema.sql` - database schema
- `02_seed.sql` - sample departments and employees

## Running Locally

1. Activate the Python virtual environment.
2. Install dependencies:

```text
pip install -r requirements.txt
```

3. Ensure Azurite is running.
4. Configure `SQL_CONNECTION_STRING` in `local.settings.json`.
5. Start the Functions host:

```text
func start
```

The local API is available at:

`http://localhost:7071/api`

## Project Structure

```text
EmployeeCompensationService/
├── .funcignore
├── .gitignore
├── db.py
├── function_app.py
├── host.json
├── requirements.txt
├── README.md
└── sql/
    ├── 01_schema.sql
    └── 02_seed.sql
```

## Design Notes

- `LEFT JOIN` is used for employee retrieval so employees with a nullable DepartmentID are not unintentionally excluded.
- `COALESCE` is used where NULL bonus values must be treated as zero.
- `NULLIF` prevents division-by-zero in bonus percentage calculations.
- `RANK()` is used for bonus ranking; employees with equal bonuses receive the same rank.
- EmployeeID is used as a deterministic tie-breaker where appropriate.
- Azure SQL transient connection error 40613 is retried before returning a database error.
