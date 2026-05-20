from fastapi import HTTPException, status

class APIException(HTTPException):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(status_code=status_code, detail=detail)

class AuthenticationException(APIException):
    pass

class ValidationErrorException(APIException):
    pass

class NotFoundException(APIException):
    pass

class PermissionDeniedException(APIException):
    pass

def raise_api_exception(status_code: int, detail: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail=detail)

def raise_not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=404, detail=detail)

def raise_unauthorized(detail: str) -> HTTPException:
    return HTTPException(status_code=401, detail=detail)

def raise_forbidden(detail: str) -> HTTPException:
    return HTTPException(status_code=403, detail=detail)