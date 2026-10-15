"""
policies.py(IFN636-66): Strategy design pattern for block submission.Allows different deadline policies without changing controller layer.
"""
from abc import ABC, abstractmethod
from datetime import datetime

# Strategy Pattern :
# The Strategy pattern suggests that you take a class that does something specific in a lot of different ways and extract all of these algorithms into separate classes called strategies.

# Strategy Interface
class SubmissionPolicy(ABC):
    @abstractmethod
    def is_submission_allowed(self, current_time: datetime, due_date: datetime) -> bool:
        pass


# Concrete Strategies A : Late submission not allowed
class NotAllowLatePolicy(SubmissionPolicy):
    def is_submission_allowed(self, current_time: datetime, due_date: datetime) -> bool:
        if due_date is None:
            return True
        return current_time <= due_date

# Concrete Strategies B : Late submission allowed (return True)
class AllowLatePolicy(SubmissionPolicy):
    def is_submission_allowed(self, current_time: datetime, due_date: datetime) -> bool:
        return True


# Context Class
class SubmissionContext:
    def __init__(self, policy: SubmissionPolicy) -> None:
        self.policy = policy

    def set_policy(self, policy: SubmissionPolicy) -> None:
        self.policy = policy

    def validate_submission(self, current_time: datetime, due_date: datetime) -> bool:
        return self.policy.is_submission_allowed(current_time, due_date)

# Helper
def get_submission_policy(allow_late) -> SubmissionPolicy:
    if allow_late:
        return AllowLatePolicy()
    return NotAllowLatePolicy()