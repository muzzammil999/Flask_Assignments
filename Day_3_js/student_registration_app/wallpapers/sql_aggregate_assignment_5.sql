DROP TABLE IF EXISTS students;
CREATE TABLE students (
    student_id   INT           PRIMARY KEY AUTO_INCREMENT,
    name         VARCHAR(60)   NOT NULL,
    age          INT,
    city         VARCHAR(40),
    course       VARCHAR(50),
    batch        VARCHAR(20),
    fees_paid    DECIMAL(8,2),
    join_date    DATE,
    email        VARCHAR(80),
    phone        VARCHAR(15),
    gender       CHAR(1),           -- 'M' or 'F'
    is_active    TINYINT(1)         -- 1=active, 0=dropped
);

desc students;

INSERT INTO students VALUES
(1,  'Arjun Sharma',    21, 'Hyderabad', 'Python Full Stack',  'Batch A', 45000.00, '2024-01-10', 'arjun@mail.com',    '9876543210', 'M', 1),
(2,  'Priya Reddy',     20, 'Vijayawada','Data Science',       'Batch B', 38000.00, '2024-02-01', 'priya@mail.com',    '9876543211', 'F', 1),
(3,  'Ravi Kumar',      23, 'Hyderabad', 'Python Full Stack',  'Batch A', 45000.00, '2024-01-10', 'ravi@mail.com',     '9876543212', 'M', 1),
(4,  'Sneha Patel',     22, 'Mumbai',    'Data Science',       'Batch B', 35000.00, '2024-02-01', 'sneha@mail.com',    '9876543213', 'F', 0),
(5,  'Kiran Babu',      25, 'Bangalore', 'DevOps',             'Batch C', 55000.00, '2024-03-15', 'kiran@mail.com',    '9876543214', 'M', 1),
(6,  'Anjali Singh',    21, 'Hyderabad', 'Python Full Stack',  'Batch A', 45000.00, '2024-01-10', 'anjali@mail.com',   '9876543215', 'F', 1),
(7,  'Vikram Rao',      24, 'Chennai',   'DevOps',             'Batch C', 55000.00, '2024-03-15', 'vikram@mail.com',   '9876543216', 'M', 1),
(8,  'Divya Nair',      20, 'Kochi',     'Data Science',       'Batch B', 38000.00, '2024-02-01', 'divya@mail.com',    '9876543217', 'F', 1),
(9,  'Suresh Verma',    26, 'Delhi',     'Python Full Stack',  'Batch A', 42000.00, '2024-01-10', 'suresh@mail.com',   '9876543218', 'M', 0),
(10, 'Meera Joshi',     22, 'Pune',      'Data Science',       'Batch B', 38000.00, '2024-02-01', 'meera@mail.com',    '9876543219', 'F', 1),
(11, 'Rahul Gupta',     23, 'Hyderabad', 'DevOps',             'Batch C', 55000.00, '2024-03-15', 'rahul@mail.com',    '9876543220', 'M', 1),
(12, 'Lakshmi Devi',    21, 'Vijayawada','Python Full Stack',  'Batch A', 45000.00, '2024-01-10', 'lakshmi@mail.com',  '9876543221', 'F', 1),
(13, 'Arun Krishnan',   24, 'Bangalore', 'Data Science',       'Batch B', NULL,     '2024-02-01', 'arun@mail.com',     '9876543222', 'M', 1),
(14, 'Pooja Mishra',    22, 'Bhopal',    'Python Full Stack',  'Batch A', 45000.00, '2024-01-10', 'pooja@mail.com',    '9876543223', 'F', 1),
(15, 'Naveen Chandra',  25, 'Hyderabad', 'DevOps',             'Batch C', 50000.00, '2024-03-15', 'naveen@mail.com',   '9876543224', 'M', 1),
(16, 'Swetha Reddy',    20, 'Vijayawada','Data Science',       'Batch B', 38000.00, '2024-02-01', 'swetha@mail.com',   '9876543225', 'F', 1),
(17, 'Mohan Das',       28, 'Kolkata',   'DevOps',             'Batch C', 55000.00, '2024-03-15', 'mohan@mail.com',    '9876543226', 'M', 0),
(18, 'Kavya Sharma',    21, 'Hyderabad', 'Python Full Stack',  'Batch A', 45000.00, '2024-01-10', 'kavya@mail.com',    '9876543227', 'F', 1),
(19, 'Deepak Sinha',    23, 'Patna',     'Data Science',       'Batch B', NULL,     '2024-02-01', 'deepak@mail.com',   '9876543228', 'M', 1),
(20, 'Harini Rajan',    22, 'Chennai',   'Python Full Stack',  'Batch A', 40000.00, '2024-01-10', 'harini@mail.com',   '9876543229', 'F', 1);



select * from students;

-- ╔══════════════════════════════════════════════════════╗
-- ║           TABLE 2 :  courses                         ║
-- ╚══════════════════════════════════════════════════════╝
DROP TABLE IF EXISTS courses;
CREATE TABLE courses (
    course_id     INT          PRIMARY KEY AUTO_INCREMENT,
    course_name   VARCHAR(60)  NOT NULL,
    duration_weeks INT,
    fee           DECIMAL(8,2),
    instructor    VARCHAR(50),
    department    VARCHAR(40),
    seats_total   INT,
    seats_filled  INT
);

INSERT INTO courses VALUES
(1, 'Python Full Stack',  16, 45000.00, 'Mr. Praveen',  'Software Dev',   30, 27),
(2, 'Data Science',       20, 38000.00, 'Ms. Ananya',   'Analytics',      25, 22),
(3, 'DevOps',             12, 55000.00, 'Mr. Srikanth', 'Infrastructure', 20, 18),
(4, 'Java Backend',       14, 40000.00, 'Mr. Ramesh',   'Software Dev',   25, 10),
(5, 'UI/UX Design',       10, 30000.00, 'Ms. Preethi',  'Design',         20,  8),
(6, 'Cybersecurity',      18, 60000.00, 'Mr. Akhil',    'Security',       15,  5);


select * from courses;
-- ╔══════════════════════════════════════════════════════╗
-- ║           TABLE 3 :  assignments                     ║
-- ╚══════════════════════════════════════════════════════╝
DROP TABLE IF EXISTS assignments;
CREATE TABLE assignments (
    assignment_id  INT   PRIMARY KEY AUTO_INCREMENT,
    student_id     INT,
    topic          VARCHAR(80),
    score          INT,           -- out of 100
    submitted_date DATE,
    remarks        VARCHAR(100)
);

INSERT INTO assignments VALUES
( 1,  1, 'Python Basics',         88, '2024-02-10', 'Good work'),
( 2,  1, 'Flask REST API',        92, '2024-03-05', 'Excellent'),
( 3,  2, 'Pandas DataFrames',     75, '2024-03-10', 'Needs improvement'),
( 4,  3, 'Python Basics',         95, '2024-02-10', 'Outstanding'),
( 5,  3, 'Flask REST API',        80, '2024-03-05', 'Good'),
( 6,  4, 'Pandas DataFrames',     NULL,'2024-03-10', 'Not submitted'),
( 7,  5, 'Docker Fundamentals',   88, '2024-04-20', 'Good work'),
( 8,  6, 'Python Basics',         72, '2024-02-10', 'Average'),
( 9,  7, 'Docker Fundamentals',   90, '2024-04-20', 'Excellent'),
(10,  8, 'Pandas DataFrames',     85, '2024-03-10', 'Good'),
(11,  9, 'Python Basics',         65, '2024-02-10', 'Average'),
(12, 10, 'Pandas DataFrames',     78, '2024-03-10', 'Good'),
(13, 11, 'Docker Fundamentals',   55, '2024-04-20', 'Below average'),
(14, 12, 'Python Basics',         92, '2024-02-10', 'Excellent'),
(15, 13, 'Pandas DataFrames',     NULL,'2024-03-10', 'Not submitted'),
(16, 14, 'Python Basics',         88, '2024-02-10', 'Good work'),
(17, 15, 'Docker Fundamentals',   70, '2024-04-20', 'Average'),
(18, 16, 'Pandas DataFrames',     82, '2024-03-10', 'Good'),
(19, 17, 'Docker Fundamentals',   NULL,'2024-04-20', 'Not submitted'),
(20, 18, 'Python Basics',         96, '2024-02-10', 'Outstanding'),
(21, 19, 'Pandas DataFrames',     73, '2024-03-10', 'Average'),
(22, 20, 'Python Basics',         84, '2024-02-10', 'Good'),
(23,  1, 'SQL Basics',            79, '2024-04-15', 'Good'),
(24,  2, 'SQL Basics',            88, '2024-04-15', 'Excellent'),
(25,  6, 'Flask REST API',        68, '2024-03-05', 'Needs improvement'),
(26, 18, 'Flask REST API',        91, '2024-03-05', 'Excellent'),
(27, 20, 'SQL Basics',            77, '2024-04-15', 'Good');

-- ╔══════════════════════════════════════════════════════╗
-- ║           TABLE 4 :  fees                            ║
-- ╚══════════════════════════════════════════════════════╝
DROP TABLE IF EXISTS fees;
CREATE TABLE fees (
    fee_id       INT           PRIMARY KEY AUTO_INCREMENT,
    student_id   INT,
    amount       DECIMAL(8,2),
    paid_date    DATE,
    payment_mode VARCHAR(20),   -- Cash, UPI, Card
    remarks      VARCHAR(60)
);

INSERT INTO fees VALUES
( 1,  1, 20000.00, '2024-01-10', 'UPI',  'First installment'),
( 2,  1, 25000.00, '2024-02-15', 'UPI',  'Second installment'),
( 3,  2, 38000.00, '2024-02-01', 'Card', 'Full payment'),
( 4,  3, 25000.00, '2024-01-10', 'Cash', 'First installment'),
( 5,  3, 20000.00, '2024-02-20', 'UPI',  'Second installment'),
( 6,  5, 55000.00, '2024-03-15', 'Card', 'Full payment'),
( 7,  6, 45000.00, '2024-01-12', 'UPI',  'Full payment'),
( 8,  7, 30000.00, '2024-03-15', 'Cash', 'First installment'),
( 9,  7, 25000.00, '2024-04-10', 'UPI',  'Second installment'),
(10,  8, 38000.00, '2024-02-01', 'UPI',  'Full payment'),
(11, 10, 38000.00, '2024-02-01', 'Card', 'Full payment'),
(12, 11, 55000.00, '2024-03-15', 'UPI',  'Full payment'),
(13, 12, 45000.00, '2024-01-10', 'Cash', 'Full payment'),
(14, 14, 45000.00, '2024-01-10', 'UPI',  'Full payment'),
(15, 15, 50000.00, '2024-03-15', 'Card', 'Full payment'),
(16, 16, 38000.00, '2024-02-01', 'UPI',  'Full payment'),
(17, 18, 45000.00, '2024-01-10', 'UPI',  'Full payment'),
(18, 20, 20000.00, '2024-01-10', 'Cash', 'First installment'),
(19, 20, 20000.00, '2024-02-28', 'UPI',  'Second installment');


/*
   ╔══════════════════════════════════════════════════════════════════════════╗
   ║  EXERCISE SET 1 — SELECT, DISTINCT, WHERE, Comparison Operators         ║
   ╠══════════════════════════════════════════════════════════════════════════╣
   ║  1. Retrieve name, course, and city for all students from Bangalore.   ║
   ║  2. List all unique cities where students are from.                    ║
   ║  3. Find students whose age is NOT 21 or 22.                           ║
   ║  4. Get students who joined before 15th January 2024.                  ║
   ║  5. Find all students whose name comes alphabetically after 'M'.       ║
   ╚══════════════════════════════════════════════════════════════════════════╝

   ╔══════════════════════════════════════════════════════════════════════════╗
   ║  EXERCISE SET 2 — AND / OR / NOT / BETWEEN / IN / LIKE                  ║
   ╠══════════════════════════════════════════════════════════════════════════╣
   ║  1. Find active female students in Data Science or Python.             ║
   ║  2. Get students aged between 22 and 25 from South India cities.       ║
   ║  3. Find students NOT from Hyderabad, Mumbai, or Delhi.                ║
   ║  4. Find all students whose name starts with 'S' or ends with 'a'.    ║
   ║  5. Find students whose email contains 'kumar' or 'reddy'.             ║
   ╚══════════════════════════════════════════════════════════════════════════╝

   ╔══════════════════════════════════════════════════════════════════════════╗
   ║  EXERCISE SET 3 — NULL, ORDER BY, LIMIT, ALIASES                        ║
   ╠══════════════════════════════════════════════════════════════════════════╣
   ║  1. List all students who have NOT paid any fees (fees_paid is NULL).  ║
   ║  2. Get the top 5 students ordered by fees paid (highest first).       ║
   ║  3. Show page 2 (students 6–10) sorted alphabetically by name.        ║
   ║  4. Display name as "Full Name", fees_paid as "Amount Paid".          ║
   ║  5. Find the most recently submitted assignment.                       ║
   ╚══════════════════════════════════════════════════════════════════════════╝

   ╔══════════════════════════════════════════════════════════════════════════╗
   ║  EXERCISE SET 4 — GROUP BY, Aggregate Functions, HAVING                  ║
   ╠══════════════════════════════════════════════════════════════════════════╣
   ║  1. How many students are in each batch? Include total fees per batch.  ║
   ║  2. What is the average age of students per course?                    ║
   ║  3. Which city has the most students? Show top 3.                      ║
   ║  4. Find courses where the total fees collected is more than 1,50,000. ║
   ║  5. Which assignment topic hasn the lowest average score?               ║
   ║  6. Count how many students per course have paid above 40,000.         ║
   ║  7. Among active students, which courses have more than 4 students?    ║
   ║  8. Find payment modes used for amounts above 30,000 average.          ║
   ╚══════════════════════════════════════════════════════════════════════════╝
*/


-- ════════════════════════════════════════════════════════════════════════════════════════
--   QUICK REFERENCE CHEATSHEET
-- ════════════════════════════════════════════════════════════════════════════════════════
/*
┌────────────────────────────────────────────────────────────────────────────────────────┐
│  CLAUSE        │  PURPOSE                         │  RUNS AT STEP                      │
├────────────────┼──────────────────────────────────┼────────────────────────────────────┤
│  FROM          │  Identify the table(s)            │  1 — Always first                  │
│  WHERE         │  Filter ROWS before grouping      │  2 — No aggregates allowed here    │
│  GROUP BY      │  Collapse rows into groups        │  3                                 │
│  HAVING        │  Filter GROUPS after grouping     │  4 — Aggregates allowed here       │
│  SELECT        │  Choose columns / expressions     │  5                                 │
│  ORDER BY      │  Sort the final result            │  6 — Aliases work here             │
│  LIMIT/OFFSET  │  Restrict rows returned           │  7 — Always last                   │
└────────────────┴──────────────────────────────────┴────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────────────────┐
│  AGGREGATE FUNCTIONS                                                                    │
├────────────────┬────────────────────────────────────────────────────────────────────── │
│  COUNT(*)      │  Counts all rows including NULLs                                      │
│  COUNT(col)    │  Counts non-NULL values in column                                     │
│  SUM(col)      │  Adds up non-NULL numeric values                                      │
│  AVG(col)      │  Average of non-NULL numeric values                                   │
│  MIN(col)      │  Smallest value (works on numbers, dates, strings)                    │
│  MAX(col)      │  Largest value  (works on numbers, dates, strings)                    │
└────────────────┴────────────────────────────────────────────────────────────────────── │

┌────────────────────────────────────────────────────────────────────────────────────────┐
│  WHERE vs HAVING  — the most common exam question!                                      │
├─────────────────────────────────────┬──────────────────────────────────────────────────┤
│  WHERE                              │  HAVING                                           │
│  Filters individual ROWS            │  Filters GROUPS                                   │
│  Runs BEFORE GROUP BY               │  Runs AFTER GROUP BY                              │
│  Cannot use aggregate functions     │  Must use aggregate functions                     │
│  WHERE age > 20                     │  HAVING COUNT(*) > 5                              │
└─────────────────────────────────────┴──────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────────────────┐
│  NULL RULES  — remember these or bugs will haunt you!                                  │
├────────────────────────────────────────────────────────────────────────────────────────┤
│  ✘  NULL = NULL     → returns NULL  (not TRUE!)                                        │
│  ✘  NULL = 0        → returns NULL                                                     │
│  ✘  NULL + 5        → returns NULL                                                     │
│  ✔  IS NULL         → correct way to check for NULL                                    │
│  ✔  IS NOT NULL     → correct way to check for non-NULL                                │
│  ✔  IFNULL(col, 0)  → treat NULL as 0                                                  │
│  ✔  COALESCE(col,0) → return first non-null value                                      │
│  All aggregates (SUM, AVG, MIN, MAX, COUNT(col)) SKIP NULLs automatically!             │
└────────────────────────────────────────────────────────────────────────────────────────┘
*/

