class UserRoleEnum(str):
    PATIENT = "patient"
    DOCTOR = "doctor"
    RECEPTIONIST = "receptionist"
    ADMIN = "admin"


class PriorityEnum(str):
    NORMAL = "normal"
    EMERGENCY = "emergency"


class StatusEnum(str):
    WAITING = "waiting"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class OpdTokenStatusEnum(str):
    WAITING = "waiting"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
