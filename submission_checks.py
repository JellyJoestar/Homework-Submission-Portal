class SubmissionCheck:
    """Base handler for the submission validation chain."""

    def __init__(self, next_check=None):
        self.next_check = next_check

    def handle(self, ctx):
        if self.next_check is not None:
            return self.next_check.handle(ctx)
        return None


class GradedCheck(SubmissionCheck):
    """Reject resubmission if the submission has been graded."""

    def handle(self, ctx):
        if ctx["mark"] is not None:
            return "Graded submissions cannot be resubmitted.", 403

        return super().handle(ctx)


class AttemptLimitCheck(SubmissionCheck):
    """Reject submissions that have reached their allowed limit."""

    def handle(self, ctx):
        max_attempts = ctx["max_attempts"]
        attempt_count = ctx["attempt_count"]

        if max_attempts != 0 and attempt_count >= max_attempts:
            return "Maximum submission limit reached", 403

        return super().handle(ctx)


def build_submission_check_chain():
    """Build the validation chain in the required order."""
    return GradedCheck(AttemptLimitCheck())
