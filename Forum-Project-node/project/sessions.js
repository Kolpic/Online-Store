const { AssertUser, AssertDev } = require('./exceptions');
const crypto = require('crypto');

async function createSession(email, isFrontOffice, client) {
	const sessionId = crypto.randomBytes(20).toString('hex');
  	const expiresAt = new Date(Date.now() + 3600 * 1000); // 1-hour expiration

  	if (isFrontOffice) {
  		await client.query(`
  			INSERT INTO custom_sessions 
  				(session_id, expires_at, is_active, user_id)
         	VALUES 
         		($1, $2, $3, (SELECT id FROM users WHERE email = $4))`,
        	[sessionId, expiresAt, true, email]
  		);
  	} else {
  		await client.query(
        `INSERT INTO custom_sessions 
        	(session_id, expires_at, is_active, staff_id)
         VALUES 
         	($1, $2, $3, (SELECT id FROM staff WHERE username = $4))`,
        [sessionId, expiresAt, true, email]
      );
  	}

  	return sessionId;
}

async function getCurrentUser(sessionId , client) {
	if (!sessionId) {
		return null;
	} else {
		return await getUserBySession(sessionId, client);
	}
}

async function getUserBySession(sessionId, client) {
	const sessionRes = await client.query(
      `SELECT 
      		custom_sessions.*, 
      		users.email    AS user_email, 
      		staff.username AS staff_username
       FROM 
       		custom_sessions
       LEFT JOIN 
       		users ON custom_sessions.user_id = users.id AND custom_sessions.user_id IS NOT NULL
       LEFT JOIN 
       		staff ON custom_sessions.staff_id = staff.id AND custom_sessions.staff_id IS NOT NULL
       WHERE custom_sessions.session_id = $1`,
      [sessionId]
    );

    const customSessionUserRow = sessionRes.rows[0];

    if (!customSessionUserRow) {
      return null;
    }

    const settingsRes = await client.query('SELECT * FROM settings');
    const settingsRow = settingsRes.rows[0];

    AssertDev(settingsRow, "No information in db about settings");

    const data = customSessionUserRow.user_email || customSessionUserRow.staff_username;
    const isActive = customSessionUserRow.is_active;

    const dataToReturn = {
      userRow: {
        session_id: customSessionUserRow.session_id,
        data,
        user_id: customSessionUserRow.user_id,
        is_active: isActive,
        expires_at: customSessionUserRow.expires_at,
      },
      settingsRow: {
        id: settingsRow.id,
        vat: settingsRow.vat,
        report_limitation_rows: settingsRow.report_limitation_rows,
        send_email_template_background_color: settingsRow.send_email_template_background_color,
        send_email_template_text_align: settingsRow.send_email_template_text_align,
        send_email_template_border: settingsRow.send_email_template_border,
        send_email_template_border_collapse: settingsRow.send_email_template_border_collapse,
      },
    };

    if (isActive && data) {
      return dataToReturn;
    } else {
      return null;
    }
}

async function clearExpiredSessions(client) {
    await client.query('DELETE FROM custom_sessions WHERE expires_at < NOW()');
}

async function getSessionCookieType(sessionId, client) {
    const res = await client.query(
      'SELECT user_id, staff_id FROM custom_sessions WHERE session_id = $1 AND is_active = true',
      [sessionId]
    );
    const { user_id: userId, staff_id: staffId } = res.rows[0] || {};

    if (userId) {
      return true; // Session belongs to a user
    } else if (staffId) {
      return false; // Session belongs to a staff member
    } else {
      return null; // Invalid session
    }
}

module.exports = {
	createSession,
	getCurrentUser,

}