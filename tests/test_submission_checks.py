import pytest

from submission_checks import build_submission_check_chain


@pytest.mark.parametrize(
    "mark, max_attempts, attempt_count, expected",
    [
        # First submission is allowed
        (None, 3, 0, None),

        # Resubmission below the limit is allowed
        (None, 3, 2, None),

        # Reaching the limit blocks submission
        (None, 3, 3, ("Maximum submission limit reached", 403)),

        # Attempt count above the limit is also rejected
        (None, 3, 4, ("Maximum submission limit reached", 403)),

        # Unlimited submissions remain allowed
        (None, 0, 100, None),

        # Graded submissions cannot be resubmitted
        (85, 3, 1, ("Graded submissions cannot be resubmitted.", 403)),

        # Zero is a valid grade, not an ungraded submission
        (0, 3, 1, ("Graded submissions cannot be resubmitted.", 403)),

        # Graded rejection takes priority over attempt limit
        (85, 3, 3, ("Graded submissions cannot be resubmitted.", 403)),

        # Unlimited attempts do not override grading restrictions
        (0, 0, 5, ("Graded submissions cannot be resubmitted.", 403)),
    ],
)
def test_submission_check_chain(
    mark, max_attempts, attempt_count, expected
):
    chain = build_submission_check_chain()

    ctx = {
        "mark": mark,
        "max_attempts": max_attempts,
        "attempt_count": attempt_count,
    }

    assert chain.handle(ctx) == expected
