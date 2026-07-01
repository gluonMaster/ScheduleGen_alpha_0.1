class ScheduleStateError(RuntimeError):
    def __init__(self, message: str, code: str, status_code: int = 409):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code

    def to_payload(self) -> dict:
        return {"ok": False, "error": self.message, "code": self.code}


class ScheduleStateReadError(ScheduleStateError):
    pass


class OccupancyUnavailable(ScheduleStateError):
    def __init__(self, message: str = "Occupancy snapshot is unavailable"):
        super().__init__(message, "OCCUPANCY_UNAVAILABLE", status_code=503)
