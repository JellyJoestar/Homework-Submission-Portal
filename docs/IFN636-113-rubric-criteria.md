# IFN636-113: assessment rubric criteria

This story implements FR-RUB-01 under Epic IFN636-72. Teachers manage criteria
on Draft assessments and must configure a valid 100% rubric before publishing.
Criterion grading and student rubric/result views belong to the following stories.

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
