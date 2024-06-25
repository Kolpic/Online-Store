def create_session(os, datetime, timedelta, session_data, cur, conn):
    session_id = os.urandom(20).hex()
    expires_at = datetime.now() + timedelta(hours=1)

    cur.execute("INSERT INTO custom_sessions (session_id, data, expires_at, is_active) VALUES (%s, %s, %s, %s) RETURNING id", (session_id, session_data, expires_at, True))
    _id = cur.fetchone()['id']

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