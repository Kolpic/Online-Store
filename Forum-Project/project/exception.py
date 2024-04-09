class CustomError(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message

class WrongUserInputLogin(Exception):
    def __init__(self, message, redirect_url='/login'):
        super().__init__(message)
        self.message = message
        self.redirect_url = redirect_url

class WrongUserInputRegistration(Exception):
    def __init__(self, message, redirect_url='/registration'):
        super().__init__(message)
        self.message = message
        self.redirect_url = redirect_url

class WrongUserInputVerification(Exception):
    def __init__(self, message, redirect_url='/verify'):
        super().__init__(message)
        self.message = message
        self.redirect_url = redirect_url

class MethodNotAllowed(Exception):
    def __init__(self, message, redirect_url='/home'):
        super().__init__(message)
        self.message = message
        self.redirect_url = redirect_url