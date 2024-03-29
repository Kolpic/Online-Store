from project.main import app
from project.exception import WrongUserInputLogin, MethodNotAllowed, WrongUserInputRegistration, WrongUserInputVerification

from flask import render_template, request

@app.errorhandler(404)
def not_found(e):
    return render_template("404.html")

@app.errorhandler(500)
def server_error(e):
    return render_template("404.html")

@app.errorhandler(WrongUserInputLogin)
def login_error(e):
    return render_template("login_error.html", message=e.message)

@app.errorhandler(WrongUserInputRegistration)
def registration_error(e):
    return render_template("reistration_error.html", message=e.message)

@app.errorhandler(WrongUserInputVerification)
def verify_error(e):
    return render_template("verify_error.html", message=e.message)

# Thrown, when user typed email, not present in the database s
@app.errorhandler(TypeError)
def login_error(e):
    return render_template("login_error.html", message="Invalid email")

@app.errorhandler(MethodNotAllowed)
def method_not_allowed_exception(e):
    return render_template('method_not_allowed.html', message=e.message)