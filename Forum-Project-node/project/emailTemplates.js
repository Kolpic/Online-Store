const emailTemplates = {
    verificationEmail: (settings) => `
        <a href="{verification_url}">Click here to verify your account</a>
    `,

    purchaseTable: (settings) => `
        <table border="${settings.send_email_template_border}" 
               cellpadding="5" 
               cellspacing="3" 
               style="border-collapse: ${settings.send_email_template_border_collapse};">
            <tr>
                <th style="background-color: ${settings.send_email_template_background_color};">Product</th>
                <th style="background-color: ${settings.send_email_template_background_color};">Quantity</th>
                <th style="background-color: ${settings.send_email_template_background_color};">Price (Per item with VAT)</th>
                <th style="background-color: ${settings.send_email_template_background_color};">Total Product Price With VAT</th>
            </tr>
            {product_rows}
            {summary_rows}
            {discount_rows}
        </table>
    `,

    shippingDetails: (settings) => `
        <table border="${settings.send_email_template_border}" 
               cellpadding="5" 
               cellspacing="3" 
               style="border-collapse: ${settings.send_email_template_border_collapse};">
            <tr>
                <th style="background-color: ${settings.send_email_template_background_color};">Order ID</th>
                <td>{order_id}</td>
            </tr>
            <tr>
                <th style="background-color: ${settings.send_email_template_background_color};">Recipient</th>
                <td>{recipient_name}</td>
            </tr>
            <tr>
                <th style="background-color: ${settings.send_email_template_background_color};">Email</th>
                <td>{email}</td>
            </tr>
            <tr>
                <th style="background-color: ${settings.send_email_template_background_color};">Address</th>
                <td>{full_address}</td>
            </tr>
            <tr>
                <th style="background-color: ${settings.send_email_template_background_color};">Phone</th>
                <td>{phone}</td>
            </tr>
        </table>
    `
};

module.exports = { emailTemplates }