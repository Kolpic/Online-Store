class MethodNotAllowed(Exception):
    def __init__(self, message, redirect_url='/home'):
        super().__init__(message)
        self.message = message
        self.redirect_url = redirect_url

class WrongUserInputException(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message

class DevException(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message