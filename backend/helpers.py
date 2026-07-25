"""Shared helpers used across API blueprints."""


def error_response(code: str, message: str, fields: dict | None = None, status: int = 422):
    """Builds the single error envelope used by every endpoint (White Paper §10.2):

        {"error": {"code": "VALIDATION_ERROR", "message": "...", "fields": {"reps": "1-100"}}}
    """
    body = {"error": {"code": code, "message": message}}
    if fields:
        body["error"]["fields"] = fields
    return body, status
