# IFN636-134: rubric and grading access control

NFR-RUB-01 completes the authorization scope under Epic IFN636-72. The branch is
`feature/IFN636-134-rubric-access-control`, based on `origin/main` at `d8d39d7`,
which contains all three FR Stories and the Student Results template fix.
IFN636-135 through IFN636-139 each have one commit.

## Authorization rules

| Request | Unauthenticated | Student | Teacher |
|---|---|---|---|
| Published rubric through student assessment details | Login redirect | Allowed | Student route rejected by existing role policy |
| Teacher rubric configuration/view | Login redirect | 403 | Allowed, with existing lifecycle and validation rules |
| Teacher submission review, download and preview | Login redirect | 403 | Allowed |
| Rubric grading or legacy mark/feedback write | Login redirect | 403 | Allowed, subject to validation and rubric rules |
| Student submission/grading detail and file preview | Login redirect | Own submission only; another owner's ID returns 404 | Student route rejected by existing role policy |
| Student submission list and result summary | Login redirect | Own records only | Student route rejected by existing role policy |

Teacher authorization follows the existing Teacher role. The schema has no
per-assessment teacher assignment relation; this Story does not invent a new
teacher ownership rule. Published assessment definitions remain visible to
authenticated Students through the existing student route.

## Audit findings and changes

### IFN636-135: authentication

The relevant routes already use `teacher_required` or `student_required`, both
of which apply Flask-Login's `login_required` before running the route body.
These controls were retained. New tests cover 19 concrete protected requests
and verify that anonymous requests stop before database access.

`auth.load_user()` previously converted a session user ID directly with `int()`.
Malformed stored identities could therefore raise an exception. It now rejects
non-string, non-ASCII, non-decimal and non-positive identities before lookup,
and handles integer conversion errors as an anonymous identity. Expired or
missing accounts and unsigned/tampered cookies are also checked by tests.

The login/session design is unchanged. Unauthorized browser requests continue
to redirect to `/login` (302), matching the existing application convention.

### IFN636-136: rubric configuration

The existing Teacher decorator already rejects Students before rubric lookup,
Draft-state checks or writes. No additional role layer was added solely to
duplicate that behavior. This Subtask adds HTTP regression tests for create,
edit, delete and publication requests, including a valid Student CSRF token,
forged role/user fields and headers, and an existing session whose database
role has changed. A positive Teacher case verifies that valid CSRF-protected
create/edit/delete operations still work.

### IFN636-137: grading and result writes

The rubric grading endpoint, legacy mark/feedback endpoint and Teacher review
routes already require the Teacher role. New tests send direct Student requests
using both form and JSON grading payloads, a valid Student CSRF token and forged
Teacher metadata. They verify 403 responses and unchanged criterion marks,
comments and submission results. An unknown submission ID does not bypass the
role check or expose whether protected grading exists.

These two Subtasks are test-focused because the existing role controls are
already correct. Teacher role checks remain at the HTTP request boundary;
trusted backend grading services remain usable independently of Flask requests.

### IFN636-138: submission ownership

Existing submission and grading queries already bind the authenticated Student
ID in SQL. Those predicates are retained. The read boundary now checks the
returned metadata's owner as well, so it does not rely solely on a caller having
used the correct repository lookup:

- `RubricGradingFacade.submission_metadata()` requires the authenticated Student
  ID and rejects a record with a different or missing owner.
- The submission-detail route maps an unavailable/unowned record to the same
  generic 404 response. Grade snapshots are not read for a foreign record.
- The student assessment page verifies ownership before exposing the latest
  submission's filename or link.
- The submission list and Results summary drop records belonging to another
  Student or lacking an owner before rendering.
- The student preview route verifies the owner before opening/rendering a file.

The Student ID comes from `current_user.id`; query parameters, headers and body
fields cannot substitute another identity. Teacher preview behavior is unchanged.

### IFN636-139: verification

The HTTP access matrix is checked against every route in the rubric and grading
Blueprints. New management routes therefore require explicit coverage. Tests
also check unsupported HTTP methods and method-override/role headers.

The existing **Facade** and **Composition** remain the selected design. The
Facade now enforces the ownership boundary on its Student read methods. The
grading domain objects and weighted-calculation rules are unchanged; this
Story introduces no extra Design Pattern requirement.

## AC traceability

| AC | Enforcement | Evidence |
|---|---|---|
| AC1: unauthenticated requests rejected without protected data | Existing login decorators; robust session ID loading | Anonymous route matrix, expired/invalid identity and cookie tests |
| AC2: Students cannot modify rubric configuration | Existing Teacher role decorator | Direct create/edit/delete/publication requests; unchanged records |
| AC3: Students cannot modify marks, comments or results | Teacher protection on both write endpoints | Valid-CSRF form/JSON/legacy attempts; unchanged complete grading |
| AC4: another Student's private submission/grading denied | SQL predicates, metadata checks, list filtering and preview guard | Two-Student detail/preview/list tests; unexpected foreign-row tests; bound-query checks |
| AC5: direct HTTP requests rejected independently of UI | Request-layer role checks before resource operations | Role/user/header spoofing, method checks, Postman and MySQL cases |

## Verification (18 October 2026, Brisbane)

- Full local suite: **372 passed, 25 skipped**. This Story adds 70 executable
  checks while retaining the existing functional suite.
- Tests use the real Flask routing/decorators, signed test sessions, real CSRF
  form tokens and domain logic with database doubles. Captured data and stored
  values are checked after rejected requests.
- The 25 skipped tests require the explicitly enabled disposable MySQL database.
  Seven new cases cover Student attempts against a Draft rubric, form/JSON/legacy
  grading writes, and a second Student reading a completed result or an existing
  PDF. The existing CI MySQL step runs the expanded integration test file.
- Local Docker's engine was unavailable. Real MySQL execution, Postman workspace
  lint and the full Postman collection still require CI or a configured local
  test environment; they are not claimed as locally passing.
- Twelve Postman requests were added under Rubric access control (order 4900,
  before Logout). The folder uses earlier Auth, Attempt Limits, Student 2 and
  completed grading fixtures, so run the complete collection.
- Student login now saves its own CSRF token for negative write tests. No token
  values are committed. Fifteen JavaScript blocks across the twelve new requests
  and the changed login request passed syntax checks.
- Postman checks anonymous denial, Student create/edit/delete and grading denial,
  cross-Student detail/file denial, and unchanged rubric/grading after rejection.

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest_cache/rubric-access-tests
```

The additional MySQL tests must run only against an explicitly configured
disposable test database:

```bash
RUBRIC_MYSQL_TESTS=1 python -m pytest -q tests/integration/test_rubric_mysql.py
```

## Deployment and review

1. Review the five commits against `main`, then the user performs the branch
   Push. This implementation does not push or merge automatically.
2. Require the CI unit, real MySQL and Postman checks before merging.
3. No new schema migration, dependency, environment variable or UI content is
   introduced. The existing IFN636-114 and IFN636-122 tables remain prerequisites.
4. The existing `main` CD deploys after merge and supports manual dispatch.
   Verify both application servers activate the reviewed revision.
5. In the deployed test workflow, check an anonymous request, a Student's direct
   management request, two distinct Students' own/foreign submission views and
   previews, and a legitimate Teacher operation. Verify denied writes leave
   stored data unchanged.

Application rollback follows the existing release process; no database rollback
or data deletion is required by this Story. Existing valid accounts and sessions
continue to work, with roles loaded from the account lookup on each request.

The checks establish these Flask application access rules. They do not certify
the running AWS proxy configuration. The repository's documented Nginx setup
proxies application routes rather than publicly serving uploaded submissions;
production verification must retain that access path.

The previously paused AWS Assessment View 500 investigation has not been resumed.
No production database, deployment or user grading was changed during this work.
