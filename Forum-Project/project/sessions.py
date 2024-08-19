from project import utils
import psycopg2.extras
from datetime import timedelta, datetime
import os

def create_session(session_data, cur, conn, is_front_office):
    session_id = os.urandom(20).hex()
    expires_at = datetime.now() + timedelta(hours=1)

    if is_front_office:
        cur.execute("""
                    INSERT INTO custom_sessions (
                        session_id, 
                        expires_at, 
                        is_active, 
                        user_id)
                    VALUES (%s, %s, %s, (SELECT id FROM users WHERE email = %s)) 

            """, (session_id, expires_at, True, session_data))
    else:
        cur.execute("""
                    INSERT INTO custom_sessions (
                        session_id, 
                        expires_at, 
                        is_active,
                        staff_id) 
                    VALUES (%s, %s, %s, (SELECT id FROM staff WHERE username = %s)) 

            """, (session_id, expires_at, True, session_data))

    return session_id

def get_current_user(session_id, cur, conn):

    if not session_id:
        return None
    else:
        return _get_user_by_session(session_id, cur)


def _get_user_by_session(session_id, cur):

    cur.execute("""
                SELECT 
                    custom_sessions.*, 
                    users.email AS user_email, 
                    staff.username AS staff_username 
                FROM 
                    custom_sessions 
                LEFT JOIN 
                    users ON custom_sessions.user_id = users.id AND custom_sessions.user_id IS NOT NULL
                LEFT JOIN 
                    staff ON custom_sessions.staff_id = staff.id AND custom_sessions.staff_id IS NOT NULL
                WHERE 
                    custom_sessions.session_id = %s
                """, 
    (session_id,))

    custom_sessions_user_row = cur.fetchone()
    
    if custom_sessions_user_row is None:
        return None

    data = None

    if custom_sessions_user_row['user_email'] is not None:
        data = custom_sessions_user_row['user_email']
    elif custom_sessions_user_row['staff_username'] is not None:
        data = custom_sessions_user_row['staff_username']

    is_active = custom_sessions_user_row['is_active']


    if is_active and data:
        return data
    else:
        return None

def clear_expired_sessions(cur, conn):
    cur.execute("DELETE FROM custom_sessions WHERE expires_at < NOW()")
    conn.commit()


def get_user_session_id(request):
    return request.cookies.get('session_id')

def get_session_cookie_type(session_id, cur):

    cur.execute("SELECT user_id, staff_id FROM custom_sessions WHERE session_id = %s AND is_active = True", (session_id,))
    user_id, staff_id = cur.fetchone()

    if user_id:
        return True
    else:
        return False
