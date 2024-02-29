from flask import url_for, redirect
from unittest.mock import patch, MagicMock
from project.main import verify

@patch('project.conn.cursor')
def test_verify_successfull(mock_cursor, client):
    # with patch('project.main.verify.conn.cursor') as mock_cursor:
        
        mock_cur_instance = mock_cursor.return_value.__enter__.return_value
        mock_cur_instance.fetchone.return_value = ['emailexample@gmail.com']
        mock_cur_instance.rowcount = 1

        response = client.post('/verify', data = {
            'email': 'emailexample@gmail.com',
            'verification_code': 'ggbdfpok[spef][sdfsdlfldssa]'
        })

        assert response.status_code == 302
        assert url_for('login') in response.location

