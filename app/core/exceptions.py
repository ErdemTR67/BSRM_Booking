from uuid import UUID


class ApplicationError(Exception):
    code = "application_error"
    default_message = "The operation could not be completed."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.default_message)


class ResourceNotFoundError(ApplicationError):
    pass


class ConflictError(ApplicationError):
    pass


class AuthenticationError(ApplicationError):
    pass


class AuthorizationError(ApplicationError):
    pass


class PersistenceError(ApplicationError):
    code = "persistence_error"
    default_message = "The data could not be saved."


class ServiceUnavailableError(ApplicationError):
    code = "service_unavailable"
    default_message = "The service is temporarily unavailable."


class TooManyRequestsError(ApplicationError):
    code = "rate_limit_exceeded"
    default_message = "Too many requests. Please try again later."

    def __init__(self, retry_after: int) -> None:
        super().__init__()
        self.retry_after = retry_after


class InvalidCredentialsError(AuthenticationError):
    code = "invalid_credentials"
    default_message = "Invalid email or password."


class InvalidAccessTokenError(AuthenticationError):
    code = "invalid_access_token"
    default_message = "Could not validate credentials."


class InvalidRefreshTokenError(AuthenticationError):
    code = "invalid_refresh_token"
    default_message = "Invalid, expired, or revoked refresh token."


class RefreshTokenPersistenceError(PersistenceError):
    code = "refresh_token_persistence_error"
    default_message = "The authentication session could not be saved."


class InactiveUserError(AuthorizationError):
    code = "inactive_user"
    default_message = "User is inactive."

    def __init__(self, user_id: UUID | None = None) -> None:
        super().__init__()
        self.user_id = user_id


class InsufficientPermissionsError(AuthorizationError):
    code = "insufficient_permissions"
    default_message = "You do not have permission to perform this action."


class InvalidInvitationError(AuthenticationError):
    code = "invalid_invitation"
    default_message = "The invitation is invalid, expired, revoked, or already used."


class InvitationAccountExistsError(ConflictError):
    code = "invitation_account_exists"
    default_message = "An account already exists for this invitation email. Sign in to accept it."


class InvitationNotFoundError(ResourceNotFoundError):
    code = "invitation_not_found"
    default_message = "Invitation not found."

    def __init__(self, invitation_id: UUID | None = None) -> None:
        super().__init__()
        self.invitation_id = invitation_id


class InvitationPersistenceError(PersistenceError):
    code = "invitation_persistence_error"
    default_message = "The invitation could not be saved."


class InvitationAlreadyResolvedError(ConflictError):
    code = "invitation_already_resolved"
    default_message = "The invitation has already been accepted or revoked."


class InvitationDeliveryError(ServiceUnavailableError):
    code = "invitation_delivery_error"
    default_message = "The invitation was created but the email could not be delivered."


class UserEmailAlreadyExistsError(ConflictError):
    code = "user_email_already_exists"
    default_message = "A user with this email already exists."

    def __init__(self, email: str) -> None:
        super().__init__()
        self.email = email


class UserNotFoundError(ResourceNotFoundError):
    code = "user_not_found"
    default_message = "User not found."

    def __init__(self, user_id: UUID | None = None) -> None:
        super().__init__()
        self.user_id = user_id


class UserPersistenceError(PersistenceError):
    code = "user_persistence_error"
    default_message = "The user could not be saved."


class TenantAlreadyExistsError(ConflictError):
    code = "tenant_already_exists"
    default_message = "A tenant with this slug already exists."

    def __init__(self, slug: str) -> None:
        super().__init__()
        self.slug = slug


class TenantNotFoundError(ResourceNotFoundError):
    code = "tenant_not_found"
    default_message = "Tenant not found."

    def __init__(self, tenant_id: UUID) -> None:
        super().__init__()
        self.tenant_id = tenant_id


class TenantPersistenceError(PersistenceError):
    code = "tenant_persistence_error"
    default_message = "The tenant could not be saved."


class LocationSlugAlreadyExistsError(ConflictError):
    code = "location_slug_already_exists"
    default_message = "A location with this slug already exists."

    def __init__(self, slug: str) -> None:
        super().__init__()
        self.slug = slug


class LocationNotFoundError(ResourceNotFoundError):
    code = "location_not_found"
    default_message = "Location not found."

    def __init__(self, location_id: UUID) -> None:
        super().__init__()
        self.location_id = location_id


class LocationPersistenceError(PersistenceError):
    code = "location_persistence_error"
    default_message = "The location could not be saved."


class EmployeeNotFoundError(ResourceNotFoundError):
    code = "employee_not_found"
    default_message = "Employee not found."

    def __init__(self, employee_id: UUID) -> None:
        super().__init__()
        self.employee_id = employee_id


class EmployeePersistenceError(PersistenceError):
    code = "employee_persistence_error"
    default_message = "The employee could not be saved."


class ServiceNotFoundError(ResourceNotFoundError):
    code = "service_not_found"
    default_message = "Service not found."

    def __init__(self, service_id: UUID) -> None:
        super().__init__()
        self.service_id = service_id


class ServicePersistenceError(PersistenceError):
    code = "service_persistence_error"
    default_message = "The service could not be saved."


class EmployeeServiceNotFoundError(ResourceNotFoundError):
    code = "employee_service_not_found"
    default_message = "Employee service association not found."


class EmployeeServicePersistenceError(PersistenceError):
    code = "employee_service_persistence_error"
    default_message = "The employee service association could not be saved."


class OpeningHourNotFoundError(ResourceNotFoundError):
    code = "opening_hour_not_found"
    default_message = "Opening hour not found."

    def __init__(self, opening_hour_id: UUID) -> None:
        super().__init__()
        self.opening_hour_id = opening_hour_id


class OpeningHourPersistenceError(PersistenceError):
    code = "opening_hour_persistence_error"
    default_message = "The opening hour could not be saved."


class LocationClosureNotFoundError(ResourceNotFoundError):
    code = "location_closure_not_found"
    default_message = "Location closure not found."

    def __init__(self, closure_id: UUID) -> None:
        super().__init__()
        self.closure_id = closure_id


class LocationClosurePersistenceError(PersistenceError):
    code = "location_closure_persistence_error"
    default_message = "The location closure could not be saved."


class EmployeeAvailabilityNotFoundError(ResourceNotFoundError):
    code = "employee_availability_not_found"
    default_message = "Employee availability not found."

    def __init__(self, availability_id: UUID) -> None:
        super().__init__()
        self.availability_id = availability_id


class EmployeeAvailabilityPersistenceError(PersistenceError):
    code = "employee_availability_persistence_error"
    default_message = "The employee availability could not be saved."


class TimeOffNotFoundError(ResourceNotFoundError):
    code = "time_off_not_found"
    default_message = "Time off not found."

    def __init__(self, time_off_id: UUID) -> None:
        super().__init__()
        self.time_off_id = time_off_id


class TimeOffPersistenceError(PersistenceError):
    code = "time_off_persistence_error"
    default_message = "The time off could not be saved."


class CustomerNotFoundError(ResourceNotFoundError):
    code = "customer_not_found"
    default_message = "Customer not found."

    def __init__(self, customer_id: UUID) -> None:
        super().__init__()
        self.customer_id = customer_id


class CustomerPersistenceError(PersistenceError):
    code = "customer_persistence_error"
    default_message = "The customer could not be saved."


class AvailabilityCalculationError(ApplicationError):
    code = "availability_calculation_error"
    default_message = "Availability could not be calculated."


class AppointmentNotFoundError(ResourceNotFoundError):
    code = "appointment_not_found"
    default_message = "Appointment not found."

    def __init__(self, appointment_id: UUID) -> None:
        super().__init__()
        self.appointment_id = appointment_id


class AppointmentConflictError(ConflictError):
    code = "appointment_conflict"
    default_message = "The requested appointment time is not available."


class InvalidAppointmentTransitionError(ConflictError):
    code = "invalid_appointment_transition"
    default_message = "The appointment status transition is not allowed."

    def __init__(self, current_status: str, target_status: str) -> None:
        super().__init__()
        self.current_status = current_status
        self.target_status = target_status


class AppointmentPersistenceError(PersistenceError):
    code = "appointment_persistence_error"
    default_message = "The appointment could not be saved."


class BookingSiteNotFoundError(ResourceNotFoundError):
    code = "booking_site_not_found"
    default_message = "Booking site not found."


class BookingSiteAlreadyExistsError(ConflictError):
    code = "booking_site_already_exists"
    default_message = "A booking site already exists for this tenant."


class BookingSitePersistenceError(PersistenceError):
    code = "booking_site_persistence_error"
    default_message = "The booking site configuration could not be saved."


class PublicBookingOriginError(AuthorizationError):
    code = "origin_not_allowed"
    default_message = "This origin is not allowed to use the booking site."


class PublicBookingChallengeError(AuthorizationError):
    code = "invalid_challenge"
    default_message = "The anti-abuse challenge is invalid or expired."


class PublicBookingIdempotencyConflictError(ConflictError):
    code = "idempotency_conflict"
    default_message = "This idempotency key was already used for a different request."


class PublicBookingResourceNotFoundError(ResourceNotFoundError):
    code = "public_resource_not_found"
    default_message = "The requested booking resource was not found."
