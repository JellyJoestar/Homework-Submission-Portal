# IFN636-113: assessment rubric criteria

This story implements FR-RUB-01 under Epic IFN636-72. Teachers manage criteria
on Draft assessments and must configure a valid 100% rubric before publishing.
Criterion grading and student rubric/result views belong to the following stories.

## Local verification (17 October 2026)

- Normal Pytest suite: 179 passed, 5 opt-in MySQL cases skipped.
- Postman JavaScript syntax: 87 script blocks checked across 82 requests. The
  collection itself was not executed locally; the CI API job runs it with MySQL.
- Browser checks used temporary in-memory assessment data with the real Flask
  routes/templates and CSRF forms: add, edit, reject publication at 40%, publish
  at 100%, and display the published rubric read-only.
- The local Docker engine was unavailable, so real MySQL persistence/concurrency
  remains to be confirmed by the configured CI integration step or an explicitly
  configured disposable MySQL environment.
- The branch starts from local `main` at `bc5d43f`; remote fetch was not performed.
  No source was pushed and no production deployment/migration was performed.

### PR integration follow-up: late-allowed assessment

The late-allowed submission scenario from IFN636-73 publishes a separate
assessment. It also needs a valid rubric before publication. The Postman request
`Teacher / Prepare late allowed assessment rubric` adds a 100% criterion at
order 7450, after finding that assessment (7400) and before publishing it (7500).
The assessment ID, teacher session and teacher CSRF token are reused from the
existing setup. Application validation and submission behavior are unchanged.

Local follow-up verification: 179 Pytest cases passed, with 5 opt-in MySQL cases
skipped. A temporary check used the new request's URL/form fields with actual
Flask routes, CSRF enabled and in-memory persistence: publication without a
rubric returned 400, rubric setup and publication returned 302, and an allowed
late student submission followed its redirect to a 200 confirmation page.
Request ordering was checked against the locally cached IFN636-73 requests.
The full merged Postman collection and its late-status badge assertion still
require CI verification; neither Postman CLI nor a running MySQL environment
was available locally.

## Database update (IFN636-114)

Each row in `rubric_criteria` belongs to one assessment and contains a title,
description and percentage weight. Weights have at most two decimal places.
Deleting a Draft assessment also removes its criteria through the foreign key.
The original `assessments.criteria` text column remains intact for existing data.

For an existing database, apply the additive migration once, using the actual
database host and an account permitted to create tables:

```sh
mysql --host=DATABASE_HOST --user=MIGRATION_USER --password homework_portal < database/migrations/IFN636-114_add_rubric_criteria.sql
```

Run this against the shared database once, before activating the new release on
either application server. The password is requested interactively.

`database/homework-portal.sql` includes the same table for a fresh development or
CI database. That script drops and recreates the database; use the migration for
an existing database with data.

The migration does not manufacture criteria for existing assessments or change
previously published assessments, submissions, marks or feedback.

## Object design and implementation

`rubric/models.py` implements Composition using `AssessmentRubric` and
`RubricCriterion`. A rubric creates its own criterion objects from its database
rows and controls adding, replacing and removing them. Each criterion belongs
to the same assessment as its owner. Removing one leaves the other criteria
unchanged. Callers receive a tuple of immutable criterion objects.

`RubricCriterion` trims and validates its title and description, accepts a finite
weight greater than zero and at most 100, and rejects values needing more than
two decimal places. It uses `Decimal` for exact decimal totals. A Draft rubric
may temporarily total less or more than 100 while the Teacher edits it.
`AssessmentRubric.validate_for_publication()` requires at least one valid
criterion and an exact total of `100.00`.

Composition fits the Epic's ownership rule: rubric definitions belong to an
assessment. It also provides one place to keep criteria associated with their
owner and validate the combined rubric. The later grading story will apply the
same idea to Submission Grading and its Criterion Grades.

The selected Design Pattern for the Epic is Facade. Its main grading entry point
will be implemented in IFN636-121, where it coordinates validation, calculation
and persistence. This story establishes Composition and rubric-definition rules;
it does not claim that the grading Facade or the other stories are complete.

## Request and persistence flow

The existing Teacher Assessment Details page displays the rubric table, total
weight and add form. Each row has edit/remove actions while the assessment is
Draft. Form errors retain the entered values. Published, Closed and Archived
assessments display the same rubric without management controls.

The new `rubric` Blueprint provides:

| Method | Route | Purpose |
|---|---|---|
| POST | `/teacher/assessments/<assessment_id>/rubric` | Add a criterion |
| GET/POST | `/teacher/assessments/<assessment_id>/rubric/<criterion_id>/edit` | Show and save edits |
| POST | `/teacher/assessments/<assessment_id>/rubric/<criterion_id>/delete` | Remove one criterion |

Routes reuse the existing `teacher_required` authentication/role check. The new
forms use the project's Flask-WTF CSRF support. Publication keeps its existing
URL and delegates to `publish_assessment_with_rubric()`.

All rubric writes and publication use `_rubric_transaction()` in `db.py`:

1. Open a transaction and lock the parent assessment with `SELECT ... FOR UPDATE`.
2. Recheck that it exists and is still Draft, then load its criteria.
3. Apply domain validation and execute a scoped SQL change.
4. Commit on success; roll back on failure and close the connection.

Update/delete operations check both the criterion ID and assessment ID. The
shared parent lock ensures that rubric edits and publication cannot race across
the two application servers. In particular, publication validates the rubric
after obtaining the lock. Routes return 400 for invalid input/state and 404 for
missing assessments or criteria belonging to another assessment.

The original free-text `assessments.criteria` value remains stored and is labeled
Assessment Guidance in the existing forms/pages. The structured rubric is the
publication grading structure. Already-published records without criteria remain
unchanged and read-only; this migration does not reopen or backfill them.

## Validation and AC traceability

| AC | Evidence |
|---|---|
| 1 | Create route, owned criterion objects, INSERT scoped to assessment |
| 2 | Edit form, immutable replacement preserving both IDs, scoped UPDATE |
| 3 | Scoped removal and preservation of other criteria |
| 4 | Required title/description/weight, rejected saves with form feedback |
| 5 | Decimal validation, finite values, `0 < weight <= 100`, two decimal places |
| 6 | Nonempty 100% rubric validation inside the publication transaction |
| 7 | Read-only page plus Draft recheck inside every database write transaction |

Tests are split by boundary:

- `tests/test_rubric_models.py`: Composition, field validation and exact totals.
- `tests/test_rubric_configuration.py`: Teacher forms, feedback and publication.
- `tests/test_rubric_database.py`: scoped SQL, locking, rollback and cleanup.
- `tests/integration/test_rubric_mysql.py`: opt-in real MySQL CRUD, rejected
  writes, publication, association checks and concurrent edit/publication.

Run the normal suite from the repository's virtual environment:

```sh
python -m pytest -q
```

The five real MySQL cases are skipped unless `RUBRIC_MYSQL_TESTS=1` is explicitly
set for a disposable database configured through `DB_HOST`, `DB_PORT`, `DB_NAME`,
`DB_USER` and `DB_PASSWORD`. The existing CI API job loads an isolated MySQL 8.4
database, runs these cases, then starts Flask and runs Postman.

```sh
RUBRIC_MYSQL_TESTS=1 python -m pytest -q tests/integration/test_rubric_mysql.py
```

Postman's teacher login also saves `teacher_csrf_token`. Six scenario setup
requests now create a 100% rubric before their existing publish requests, so the
file-preview, attempt-limit and late-submission workflows remain valid. Run Auth
first, as required by the existing collection.

## Deployment of this story

1. Review the six local Subtask commits and run the tests. Push/review/merge using
   the team's normal workflow; the implementation does not push automatically.
2. Back up the existing shared database. Apply the additive IFN636-114 migration
   once before either application server starts serving the new code. It is
   compatible with the previous application version, so it can be applied before
   a merge that triggers deployment.
3. Deploy the reviewed revision through the team's release workflow. In this
   branch's base, `.github/workflows/cd.yml` uses `workflow_dispatch` on `main`:
   open GitHub Actions, select the two-runner source deployment workflow, and run
   it for `main`. If other reviewed CD changes have since added automatic
   deployment, use that updated team's workflow after the migration is applied.
4. Confirm both application servers activated the expected release. No new Python
   dependencies, upload-storage paths or environment variables are required by
   the feature itself.
5. As Teacher, open a Draft, add 40% and 60% criteria, edit and remove a criterion,
   and verify an incomplete total cannot publish. Restore 100%, publish, and
   confirm the rubric is read-only and direct edit/remove requests are rejected.
6. Check the other submission, preview and attempt-limit flows. Their assessments
   now need valid rubrics before publication too.

For local development, apply the migration to the development database, retain
the existing `.env` settings, activate `.venv`, and run `python app.py`.

If an application rollback is needed, reactivate the previous known-good release
using the team's release procedure. The additive rubric table can remain in place
to preserve entered definitions. Do not drop it as part of an application rollback.

## Review and report evidence

Suggested code screenshots are `AssessmentRubric` creating/managing criteria,
`RubricCriterion` validating a weight, and `_rubric_transaction()` together with
`publish_assessment_with_rubric()`. Pair these with the Teacher rubric form,
invalid-publication feedback and the published read-only table. Label the OOP
evidence as Composition. Capture the Facade evidence after IFN636-121 implements
the actual grading coordinator.
