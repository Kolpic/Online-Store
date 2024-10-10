const nodemailer = require('nodemailer');

async function sendEmail(email, token) {
	const transporter = nodemailer.createTransport({
    	host: 'localhost',
    	port: 1025,
    	auth: null 
	});

	const verificationURL = "http://10.20.3.101:5002/verify.html?token=" + token;
	const mailOptions = {
        from: 'no-reply@pascal.com',
        to: email,
        subject: 'Email Verification',
        html: `<p>Please verify your email by clicking on the following link: 
               <a href="${verificationURL}">Verify Email</a></p>`
    };

    transporter.sendMail(mailOptions, (error, info) => {
        if (error) {
            return {isSend: false, info: info};
        } else {
            return {isSend: true, info: info};
        }
    });
}

module.exports = {
	sendEmail,
}