INSERT INTO Department
    (DepartmentID, DepartmentName, Location)
VALUES
    (1, 'Engineering', 'Pune'),
    (2, 'Human Resources', 'Mumbai'),
    (3, 'Finance', 'Bangalore'),
    (4, 'Sales', 'Delhi');


INSERT INTO Employee
    (FirstName, LastName, DepartmentID, Salary, Bonus, HireDate)
VALUES
    ('Rohan', 'Chaudhari', 1, 800000.00, 80000.00, '2026-10-05'),
    ('Amit', 'Patil', 1, 700000.00, NULL, '2023-04-10'),
    ('Priya', 'Deshmukh', 2, 650000.00, 65000.00, '2022-07-20'),
    ('Sneha', 'Joshi', 3, 900000.00, NULL, '2021-03-12'),
    ('Rahul', 'Kulkarni', 4, 600000.00, 120000.00, '2024-02-01'),
    ('Neha', 'Shinde', 4, 550000.00, 50000.00, '2023-09-15');
