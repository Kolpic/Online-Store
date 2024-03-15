class CustomError(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message

class WrongUserInputLogin(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message
class WrongUserInputRegistration(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message

class WrongUserInputVerification(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message

class MethodNotAllowed(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message