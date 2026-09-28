from fastapi import HTTPException, status


def api_error(status_code: int, code: str, message: str, correlation_id: str = "n/a") -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message, "correlation_id": correlation_id}},
    )


def not_found(message: str, correlation_id: str = "n/a") -> HTTPException:
    return api_error(status.HTTP_404_NOT_FOUND, "NOT_FOUND", message, correlation_id)


def bad_request(message: str, correlation_id: str = "n/a") -> HTTPException:
    return api_error(status.HTTP_400_BAD_REQUEST, "BAD_REQUEST", message, correlation_id)


def conflict(message: str, correlation_id: str = "n/a") -> HTTPException:
    return api_error(status.HTTP_409_CONFLICT, "CONFLICT", message, correlation_id)
