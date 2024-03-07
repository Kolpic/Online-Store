from unittest.mock import patch
from flask import url_for

def test_home_get_successful(client):
    with patch('project.main.is_authenticated', return_value=True):
        responce = client.get('/home')

        assert responce.status_code == 200
        assert b"Welcome to Our Application!" in responce.data

def test_home_get_unsuccessful(client):
    with patch('project.main.is_authenticated', return_value=False):
        responce = client.get('/home', follow_redirects=True)

    assert responce.status_code == 200
    assert responce.request.path == url_for('login')
    assert b"Login" in responce.data