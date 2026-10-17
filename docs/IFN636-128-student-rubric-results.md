# IFN636-128: student rubric and completed results

FR-RUB-03 implements the student view under Epic IFN636-72. The branch is
`feature/IFN636-128-student-rubric-results`. It was initially created from Story
2's pushed `8dec7bd`. After Story 2 merged, the five unpublished Story 3 commits
were rebased onto `origin/main` at `a3469d8` on 18 October 2026. They correspond
to IFN636-129 through IFN636-133; the PR base is now `main`.

## Student behavior

The published assessment details page displays a read-only table containing
the actual saved criterion titles, descriptions and percentage weights. It has
no management controls, sample records, captions explaining the table or
read-only reminder text. Historical assessments without criteria do not display
an empty rubric panel. The existing route continues to reject unavailable and
non-Published assessments before reading their rubric.

On the student's Submission Details page, rubric marks, comments and the final
grade appear together only after grading is complete. Incomplete grading does
not produce a result table, hidden grading payload or partial criterion values.
The table contains the title, description, weight, awarded mark and optional
comment for each criterion, followed by the final grade. Empty comments remain
empty cells. Values are formatted to two decimal places.

The Student Results summary applies the same completeness rule. A complete
rubric result includes a link to the submission's criterion breakdown. A pending
rubric result does not expose the earlier stored total or general feedback.
The My Submissions and assessment pages receive submission metadata without
unverified grading fields.

Every page request reads the current saved result. Teacher mark updates therefore
show the new marks and recalculated total on the next student request. Comment
updates show the latest comment while retaining the same total. No independent
student-side calculation or cached copy of grading is introduced.

## Implementation and the selected design

The Story extends the existing **Facade** in `rubric/grading.py`; it does not add
a different Design Pattern. Routes call `published_rubric()`,
`student_submission()` or `student_results()` instead of implementing grade
visibility themselves. The Facade coordinates retrieval, domain validation and
construction of the safe student-facing record.

The existing **Composition** remains relevant: `AssessmentRubric` owns its
criteria, and `SubmissionGrading` constructs and owns the criterion grades for
one submission. The read path reuses these objects to verify the same rules as
teacher grading rather than duplicating mark/weight arithmetic in the template.

Files and responsibilities:

| File | Responsibility |
|---|---|
| `db.py` | Published-only rubric lookup and one-statement grading snapshot |
| `rubric/grading.py` | Completeness check and safe student projection |
| `views.py` | Connect existing student pages to the Facade |
| `templates/student_rubric.html` | Published rubric definition table |
| `templates/student_rubric_result.html` | Completed criterion marks/comments and final grade |
| `templates/student_results.html` | Consistent summary visibility and breakdown link |

## Backend visibility and consistency

`get_published_rubric_by_assessment()` filters the assessment ID and
`status = 'Published'` in SQL. A missing/unavailable assessment returns no rubric;
a historical published assessment with no criteria returns an empty rubric.

`get_student_grading_snapshots()` reads the stored submission result, assessment
status, rubric criteria, awarded marks, comments and grade count in one SQL
statement. Its student predicate uses the current student's ID; the detail page
also supplies the submission ID. The result summary loads all of that student's
grading snapshots in one query, avoiding a query for every result card.

The single statement ensures that criterion marks and their stored final grade
come from one database snapshot. It does not mix an earlier submission total
with newer criterion marks from another query.

The Facade removes unverified grading fields from a copy of the submission
record before preparing any student template context. Rubric grading is released
only if all of the following hold:

1. The assessment has been published (Published, Closed or Archived for an
   already-owned submission result).
2. Its rubric has valid required fields, valid weights and a total of 100%.
3. The number of stored grades matches the criterion count.
4. Every criterion appears exactly once and has a valid mark within 0–100.
5. The stored final grade exists, is finite and matches the weighted result.

Any failure returns metadata without the marks, comments, final result or raw
grade records. A zero mark or zero final grade is valid. Reading a result never
changes stored marks or repairs an inconsistent record by publishing it.

The calculation uses Story 2's `SubmissionGrading` and its existing `Decimal`
arithmetic with a single `ROUND_HALF_UP` operation at the end. This Story does
not introduce another calculation rule.

Historical assessments without a rubric retain manual results in Student
Results. Their general feedback is shown only once a mark has been stored.
Criterion-level comments remain separate from that legacy feedback.

## AC and Subtask mapping

| AC | Behavior | Verification |
|---|---|---|
| AC1–AC2 | Published title, description and weight displayed | Published definition and no-management-control cases |
| AC3 | Incomplete grading withheld by the backend | Partial marks, missing marks, stale/missing total and captured template contexts |
| AC4 | Complete grading displayed together | Teacher save followed by student detail and summary requests |
| AC5 | Latest marks and recalculated result displayed | Mark update followed by fresh student requests |
| AC6 | Latest optional comment with unchanged total | Comment update/clear followed by fresh student requests |

| Subtask | Commit scope |
|---|---|
| IFN636-129 | Retrieve published rubric definitions |
| IFN636-130 | Student assessment rubric table |
| IFN636-131 | Backend completeness check and response projection |
| IFN636-132 | Student completed-results table and summary link |
| IFN636-133 | Tests, Postman checks, compatibility fixtures and this guide |

## Verification (18 October 2026, Brisbane)

- Local suite: **302 passed, 18 skipped**. This adds 36 executable cases for
  student rendering, backend projections and database read boundaries.
- Tests capture the actual Jinja template contexts and assert that incomplete
  grading fields are absent, in addition to checking the HTML response. They
  cover the submission, assessment, result-summary and submission-list pages.
- Teacher saves, mark updates, comment updates/clears and zero grades are
  exercised through the real Flask routes with transactional database doubles.
- Repository tests verify published-only filtering, student/submission query
  parameters, one-statement snapshots, result grouping and resource cleanup.
- The 18 skipped cases require the opt-in disposable MySQL environment. Four
  new cases cover published/latest results, an intentionally incomplete stored
  result and unavailable definitions. The existing CI MySQL step runs the same
  expanded `tests/integration/test_rubric_mysql.py` file.
- Local Docker's engine is unavailable. Real MySQL execution, Postman workspace
  lint and full collection execution still require CI or a configured local
  environment. These are not claimed as locally passing.
- Four new Postman JavaScript blocks passed syntax checks. A pending-result
  request runs between initial submission and teacher grading. The Student
  rubric folder runs after the existing Rubric grading folder and checks the
  published definition, current student result and summary link. Run the entire
  collection so its prerequisite fixtures exist.

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest_cache/student-rubric-tests
```

Test fixture content stays inside tests/Postman. Production templates contain
only field labels and the teacher's saved criterion/grading values; no demo
rubric data is inserted or prefilled by the feature.

## Review, deployment and recovery

1. Review the five new commits against `origin/main` and use `main` as the PR
   base. Story 2 has already merged; only Story 3 changes should appear in this
   PR. The branch also includes the repeated-submission Postman test added to
   `main` before the rebase.
2. The user performs Git Push after review. No push or PR creation is performed
   automatically by this implementation.
3. **This Story requires no new migration**, but the shared database must already
   contain the tables from IFN636-114 and IFN636-122. Confirm both preceding
   migrations were applied before activating the application on either server.
   If either is missing, back up the database and apply the reviewed additive
   migrations in dependency order. Do not run the fresh-install schema against
   existing data: it drops and recreates the database.
4. Require the CI unit, real MySQL and Postman checks before merge. The current
   `main` CD deploys after a push/merge to `main`, and also supports manual
   dispatch. No new dependency, environment variable or upload path is required.
5. Verify a student's published rubric, an ungraded submission, a complete
   result, a teacher mark update and a comment-only update on the deployed
   release. Confirm the Results summary and both app servers behave consistently.
6. An application rollback uses the existing release procedure. This Story makes
   no schema changes and requires no data deletion or result recalculation.

The paused AWS Assessment View 500 issue remains outside this work. Production
data has not been changed. IFN636-134's additional NFR authorization work has not
started; the existing login/role/ownership checks continue to be used.
