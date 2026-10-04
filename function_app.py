import json
import logging
from datetime import date
from decimal import Decimal

import azure.functions as func
import pyodbc

from db import get_connection


app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


def response(data, status_code=200):
    return func.HttpResponse(
        json.dumps(data, default=str),
        status_code=status_code,
        mimetype="application/json"
    )


#def employee_from_row(row):
    if row is None:
        return None

    return {
        "EmployeeID": row.EmployeeID,
        "FirstName": row.FirstName,
        "LastName": row.LastName,
        "DepartmentID": row.DepartmentID,
        "DepartmentName": row.DepartmentName,
        "Location": row.Location,
        "Salary": float(row.Salary) if row.Salary is not None else None,
        "Bonus": float(row.Bonus) if row.Bonus is not None else None,
        "HireDate": row.HireDate.isoformat() if row.HireDate else None
    }
def employee_from_row(row):
    if row is None:
        return None

    effective_bonus = (
        float(row.Bonus)
        if row.Bonus is not None
        else float(row.Salary) * 0.05
    )

    return {
        "EmployeeID": row.EmployeeID,
        "FirstName": row.FirstName,
        "LastName": row.LastName,
        "DepartmentID": row.DepartmentID,
        "DepartmentName": row.DepartmentName,
        "Location": row.Location,
        "Salary": float(row.Salary) if row.Salary is not None else None,
        "Bonus": float(row.Bonus) if row.Bonus is not None else None,
        "EffectiveBonus": effective_bonus,
        "HireDate": row.HireDate.isoformat() if row.HireDate else None
    } 
def validate_money(value, field_name, required=False):
    if value is None:
        if required:
            return f"{field_name} is required"
        return None

    if isinstance(value, bool):
        return f"{field_name} must be a number"

    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return f"{field_name} must be a number"

    if numeric_value < 0:
        return f"{field_name} cannot be negative"

    return None

def validate_department(cursor, department_id):
    if department_id is None:
        return True

    cursor.execute(
        "SELECT 1 FROM Department WHERE DepartmentID = ?",
        department_id
    )

    return cursor.fetchone() is not None


def parse_decimal(value, field_name):
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be a number")


# ---------------------------------------------------------
# CREATE EMPLOYEE
# POST /api/employees
# ---------------------------------------------------------

@app.route(
    route="employees",
    methods=["POST"]
)
def create_employee(req: func.HttpRequest) -> func.HttpResponse:

    try:
        data = req.get_json()

        required_fields = [
            "FirstName",
            "LastName",
            "Salary"
        ]

        for field in required_fields:
            if field not in data:
                return response(
                    {"error": f"{field} is required"},
                    400
                )

        first_name = data["FirstName"]
        last_name = data["LastName"]
        department_id = data.get("DepartmentID")
        salary = data["Salary"]
        bonus = data.get("Bonus")
        hire_date = data.get("HireDate")

        if not first_name or not last_name:
            return response(
                {"error": "FirstName and LastName cannot be empty"},
                400
            )

        salary_error = validate_money(salary, "Salary", required=True)
        if salary_error:
            return response({"error": salary_error}, 400)
        salary = float(salary)

        bonus_error = validate_money(bonus, "Bonus")
        if bonus_error:
            return response({"error": bonus_error}, 400)

        if bonus is not None:
            bonus = float(bonus)
            if bonus < 0:
                return response(
                    {"error": "Bonus cannot be negative"},
                    400
                )

        if salary < 0:
            return response(
                {"error": "Salary cannot be negative"},
                400
            )

        conn = get_connection()

        try:
            cursor = conn.cursor()

            if not validate_department(cursor, department_id):
                return response(
                    {"error": "DepartmentID does not exist"},
                    400
                )

            cursor.execute(
                """
                INSERT INTO Employee
                    (FirstName, LastName, DepartmentID, Salary, Bonus, HireDate)
                OUTPUT INSERTED.EmployeeID
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                first_name,
                last_name,
                department_id,
                salary,
                bonus,
                hire_date
            )

            employee_id = cursor.fetchone()[0]
            conn.commit()

            return response(
                {
                    "message": "Employee created successfully",
                    "EmployeeID": employee_id
                },
                201
            )

        finally:
            conn.close()

    except ValueError:
        return response(
            {"error": "Request body must contain valid JSON"},
            400
        )

    except pyodbc.Error:
        logging.exception("Database error while creating employee")
        return response(
            {"error": "Database error"},
            500
        )

    except Exception:
        logging.exception("Unexpected error while creating employee")
        return response(
            {"error": "Internal server error"},
            500
        )


# ---------------------------------------------------------
# GET EMPLOYEE BY ID
# GET /api/employees/{employee_id}
# ---------------------------------------------------------

@app.route(
    route="employees/{employee_id}",
    methods=["GET"]
)
def get_employee(req: func.HttpRequest) -> func.HttpResponse:

    try:
        employee_id = int(req.route_params.get("employee_id"))

        conn = get_connection()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT
                    e.EmployeeID,
                    e.FirstName,
                    e.LastName,
                    e.DepartmentID,
                    d.DepartmentName,
                    d.Location,
                    e.Salary,
                    e.Bonus,
                    e.HireDate
                FROM Employee e
                LEFT JOIN Department d
                    ON e.DepartmentID = d.DepartmentID
                WHERE e.EmployeeID = ?
                """,
                employee_id
            )

            row = cursor.fetchone()

            if row is None:
                return response(
                    {"error": "Employee not found"},
                    404
                )

            return response(employee_from_row(row))

        finally:
            conn.close()

    except ValueError:
        return response(
            {"error": "EmployeeID must be an integer"},
            400
        )

    except pyodbc.Error:
        logging.exception("Database error while getting employee")
        return response(
            {"error": "Database error"},
            500
        )

    except Exception:
        logging.exception("Unexpected error while getting employee")
        return response(
            {"error": "Internal server error"},
            500
        )


# ---------------------------------------------------------
# LIST EMPLOYEES
# GET /api/employees
# GET /api/employees?departmentId=1
# ---------------------------------------------------------

@app.route(
    route="employees",
    methods=["GET"]
)
def list_employees(req: func.HttpRequest) -> func.HttpResponse:

    try:
        department_id = req.params.get("departmentId")

        conn = get_connection()

        try:
            cursor = conn.cursor()

            if department_id is not None:

                try:
                    department_id = int(department_id)
                except ValueError:
                    return response(
                        {"error": "departmentId must be an integer"},
                        400
                    )

                cursor.execute(
                    """
                    SELECT
                        e.EmployeeID,
                        e.FirstName,
                        e.LastName,
                        e.DepartmentID,
                        d.DepartmentName,
                        d.Location,
                        e.Salary,
                        e.Bonus,
                        e.HireDate
                    FROM Employee e
                    LEFT JOIN Department d
                        ON e.DepartmentID = d.DepartmentID
                    WHERE e.DepartmentID = ?
                    ORDER BY e.EmployeeID
                    """,
                    department_id
                )

            else:

                cursor.execute(
                    """
                    SELECT
                        e.EmployeeID,
                        e.FirstName,
                        e.LastName,
                        e.DepartmentID,
                        d.DepartmentName,
                        d.Location,
                        e.Salary,
                        e.Bonus,
                        e.HireDate
                    FROM Employee e
                    LEFT JOIN Department d
                        ON e.DepartmentID = d.DepartmentID
                    ORDER BY e.EmployeeID
                    """
                )

            rows = cursor.fetchall()

            employees = [
                employee_from_row(row)
                for row in rows
            ]

            return response(employees)

        finally:
            conn.close()

    except pyodbc.Error:
        logging.exception("Database error while listing employees")
        return response(
            {"error": "Database error"},
            500
        )

    except Exception:
        logging.exception("Unexpected error while listing employees")
        return response(
            {"error": "Internal server error"},
            500
        )


# ---------------------------------------------------------
# UPDATE EMPLOYEE
# PUT /api/employees/{employee_id}
# ---------------------------------------------------------

@app.route(
    route="employees/{employee_id}",
    methods=["PUT"]
)
def update_employee(req: func.HttpRequest) -> func.HttpResponse:

    try:
        employee_id = int(req.route_params.get("employee_id"))
        data = req.get_json()

        allowed_fields = {
            "FirstName",
            "LastName",
            "DepartmentID",
            "Salary",
            "Bonus",
            "HireDate"
        }

        updates = {
            key: value
            for key, value in data.items()
            if key in allowed_fields
        }

        if not updates:
            return response(
                {"error": "No valid fields supplied for update"},
                400
            )

        if "Salary" in updates:
           salary_error = validate_money(updates["Salary"], "Salary")
           if salary_error:
               return response({"error": salary_error}, 400)

        if "Bonus" in updates:
           bonus_error = validate_money(updates["Bonus"], "Bonus")
           if bonus_error:
              return response({"error": bonus_error}, 400)

        conn = get_connection()

        try:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT EmployeeID FROM Employee WHERE EmployeeID = ?",
                employee_id
            )

            if cursor.fetchone() is None:
                return response(
                    {"error": "Employee not found"},
                    404
                )

            if "DepartmentID" in updates:
                if not validate_department(
                    cursor,
                    updates["DepartmentID"]
                ):
                    return response(
                        {"error": "DepartmentID does not exist"},
                        400
                    )

            set_clauses = []
            parameters = []

            for field, value in updates.items():
                set_clauses.append(f"{field} = ?")
                parameters.append(value)

            parameters.append(employee_id)

            query = f"""
                UPDATE Employee
                SET {", ".join(set_clauses)}
                WHERE EmployeeID = ?
            """

            cursor.execute(query, parameters)
            conn.commit()

            return response(
                {"message": "Employee updated successfully"}
            )

        finally:
            conn.close()

    except ValueError:
        return response(
            {"error": "EmployeeID must be an integer"},
            400
        )

    except pyodbc.Error:
        logging.exception("Database error while updating employee")
        return response(
            {"error": "Database error"},
            500
        )

    except Exception:
        logging.exception("Unexpected error while updating employee")
        return response(
            {"error": "Internal server error"},
            500
        )


# ---------------------------------------------------------
# DELETE EMPLOYEE
# DELETE /api/employees/{employee_id}
# ---------------------------------------------------------

@app.route(
    route="employees/{employee_id}",
    methods=["DELETE"]
)
def delete_employee(req: func.HttpRequest) -> func.HttpResponse:

    try:
        employee_id = int(req.route_params.get("employee_id"))

        conn = get_connection()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                DELETE FROM Employee
                WHERE EmployeeID = ?
                """,
                employee_id
            )

            if cursor.rowcount == 0:
                return response(
                    {"error": "Employee not found"},
                    404
                )

            conn.commit()

            return response(
                {"message": "Employee deleted successfully"}
            )

        finally:
            conn.close()

    except ValueError:
        return response(
            {"error": "EmployeeID must be an integer"},
            400
        )

    except pyodbc.Error:
        logging.exception("Database error while deleting employee")
        return response(
            {"error": "Database error"},
            500
        )

    except Exception:
        logging.exception("Unexpected error while deleting employee")
        return response(
            {"error": "Internal server error"},
            500
        )

@app.route(route="reports/total-bonus", methods=["GET"])
def total_bonus_report(req: func.HttpRequest) -> func.HttpResponse:
    try:
        conn = get_connection()
        try:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT COALESCE(SUM(Bonus), 0) AS TotalBonus
                FROM Employee
            """)

            row = cursor.fetchone()

            return response({
                "TotalBonus": float(row.TotalBonus)
            })

        finally:
            conn.close()

    except pyodbc.Error:
        logging.exception("Database error while calculating total bonus")
        return response({"error": "Database error"}, 500)

    except Exception:
        logging.exception("Unexpected error while calculating total bonus")
        return response({"error": "Internal server error"}, 500)

@app.route(route="reports/no-bonus", methods=["GET"])
def employees_without_bonus_report(req: func.HttpRequest) -> func.HttpResponse:
    try:
        conn = get_connection()
        try:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    EmployeeID,
                    FirstName,
                    LastName,
                    DepartmentID,
                    Salary,
                    Bonus,
                    HireDate
                FROM Employee
                WHERE Bonus IS NULL
                ORDER BY EmployeeID
            """)

            rows = cursor.fetchall()

            employees = [
                {
                    "EmployeeID": row.EmployeeID,
                    "FirstName": row.FirstName,
                    "LastName": row.LastName,
                    "DepartmentID": row.DepartmentID,
                    "Salary": float(row.Salary),
                    "Bonus": None,
                    "HireDate": row.HireDate.isoformat() if row.HireDate else None
                }
                for row in rows
            ]

            return response(employees)

        finally:
            conn.close()

    except pyodbc.Error:
        logging.exception("Database error while finding employees without bonus")
        return response({"error": "Database error"}, 500)

    except Exception:
        logging.exception(
            "Unexpected error while finding employees without bonus"
        )
        return response({"error": "Internal server error"}, 500)

@app.route(route="reports/bonus-percentage", methods=["GET"])
def bonus_percentage_report(req: func.HttpRequest) -> func.HttpResponse:
    try:
        conn = get_connection()
        try:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    EmployeeID,
                    FirstName,
                    LastName,
                    Salary,
                    Bonus,
                    ROUND((Bonus * 100.0) / NULLIF(Salary, 0), 2)
                        AS BonusPercentage
                FROM Employee
                WHERE Bonus IS NOT NULL
                ORDER BY EmployeeID
            """)

            rows = cursor.fetchall()

            employees = [
                {
                    "EmployeeID": row.EmployeeID,
                    "FirstName": row.FirstName,
                    "LastName": row.LastName,
                    "Salary": float(row.Salary),
                    "Bonus": float(row.Bonus),
                    "BonusPercentage": float(row.BonusPercentage)
                }
                for row in rows
            ]

            return response(employees)

        finally:
            conn.close()

    except pyodbc.Error:
        logging.exception("Database error while calculating bonus percentages")
        return response({"error": "Database error"}, 500)

    except Exception:
        logging.exception(
            "Unexpected error while calculating bonus percentages"
        )
        return response({"error": "Internal server error"}, 500)

@app.route(route="reports/department-bonus", methods=["GET"])
def department_bonus_report(req: func.HttpRequest) -> func.HttpResponse:
    try:
        conn = get_connection()
        try:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    d.DepartmentID,
                    d.DepartmentName,
                    SUM(COALESCE(e.Bonus, 0)) AS TotalBonus,
                    AVG(e.Salary) AS AverageSalary
                FROM Department d
                INNER JOIN Employee e
                    ON d.DepartmentID = e.DepartmentID
                GROUP BY
                    d.DepartmentID,
                    d.DepartmentName
                HAVING
                    SUM(COALESCE(e.Bonus, 0)) > AVG(e.Salary)
                ORDER BY d.DepartmentID
            """)

            rows = cursor.fetchall()

            departments = [
                {
                    "DepartmentID": row.DepartmentID,
                    "DepartmentName": row.DepartmentName,
                    "TotalBonus": float(row.TotalBonus),
                    "AverageSalary": float(row.AverageSalary)
                }
                for row in rows
            ]

            return response(departments)

        finally:
            conn.close()

    except pyodbc.Error:
        logging.exception(
            "Database error while calculating department bonus report"
        )
        return response({"error": "Database error"}, 500)

    except Exception:
        logging.exception(
            "Unexpected error while calculating department bonus report"
        )
        return response({"error": "Internal server error"}, 500)

@app.route(route="reports/bonus-ranking", methods=["GET"])
def bonus_ranking_report(req: func.HttpRequest) -> func.HttpResponse:
    try:
        conn = get_connection()
        try:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    EmployeeID,
                    FirstName,
                    LastName,
                    Salary,
                    Bonus,
                    RANK() OVER (
                        ORDER BY
                            CASE WHEN Bonus IS NULL THEN 1 ELSE 0 END,
                            Bonus DESC
                    ) AS BonusRank
                FROM Employee
                ORDER BY
                    CASE WHEN Bonus IS NULL THEN 1 ELSE 0 END,
                    Bonus DESC,
                    EmployeeID
            """)

            rows = cursor.fetchall()

            employees = [
                {
                    "EmployeeID": row.EmployeeID,
                    "FirstName": row.FirstName,
                    "LastName": row.LastName,
                    "Salary": float(row.Salary),
                    "Bonus": float(row.Bonus) if row.Bonus is not None else None,
                    "BonusRank": row.BonusRank
                }
                for row in rows
            ]

            return response(employees)

        finally:
            conn.close()

    except pyodbc.Error:
        logging.exception("Database error while ranking employees by bonus")
        return response({"error": "Database error"}, 500)

    except Exception:
        logging.exception("Unexpected error while ranking employees by bonus")
        return response({"error": "Internal server error"}, 500)

@app.route(route="reports/highest-salary", methods=["GET"])
def highest_salary_report(req: func.HttpRequest) -> func.HttpResponse:
    try:
        conn = get_connection()
        try:
            cursor = conn.cursor()

            # Employee with the highest base salary
            cursor.execute("""
                SELECT TOP 1
                    EmployeeID,
                    FirstName,
                    LastName,
                    Salary,
                    Bonus
                FROM Employee
                ORDER BY Salary DESC, EmployeeID ASC
            """)

            base_salary_row = cursor.fetchone()

            if base_salary_row is None:
                return response({
                    "message": "No employees found"
                }, 404)

            # Employee with the highest total compensation
            cursor.execute("""
                SELECT TOP 1
                    EmployeeID,
                    Salary,
                    Bonus,
                    Salary + COALESCE(Bonus, 0) AS TotalCompensation
                FROM Employee
                ORDER BY
                    Salary + COALESCE(Bonus, 0) DESC,
                    EmployeeID ASC
            """)

            total_comp_row = cursor.fetchone()

            highest_base_salary_employee = {
                "EmployeeID": base_salary_row.EmployeeID,
                "FirstName": base_salary_row.FirstName,
                "LastName": base_salary_row.LastName,
                "Salary": float(base_salary_row.Salary),
                "Bonus": (
                    float(base_salary_row.Bonus)
                    if base_salary_row.Bonus is not None
                    else None
                )
            }

            highest_total_compensation_employee = {
                "EmployeeID": total_comp_row.EmployeeID,
                "TotalCompensation": float(
                    total_comp_row.TotalCompensation
                )
            }

            same_employee = (
                base_salary_row.EmployeeID
                == total_comp_row.EmployeeID
            )

            return response({
                "highestBaseSalaryEmployee": highest_base_salary_employee,
                "highestTotalCompensationEmployee":
                    highest_total_compensation_employee,
                "sameEmployeeHasHighestTotalCompensation": same_employee
            })

        finally:
            conn.close()

    except pyodbc.Error:
        logging.exception(
            "Database error while calculating highest salary report"
        )
        return response({"error": "Database error"}, 500)

    except Exception:
        logging.exception(
            "Unexpected error while calculating highest salary report"
        )
        return response({"error": "Internal server error"}, 500)