from flask import url_for, redirect
from unittest.mock import patch, MagicMock
from project.main import verify

# @patch('project.main.conn.cursor')
# def test_verify_successfull(mock_cursor, client):
#     # with patch('project.main.verify.conn.cursor') as mock_cursor:
        
#         mock_cur_instance = mock_cursor.return_value.__enter__.return_value
#         mock_cur_instance.fetchone.return_value = ['emailexample@gmail.com']
#         mock_cur_instance.rowcount = 1

#         response = client.post('/verify', data = {
#             'email': 'emailexample@gmail.com',
#             'verification_code': 'ggbdfpok[spef][sdfsdlfldssa]'
#         })

#         assert response.status_code == 302
#         assert url_for('login') in response.location
#         mock_cur_instance.execute.assert_any_call("SELECT email FROM users WHERE email = %s", ('user@example.com',))
#         mock_cur_instance.execute.assert_any_call("UPDATE users SET verification_status = true WHERE verification_code = %s", ('123456',))
#         mock_cur_instance.close.assert_called_once()

@patch("psycopg2.connect")
def test_verify_successfull(mock_connect, client):
    breakpoint()
    expeted_email_from_db = ('galincho789@gmail.com',)

    mock_conn = mock_connect.return_value
    mock_cur = mock_conn.cursor.return_value
    mock_execure_one = mock_cur.cursor.return_value
    mock_cur.fetchone.return_value = expeted_email_from_db[0]
    breakpoint()

    response = client.post('/verify', data = {
        'email': 'galincho789@gmail.com',
        'verification_code': '123456789'
    })

    breakpoint()
    assert response.status_code == 302
    assert url_for('login') in response.headers['Location']
    breakpoint()
    # assert '/login' in response.headers['Location']
    # mock_cur.execute.assert_any_call("SELECT email FROM users WHERE email = %s", (expeted_email_from_db,))
    # mock_cur.execute.assert_any_call("UPDATE users SET verification_status = true WHERE verification_code = %s", ('123456789'))

