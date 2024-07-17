from project import utils

def create_session(os, datetime, timedelta, session_data, cur, conn):
    session_id = os.urandom(20).hex()
    expires_at = datetime.now() + timedelta(hours=1)

    # cur.execute("SELECT id FROM users WHERE email = %s", (session_data,))
    # userr_id = cur.fetchone()['id']

    # cur.execute("INSERT INTO custom_sessions (session_id, data, expires_at, is_active, user_id) VALUES (%s, %s, %s, %s, %s) RETURNING id", (session_id, session_data, expires_at, True, userr_id))
    # _id = cur.fetchone()['id']

    _id = _map_tables(session_data, cur, session_id, expires_at)

    return session_id

def get_current_user(request, cur):
    session_id = request.cookies.get('session_id')

    if not session_id:
        return None
    else:
        return _get_user_by_session(session_id, cur)

def _get_user_by_session(session_id, cur):
    cur.execute("SELECT id FROM custom_sessions WHERE session_id = %s", (session_id,))
    _id = cur.fetchone()
 
    cur.execute("SELECT data FROM custom_sessions WHERE session_id = %s AND id = %s AND is_active = True", (session_id, _id))

    # utils.AssertDev(rowcounut = 1)

    result = cur.fetchone()

    if result:
        # cur.execute("UPDATE custom_sessions SET is_active = True WHERE session_id = %s AND id = %s", (session_id, _id))
        return result[0]
    else:
        return None

def clear_expired_sessions(cur, conn):
    cur.execute("DELETE FROM custom_sessions WHERE expires_at < NOW()")
    conn.commit()

def update_current_user_session_data(cur, conn, new_data, session_id):
    cur.execute("SELECT id FROM custom_sessions WHERE session_id = %s", (session_id, ))
    _id = cur.fetchone()[0]

    cur.execute("UPDATE custom_sessions SET data = %s WHERE session_id = %s AND id = %s", (new_data, session_id, _id))
    # conn.commit()

def get_user_session_id(request):
    return request.cookies.get('session_id')

def _map_tables(session_data, cur, session_id, expires_at):

    flag = False

    if '@' in session_data:
        cur.execute("SELECT id FROM users WHERE email = %s", (session_data,))
        flag = True
    else:
        cur.execute("SELECT id FROM staff WHERE username = %s", (session_data,))
    
    userr_id = cur.fetchone()['id']

    if flag:
        cur.execute("INSERT INTO custom_sessions (session_id, data, expires_at, is_active, user_id) VALUES (%s, %s, %s, %s, %s) RETURNING id", (session_id, session_data, expires_at, True, userr_id))
    else:
        cur.execute("INSERT INTO custom_sessions (session_id, data, expires_at, is_active, staff_id) VALUES (%s, %s, %s, %s, %s) RETURNING id", (session_id, session_data, expires_at, True, userr_id))

    return cur.fetchone()['id']

def get_session_cookie_type(request, cur):

    session_id = request.cookies.get('session_id')

    cur.execute("SELECT user_id, staff_id FROM custom_sessions WHERE session_id = %s AND is_active = True", (session_id,))
    user_id, staff_id = cur.fetchone()

    utils.trace(user_id)
    utils.trace(staff_id)

    if user_id:
        return True
    else:
        return False
