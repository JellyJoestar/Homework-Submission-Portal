# Homework Submission Portal

**Author:** Jui-Chia Hsieh  
**Unit:** IFN636 Software Life Cycle Management  
**Project:** Homework Submission Portal  
**Repository:** https://github.com/JellyJoestar/Homework-Submission-Portal  
**EC2 Instance:** Jonathan (`i-0d98c7f61213c0200`)  
**Deployment URL:** http://54.153.143.94/
(The final URL may differ due to insufficient elastic IP.)

---

## 1. Project Overview

The Homework Submission Portal is a Flask-based web application developed to provide a centralized assessment-management workflow for Teachers and Students.

The project addresses a fragmented assessment-management process by providing one system where Teachers can create and manage assessments, publish assessment information, receive Student submissions, review submitted work, and record marks and feedback. Students can use the same portal to view published assessments, access supporting resources, submit assessment work, check submission information, and view their final mark and Teacher feedback.

The application supports two main end-to-end workflows:

- **Workflow 1 - Assessment Release and Submission**
- **Workflow 2 - Review and Feedback**

The project was developed using Jira, SysML modeling, Figma, Git and GitHub, Flask, MySQL, and AWS EC2.

---

## 2. User Roles and Stakeholders

The project includes three main stakeholders:

- Teacher
- Student
- System Administrator

Only **Teacher** and **Student** are implemented as application user roles.

The **System Administrator** is a supporting technical stakeholder responsible for the deployment environment and application availability. A separate System Administrator application interface is outside the project scope.

### Teacher

The Teacher can:

- Create Draft assessments.
- View assessment details.
- Edit Draft assessments.
- Delete Draft assessments.
- Select the relevant Unit.
- Enter assessment descriptions.
- Define simple assessment criteria.
- Set assessment due dates.
- Upload supporting resources.
- Publish assessments.
- Close assessments.
- Archive assessments.
- View Student submissions.
- Open individual Student submissions.
- Download submitted files.
- Record marks.
- Record written feedback.
- Modify saved marks and feedback.

### Student

The Student can:

- View Published assessments.
- View assessment information.
- View criteria and due dates.
- View the associated Unit.
- Access supporting resources.
- Upload assessment submissions.
- View submission confirmation and status.
- Open submission details.
- View saved marks.
- View Teacher feedback.

---

## 3. Main Workflows

### Workflow 1 - Assessment Release and Submission

```text
Teacher
   ↓
Create Draft Assessment
   ↓
Enter Assessment Information
   ↓
Set Unit, Due Date and Criteria
   ↓
Upload Supporting Resource
   ↓
Publish Assessment
   ↓
Student
   ↓
View Published Assessment
   ↓
Access Supporting Resource
   ↓
Upload Assessment File
   ↓
System Validation
   ↓
Store Submission
   ↓
Display Submission Status
```

The Teacher creates an assessment in the Draft state and enters the required assessment information.

The Teacher can configure the Unit, description, criteria, due date, and supporting resources before publishing the assessment.

After the assessment becomes Published, the Student can access the assessment information and supporting resources. The Student can then upload a supported assessment file.

The system validates and stores the submission before displaying the submission status.

**Final verification: PASS**

---

### Workflow 2 - Review and Feedback

```text
Teacher
   ↓
View Student Submissions
   ↓
Open Submission
   ↓
Download Submitted Work
   ↓
Enter Mark and Feedback
   ↓
Save Result
   ↓
Student
   ↓
Open Related Submission
   ↓
View Final Mark and Feedback
```

The Teacher can open a Student submission, review the submitted file, and record a mark and written feedback.

The result is stored persistently in MySQL.

The Student can then open the related submission and view the saved mark and Teacher feedback.

**Final verification: PASS**

---

## 4. Assessment Lifecycle

The Assessment entity uses a controlled lifecycle:

```text
Draft
  ↓
Published
  ↓
Closed
  ↓
Archived
```

A Draft assessment can also be permanently deleted:

```text
Draft
  ↓
Deleted
```

### Draft

The Teacher can:

- Edit assessment information.
- Set the Unit.
- Set the due date.
- Define criteria.
- Add supporting resources.
- Delete the assessment.
- Publish the assessment.

### Published

Students can access the assessment and supporting resources and submit assessment work.

### Closed

The assessment is no longer in its active submission stage.

### Archived

The assessment has completed its active lifecycle and is retained as an archived record.

Deletion is restricted to the **Draft** state.

---

## 5. Functional Scope

The project uses the **Assessment** entity to demonstrate CRUD operations.

### Create

Teachers can create new Draft assessments.

### Read

Teachers can view assessments and their details.

Students can view assessments that are available to them according to the assessment lifecycle.

### Update

Teachers can update Draft assessment information and progress assessments through the supported lifecycle.

### Delete

Teachers can permanently delete an assessment only while it remains in the Draft state.

---

## 6. File Upload Support

Supporting resources and Student submissions support:

```text
PDF
DOCX
```

Maximum upload size:

```text
10 MB
```

Runtime upload directories:

```text
uploads/resources/
uploads/submissions/
```

The `uploads/` directory is excluded from Git version control.

---

## 7. Data Persistence

MySQL is used for persistent application data.

Persisted information includes:

- Units
- Assessments
- Assessment resources
- Student submissions
- Submission status
- Marks
- Feedback

Uploaded resource and submission files are stored in application upload directories.

The Flask application uses a dedicated MySQL application account instead of the MySQL root account.

---

## 8. Technology Stack

| Component | Technology |
|---|---|
| Programming Language | Python 3.12 |
| Application Runtime | Python 3.12.13 |
| Web Framework | Flask |
| Template Engine | Jinja2 |
| Frontend | HTML5 and CSS3 |
| Database | MySQL 8.4 |
| Database Connector | mysql-connector-python |
| Environment Configuration | python-dotenv |
| Production WSGI Server | Gunicorn 26.2.0 |
| Reverse Proxy | Nginx 1.28.3 |
| Server Operating System | Ubuntu 26.04 LTS |
| Cloud Platform | AWS EC2 |
| Version Control | Git |
| Repository Hosting | GitHub |
| Project Management | Jira |
| UI/UX Design | Figma |
| System Modeling | SysML / Draw.io |

---

## 9. Project Structure

```text
Homework-Submission-Portal/
│
├── app.py
├── db.py
├── views.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
│
├── database/
│   └── homework-portal.sql
│
├── static/
│   └── css/
│       └── style.css
│
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── assessment_details.html
│   ├── create_assessment.html
│   ├── edit_assessment.html
│   ├── teacher_assessments.html
│   ├── teacher_submissions.html
│   ├── teacher_submission_details.html
│   ├── student_assessments.html
│   ├── student_assessment_details.html
│   ├── student_submissions.html
│   └── student_submission_details.html
│
└── uploads/
    ├── resources/
    └── submissions/
```

The following local/runtime files are excluded from Git:

```text
.env
.venv/
.vscode/
__pycache__/
*.pyc
.DS_Store
uploads/
```

---

## 10. Environment Variables

The repository includes an `.env.example` file.

Create a private `.env` file before running the application.

Example:

```env
DB_HOST=localhost
DB_USER=your_database_user
DB_PASSWORD=your_database_password
DB_NAME=homework_portal_db
FLASK_SECRET_KEY=your_secure_secret_key
```

Do not commit the real `.env` file to GitHub.

The `.gitignore` file excludes `.env` from version control.

---

## 11. Local Development Setup

### Prerequisites

Install:

- Git
- Python 3.12
- MySQL

Clone the repository:

```bash
git clone https://github.com/JellyJoestar/Homework-Submission-Portal.git
cd Homework-Submission-Portal
```

Create a Python virtual environment:

```bash
python3.12 -m venv .venv
```

### Linux / macOS

Activate the virtual environment:

```bash
source .venv/bin/activate
```

### Windows PowerShell

Activate the virtual environment:

```powershell
.venv\Scripts\Activate.ps1
```

Install project dependencies:

```bash
pip install -r requirements.txt
```

---

## 12. MySQL Database Setup

Open MySQL:

```bash
mysql -u root -p
```

Create the application database:

```sql
CREATE DATABASE homework_portal_db;
```

Import the project schema:

```bash
mysql -u root -p homework_portal_db < database/homework-portal.sql
```

A dedicated MySQL application account should be created for the Flask application.

The account details should match the values stored in the private `.env` file.

The application should not use the MySQL root account for normal runtime database access.

---

## 13. Running the Application Locally

Activate the Python virtual environment and run:

```bash
python app.py
```

The Flask development server is intended for local development and testing only.

The Flask development server is **not** used as the public production server on AWS EC2.

---

## 14. Production Deployment Architecture

The AWS EC2 deployment uses the following structure:

```text
User Web Browser
       ↓
Public Internet
       ↓
AWS EC2
       ↓
Security Group
HTTP TCP/80
       ↓
Nginx
       ↓
Gunicorn
127.0.0.1:8000
       ↓
Flask Application
       ↓
MySQL
localhost
```

Nginx receives public HTTP requests and forwards them internally to Gunicorn.

Gunicorn runs the Flask application.

Flask handles the application workflow and communicates with MySQL for persistent data.

The public-facing production path is therefore:

```text
Nginx
→ Gunicorn
→ Flask
→ MySQL
```

---

## 15. AWS EC2 Environment

The application is deployed to:

```text
Instance Name: Jonathan
Instance ID: i-0d98c7f61213c0200
Region: ap-southeast-2
Operating System: Ubuntu 26.04 LTS
Application Runtime: Python 3.12.13
Database: MySQL 8.4
WSGI Server: Gunicorn 26.2.0
Reverse Proxy: Nginx 1.28.3
```

Instance profile:

```text
IFN636-EC2-Role
```

Subnet:

```text
aws-controltower-PublicSubnet1
```

Application path:

```text
/opt/Homework-Submission-Portal
```

Python virtual environment:

```text
/opt/Homework-Submission-Portal/.venv
```

The EC2 deployment follows the integrated GitHub:

```text
main
```

branch.

---

## 16. Public Application URL

Current deployment URL:

```text
http://54.153.143.94/
```

The EC2 instance uses an AWS auto-assigned Public IPv4 address rather than an Elastic IP.

The Public IPv4 address may change after an EC2 Stop → Start operation.

The current Public IPv4 address can be checked from:

```text
AWS Console
→ EC2
→ Instances
→ Jonathan
→ Instance Summary
→ Public IPv4 address
```

The deployment URL must be checked before the assessment marking window.

---

## 17. Gunicorn Configuration

Gunicorn runs from:

```text
/opt/Homework-Submission-Portal/.venv/bin/gunicorn
```

Internal bind address:

```text
127.0.0.1:8000
```

Gunicorn is not directly exposed to the public Internet.

The application is managed using the systemd service:

```text
homework-portal.service
```

Useful commands:

```bash
sudo systemctl status homework-portal
sudo systemctl restart homework-portal
sudo systemctl is-active homework-portal
sudo systemctl is-enabled homework-portal
```

---

## 18. Nginx Configuration

Nginx is the public-facing web server.

It listens on HTTP TCP/80 and forwards application traffic to Gunicorn:

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name _;

    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
    }
}
```

Useful commands:

```bash
sudo nginx -t
sudo systemctl status nginx
sudo systemctl restart nginx
sudo systemctl is-active nginx
sudo systemctl is-enabled nginx
```

---

## 19. Service Startup and Recovery

The production services are configured to start automatically.

| Service | Boot Status | Restart Policy |
|---|---|---|
| MySQL | Enabled | `on-failure` |
| Homework Portal / Gunicorn | Enabled | `always` |
| Nginx | Enabled | `on-failure` |

Service verification:

```bash
sudo systemctl is-active mysql
sudo systemctl is-active homework-portal
sudo systemctl is-active nginx
```

Expected result:

```text
active
active
active
```

Local HTTP verification:

```bash
curl -I http://127.0.0.1/
```

Expected result:

```text
HTTP/1.1 200 OK
Server: nginx
```

---

## 20. EC2 Recovery Verification

### EC2 Reboot Test

A full EC2 operating-system reboot was performed without manually restarting the application services.

Result:

```text
MySQL                         PASS
Homework Portal / Gunicorn    PASS
Nginx                         PASS
Public Application            PASS
```

**EC2 Reboot Recovery: PASS**

### EC2 Stop → Start Test

A complete EC2 Stop → Start test was also performed.

No application services were manually started after the EC2 instance returned to the Running state.

Result:

```text
MySQL                         PASS
Homework Portal / Gunicorn    PASS
Nginx                         PASS
Public Application            PASS
```

**EC2 Stop → Start Recovery: PASS**

---

## 21. Security and Configuration

Basic security hygiene is applied to the deployment.

### Secrets

Database credentials and the Flask secret key are stored in:

```text
.env
```

The real `.env` file is excluded from Git.

### Database Account

The Flask application uses a dedicated MySQL application account rather than the MySQL root account.

### Public Exposure

```text
Nginx        TCP/80       Public-facing web service
Gunicorn     TCP/8000     Internal only
Flask        TCP/5000     Development only
MySQL        TCP/3306     Internal only
```

Gunicorn listens only on:

```text
127.0.0.1:8000
```

MySQL is accessed locally by the Flask application and is not intended to be publicly exposed.

### Runtime Files

The following are excluded from Git:

```text
.env
uploads/
```

This prevents secrets and runtime-uploaded assessment files from entering the Git repository.

### EC2 Administration

AWS Systems Manager Session Manager is used to access and administer the EC2 instance.

The AWS course environment also applies IAM restrictions to some networking operations.

Security Group configuration must provide appropriate HTTP access to the application during the assessment marking window.

---

## 22. Manual Deployment Procedure

CI/CD is outside the project scope.

The application is deployed manually using the following process:

```text
Prepare EC2 Instance
        ↓
Install Python 3.12
        ↓
Create Python Virtual Environment
        ↓
Deploy GitHub Source Code
        ↓
Install Python Dependencies
        ↓
Install and Configure MySQL
        ↓
Import Database Schema
        ↓
Create Dedicated Database User
        ↓
Configure .env
        ↓
Prepare Upload Directories
        ↓
Configure Gunicorn
        ↓
Configure systemd Service
        ↓
Configure Nginx
        ↓
Verify Local HTTP Access
        ↓
Verify External HTTP Access
        ↓
Run End-to-End Workflow Tests
```

---

## 23. Updating the EC2 Deployment

Move to the deployed project:

```bash
cd /opt/Homework-Submission-Portal
```

Check the current Git branch and working tree:

```bash
git branch --show-current
git status --short
```

Fetch the latest GitHub information:

```bash
git fetch origin
```

Review incoming commits:

```bash
git log HEAD..origin/main --oneline
```

Review files that will change:

```bash
git diff --name-only HEAD..origin/main
```

Update the EC2 copy of `main`:

```bash
git pull --ff-only origin main
```

Restart the application service:

```bash
sudo systemctl restart homework-portal
```

Verify production services:

```bash
sudo systemctl is-active mysql
sudo systemctl is-active homework-portal
sudo systemctl is-active nginx
```

Verify HTTP locally:

```bash
curl -I http://127.0.0.1/
```

---

## 24. Version Control Workflow

The project uses Jira-linked incremental development.

```text
Jira Issue
   ↓
Feature / Task Branch
   ↓
Implementation
   ↓
Commit
   ↓
Push
   ↓
Pull Request
   ↓
Review
   ↓
Merge into main
   ↓
EC2 Deployment
   ↓
Verification
```

Feature branches and Pull Requests were used to keep implementation changes separate until they were reviewed and ready to merge.

The EC2 production environment uses the integrated `main` branch.

---

## 25. Core Jira Traceability

| Jira Issue | Scope |
|---|---|
| IFN636-16 | Draft assessment management |
| IFN636-17 | Assessment due date and simple criteria |
| IFN636-18 | Assessment lifecycle |
| IFN636-19 | Supporting resources |
| IFN636-20 | Student published-assessment access and resources |
| IFN636-21 | Student assessment submission |
| IFN636-22 | Teacher submission review |
| IFN636-23 | Teacher mark and feedback |
| IFN636-24 | Student result and feedback |
| IFN636-30 | Apply approved Figma UI framework |
| IFN636-34 | AWS EC2 deployment |
| IFN636-32 | Final end-to-end verification |
| IFN636-41 | Final README documentation |

The project traceability follows:

```text
Requirement
   ↓
Jira Story / Task
   ↓
SysML Design
   ↓
Figma / UI
   ↓
Git Branch
   ↓
Git Commit
   ↓
Pull Request
   ↓
main
   ↓
AWS EC2 Deployment
   ↓
Verification Evidence
```

---

## 26. Final Verification Status

### Workflow Verification

| Verification Item | Status |
|---|---|
| Workflow 1 - Assessment Release and Submission | PASS |
| Workflow 2 - Review and Feedback | PASS |
| Student final mark and feedback display | PASS |

### Application Verification

| Verification Item | Status |
|---|---|
| Teacher role access | PASS |
| Student role access | PASS |
| Draft assessment creation | PASS |
| Draft assessment editing | PASS |
| Draft assessment deletion | PASS |
| Assessment lifecycle | PASS |
| Assessment publication | PASS |
| Supporting resource handling | PASS |
| Student Published assessment access | PASS |
| Student file submission | PASS |
| Submission persistence | PASS |
| Teacher submission review | PASS |
| Teacher mark and feedback entry | PASS |
| Student mark and feedback view | PASS |
| MySQL persistence | PASS |
| Final Figma-based UI | PASS |

### Deployment Verification

| Verification Item | Status |
|---|---|
| EC2 instance running | PASS |
| Python 3.12 runtime | PASS |
| MySQL service | PASS |
| Flask-to-MySQL connection | PASS |
| Gunicorn service | PASS |
| Nginx reverse proxy | PASS |
| HTTP TCP/80 connectivity | PASS |
| External browser access | PASS |
| EC2 reboot recovery | PASS |
| EC2 Stop → Start recovery | PASS |

**Final End-to-End Verification: PASS**

---

## 27. Known Limitations

The Homework Submission Portal is an academic prototype with a deliberately bounded scope.

Current limitations include:

- The system uses role selection rather than a full authentication and account-management system.
- There is no separate System Administrator application interface.
- HTTPS/TLS is not currently configured.
- The EC2 instance uses an auto-assigned Public IPv4 address instead of an Elastic IP.
- Uploaded files are stored on the EC2 filesystem rather than managed object storage.
- Only PDF and DOCX files are supported.
- The application uses a simple Student submission model rather than multiple submission versions or submission history.
- Assessment criteria are simple and do not provide a weighted or nested rubric engine.
- Virus or malware scanning is not implemented.
- Email and push notifications are not implemented.
- Plagiarism detection is not implemented.
- Analytics and reporting dashboards are outside scope.
- Automated late penalties and complex deadline-extension workflows are outside scope.
- CI/CD is outside scope; deployment is performed manually.

These limitations reflect the defined project scope rather than unresolved defects in the verified core workflows.

---

## 28. Final Project Status

| Project Area | Status |
|---|---|
| Requirements | Completed |
| System Design | Completed |
| Low-Fidelity UI Design | Completed |
| Figma Prototype | Completed |
| Core Application Implementation | Completed |
| Assessment CRUD | Completed |
| Workflow 1 | PASS |
| Workflow 2 | PASS |
| MySQL Persistence | Completed |
| Git/GitHub Integration | Completed |
| Final Figma UI Implementation | Completed |
| AWS EC2 Deployment | Completed |
| Service Startup and Recovery | PASS |
| Final End-to-End Verification | PASS |
| README Documentation | Completed |

---

## 29. Summary

The Homework Submission Portal demonstrates an end-to-end software development lifecycle:

```text
Problem and Requirements
        ↓
Jira Project Management
        ↓
SysML System Design
        ↓
Low-Fidelity UI Design
        ↓
Figma Prototype
        ↓
Flask Application Development
        ↓
MySQL Persistence
        ↓
Git and GitHub Version Control
        ↓
AWS EC2 Deployment
        ↓
Nginx and Gunicorn Production Hosting
        ↓
End-to-End Verification
```

The final deployed production architecture is:

```text
Nginx
→ Gunicorn
→ Flask
→ MySQL
```

Both required Teacher and Student workflows have been successfully implemented, deployed to AWS EC2, and verified through the deployed application.

**Workflow 1 - Assessment Release and Submission: PASS**

**Workflow 2 - Review and Feedback: PASS**

**Final End-to-End Verification: PASS**
