from app.core.database import Base  # noqa
from app.models.category import Category  # noqa
from app.models.hanzi import Hanzi, StructureType, VariantType, LevelType  # noqa
from app.models.hanzi_dictionary import HanziDictionary, HanziDataset, HanziDatasetItem  # noqa
from app.models.user import User, UserRole  # noqa
from app.models.teacher import Teacher  # noqa
from app.models.student import Student  # noqa
from app.models.student_class import StudentClass, StudentClassStatus  # noqa
from app.models.assignment import Assignment, AssignmentStatus  # noqa
from app.models.ai_chat import AIChatConversation, AIChatMemoryFact, AIChatMessage  # noqa
from app.models.assignment_attachment_upload import AssignmentAttachmentUpload  # noqa
from app.models.assignment_reminder import (  # noqa
    AssignmentReminderExecution,
    AssignmentReminderExecutionStatus,
    AssignmentReminderPlan,
    AssignmentReminderPlanStatus,
)
from app.models.submission import Submission, SubmissionStatus  # noqa
from app.models.comment import Comment, TargetType  # noqa
from app.models.comment_like import CommentLike  # noqa
from app.models.course import Course, CourseStatus  # noqa
from app.models.custom_field import (  # noqa
    CustomFieldTargetType,
    CustomFieldType,
    ManagementSystemCustomField,
    ManagementSystemCustomFieldValue,
)
from app.models.message import Message  # noqa
from app.models.event_outbox import EventOutbox  # noqa
from app.models.management_system import ManagementSystem, ManagementSystemAccessRole, UserManagementSystem  # noqa
from app.models.management_system_record import ManagementSystemRecord  # noqa
from app.models.teaching_class import (  # noqa
    TeachingClass,
    TeachingClassJoinToken,
    TeachingClassJoinTokenStatus,
    TeachingClassMember,
    TeachingClassMemberStatus,
    TeachingClassStatus,
)
