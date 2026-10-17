# IFN636-121: complete rubric grading

FR-RUB-02 implements teacher grading under Epic IFN636-72. The branch is
`feature/IFN636-121-rubric-grading`, based on the locally available `origin/main`
at `f4dde14`. Each of IFN636-122 through IFN636-127 has one commit.

## Behavior and scope

Teachers grade a submission through its existing Submission Details page.
The page displays every rubric criterion, its description and weight, a required
mark and an optional comment. Marks may be zero and must be within 0–100 with
at most two decimal places. Every criterion must appear exactly once in a save.

An invalid save returns feedback and preserves all previously stored grades and
the final result. HTML responses retain the entered values for correction.
Valid saves update the same submission/criterion records and calculate the final
result. Editing only comments preserves the numerical result. Empty comments
clear previous comments. This story does not support partial grading drafts.

For published historical assessments without a rubric, the original manual mark
and general-feedback form remains available. For rubric assessments, that legacy
endpoint rejects attempts to overwrite the calculated result. Existing general
feedback is preserved separately from criterion comments.

Student rubric/criterion-result presentation belongs to IFN636-128. The existing
student results page continues to read `submissions.mark`, which now contains
the complete weighted result. IFN636-134's additional authorization scope has
not been started. Existing Teacher authentication and form CSRF checks are used.

## Design choices: Facade and Composition

The selected Design Pattern is **Facade**, named in the Week 6 lecture. The
selected OOP concept is **Composition**, named in the Week 5 lecture. These are
the choices already selected for the Epic; no separate pattern is imposed on
each Story.

`RubricGradingFacade` in `rubric/grading.py` is the backend entry point for
reviewing and saving grading. Its `save()` method coordinates:

1. Open the repository transaction and load the locked submission/rubric.
2. Construct a `SubmissionGrading` object and validate the complete input.
3. Store the criterion grades.
4. Calculate and store the submission result.
5. Commit the complete change or roll it back on an exception.

The route handles HTTP concerns (form/JSON input, CSRF, response status and
redirects). It does not implement weighting or issue SQL. The Facade is useful
here because a single teacher action crosses validation, criterion persistence
and result persistence. Both the HTML form and JSON endpoint use that entry
point and the same rules.

`SubmissionGrading` in `rubric/grading_models.py` constructs and owns a tuple of
immutable `CriterionGrade` objects. It checks their criterion IDs against the
submission's `AssessmentRubric` before any writes. Each child carries the owning
submission ID. This is Composition, matching the requirement that criterion
grading belongs to Submission. Story 1's `AssessmentRubric` similarly owns its
`RubricCriterion` objects.

The domain objects are plain Python objects: they do not depend on Flask or a
database connection. Tests can therefore exercise the exact arithmetic and
completeness rules independently of the interface.

## Data and transaction flow

`criterion_grades` has a primary key, a submission foreign key, a criterion
foreign key, `mark DECIMAL(5,2)` and nullable `comment TEXT`. A unique key on
`(submission_id, criterion_id)` means repeated saves update existing records.
The database also checks `0 <= mark <= 100`. The application verifies that every
criterion belongs to the submission's assessment, preventing cross-assessment
grading even when a foreign criterion ID exists.

The calculated final grade remains in the existing `submissions.mark` column.
No additional final-result column, Python dependency or environment variable is
needed. The `submissions.feedback` column is not replaced by criterion comments.

`db.grading_transaction()` first discovers the assessment ID, then locks the
assessment row and the submission row in that order. This matches the existing
submission upload transaction's lock order. It rechecks the submission after
locking, rejects Draft assessments and reads the current rubric with a locking
read. A waiting grading request therefore does not use an older MySQL snapshot
of the criterion configuration.

All criterion upserts and the result update use the same connection and
transaction. Validation happens before the first write. A failure during result
persistence rolls back the criterion changes as well. Once complete grading
stores even a zero result, the existing resubmission checks recognize the
non-null mark and reject resubmission.

## Calculation

For each criterion, the awarded mark is a percentage score within 0–100:

```text
final grade = sum(criterion mark × criterion weight / 100)
```

Example: Analysis has weight 40% and mark 80; Design has weight 60% and mark 90.
The result is `80 × 0.40 + 90 × 0.60 = 86.00`.
Changing Analysis to 50 gives `50 × 0.40 + 90 × 0.60 = 74.00`.

Calculations use `Decimal`. Individual weighted contributions are not rounded;
the final sum is rounded once to two decimal places using `ROUND_HALF_UP`.
For example, `0.01 × 50% + 0 × 50% = 0.005` becomes `0.01`.

## HTTP interface

`POST /teacher/submissions/<submission_id>/rubric-grading` accepts either:

- Form fields: repeated `criterion_id`, with corresponding `mark_<id>` and
  optional `comment_<id>`, plus `csrf_token`.
- JSON: an object containing `grades`, with a complete array of criterion IDs,
  marks and optional comments. Send the session's CSRF token in `X-CSRFToken`.

```json
{
  "grades": [
    {"criterion_id": 1, "mark": "80.00", "comment": "Clear reasoning."},
    {"criterion_id": 2, "mark": "90.00"}
  ]
}
```

Criterion IDs in this example are illustrative; use the assessment's actual IDs.
The submission ID always comes from the URL; row data cannot override it.

Successful form saves redirect (302) to the review page. Successful JSON saves
return 200 with `submission_id` and the formatted `final_grade`. Validation
errors return 400 (HTML for forms, field errors for JSON). A missing submission
returns 404. The existing Teacher decorator protects the route.

## AC and Subtask traceability

The supplied Story numbers its final calculation AC as another AC5. This guide
calls that final item AC6 to distinguish it from completeness validation.

| Requirement | Implementation | Verification |
|---|---|---|
| AC1: save marks and optional comments | Model, Facade, upsert, grading form | Complete-save, zero/100 boundary and reload cases |
| AC2: update marks and recalculate | Same composite key and atomic result update | Repeated-save, mark-update and recalculation cases |
| AC3: update comments | Existing grade's comment is replaced | Comment-only update and clear-comment cases |
| AC4: valid mark range | Domain validation and database CHECK | Invalid ranges, non-finite values and decimal precision |
| AC5: all criteria marked | Exact criterion set and duplicate checks | Missing, duplicate, unknown and foreign criterion cases |
| AC6: weighted result belongs to Submission | Decimal arithmetic and `submissions.mark` | Weighted examples, half-up boundary and rollback cases |

| Subtask | Scope |
|---|---|
| IFN636-122 | Criterion grade model, fresh-install schema and additive migration |
| IFN636-123 | Grading Facade and transactional create/update persistence |
| IFN636-124 | Complete-input validation and HTTP endpoint |
| IFN636-125 | Calculation, atomic result storage and legacy overwrite prevention |
| IFN636-126 | Existing Teacher submission review form integration |
| IFN636-127 | Automated checks, Postman compatibility, MySQL integration and guide |

## Verification (17 October 2026, Brisbane)

- Full local Pytest suite: **266 passed, 14 skipped**. This includes 69 new
  grading domain/route/transaction-double cases.
- The 14 skipped cases require an explicitly enabled disposable MySQL database;
  nine were added for this Story. They cover actual saves/updates, invalid saves,
  rollback, a foreign assessment's criterion and concurrent resubmission after
  zero grading. Local Docker's engine was unavailable.
- The existing CI MySQL 8.4 step already runs the expanded
  `tests/integration/test_rubric_mysql.py` file with `RUBRIC_MYSQL_TESTS=1`.
- A temporary browser preview used the real routes, templates and CSRF with
  in-memory database doubles. It confirmed 86.00 initial grading, unchanged
  result after a comment update, recalculation to 74.00 and required-mark browser
  validation. This did not connect to AWS or grade real submissions.
- Postman's zero-grade fixture now uses the rubric endpoint. A new Rubric
  grading folder checks invalid saves, a mark update, a comment update and
  reloaded values. Run the whole collection; the folder depends on Auth and
  Student / Attempt Limits setup. Full Postman execution still requires CI or
  a configured local MySQL/Postman environment.
- All seven JavaScript blocks in the six added/changed Postman requests passed
  a JavaScript syntax check. This does not replace Postman workspace lint or
  collection execution.

Run local tests:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest_cache/rubric-grading-tests
```

## Deployment and recovery

The current `main` CD deploys automatically after a push/merge to `main`, and
also supports manual dispatch. **Database migrations remain manual. Apply them
before merging code that will activate on either app server.**

1. Review the six Story commits and CI results. Back up the shared database.
2. Confirm Story 1's `IFN636-114_add_rubric_criteria.sql` migration has already
   been applied to that database. Do not rerun it if its table already exists.
3. Apply `database/migrations/IFN636-122_add_criterion_grades.sql` once, using a
   migration account permitted to create the table. Run the following from a
   Linux shell containing the reviewed migration file:

   ```bash
   mysql --host=DATABASE_HOST --user=MIGRATION_USER --password homework_portal \
     < database/migrations/IFN636-122_add_criterion_grades.sql
   ```

4. Verify `SHOW CREATE TABLE homework_portal.criterion_grades;` and its foreign
   keys. Do not run `database/homework-portal.sql` against existing data: the
   fresh-install script drops/recreates the database.
5. The user pushes the Story branch, reviews/merges the PR, and the team's CD
   activates the reviewed release on both application servers. No new `.env`
   settings or upload paths are needed.
6. On the deployed release, review a test submission with a published rubric,
   enter all marks, reload, edit a mark and edit only a comment. Confirm the
   stored total and both servers' behavior. Confirm invalid input preserves the
   earlier result and historical assessments still support manual grading.

If reverting the application, follow the existing release rollback procedure.
Keep the additive grade table and its records to preserve entered grading;
application rollback does not automatically restore database schema or data.

The previously reported AWS Assessment View 500 investigation is paused at the
user's request. This Story does not claim that production issue has been fixed,
and no production migration, deployment or Git push was performed here.

## Suggested report evidence

Capture `RubricGradingFacade.save()` coordinating the subsystem calls for Facade,
and `SubmissionGrading.__init__()` constructing `CriterionGrade` objects for
Composition. Pair those backend screenshots with the complete grading form,
the weighted result, a mark-update example and validation feedback. Explain
their connection to FR-RUB-02 rather than presenting the class names alone.
