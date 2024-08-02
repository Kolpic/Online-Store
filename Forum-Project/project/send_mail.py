import psycopg2
from project import utils
from flask_mail import Mail, Message

def send_mail(products, shipping_details, total_sum, total_with_vat, provided_sum, user_email, cur, conn, email_type, app, mail):
    cur_dict = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    query = """
            SELECT
                settings.send_email_template_background_color AS background_color,
                settings.send_email_template_text_align       AS text_align,
                settings.send_email_template_border           AS border,
                settings.send_email_template_border_collapse  AS border_collapse,
                email_template.subject                        AS subject,
                email_template.sender                         AS sender,
                email_template.body                           AS body,
                users.first_name                              AS first_name,
                users.last_name                               AS last_name
            FROM settings
    """

    if email_type == 'payment_mail':
        query += " JOIN email_template ON email_template.name = 'Payment Email'"
    elif email_type == 'purchase_mail':
        query += "JOIN email_template  ON email_template.name = 'Purchase Email'"
    else:
        pass

    query += """
                JOIN users ON users.email = %s
        """

    cur_dict.execute(query, (user_email,))
    query_results = cur_dict.fetchone()

    utils.AssertDev(query_results, "No information in database")

    background_color = query_results['background_color']
    text_align = query_results['text_align']
    border = query_results['border']
    border_collapse = query_results['border_collapse']
    first_name = query_results['first_name']
    last_name = query_results['last_name']
    subject = query_results['subject']
    sender = query_results['sender']
    body = query_results['body']

    products_html = f"""
    <table border="{border}" cellpadding="5" cellspacing="3" style="border-collapse: {border_collapse};">
        <tr>
            <th style="background-color: {background_color};">Product</th>
            <th style="background-color: {background_color};">Quantity</th>
            <th style="background-color: {background_color};">Price</th>
            <th style="background-color: {background_color};">Total Product Price</th>
        </tr>
    """
    total_price = 0

    vat_total = 0
    currency_sumbol = ""
    for item in products:
        if email_type == 'purchase_mail':
            product_id, product_name, quantity, price, symbol, vat = item
        elif email_type == 'payment_mail':
            product_name, quantity, price, symbol, vat = item

        utils.trace(vat)
        utils.trace(type(vat))

        float_vat = float(vat)

        utils.trace(float_vat)
        utils.trace(type(float_vat))

        currency_sumbol = symbol
        price_total = float(price) * int(quantity)
        total_price += price_total
        vat_total += price_total * (float_vat / 100)
        products_html += f"""
        <tr>
            <td>{product_name}</td>
            <td style="text-align: {text_align};">{quantity}</td>
            <td style="text-align: {text_align};">{price} {symbol}</td>
            <td style="text-align: {text_align};">{price_total} {symbol}</td>
        </tr>
        """
    
    _total_price = round(total_price, 2)
    products_html += f"""
        <tr>
            <td colspan='3' style="text-align: {text_align};">Total Order Price Without VAT:</td>
            <td style="text-align: {text_align};">{round(total_sum, 2)} {currency_sumbol}</td>
        </tr>
        <tr>
            <td colspan='3' style="text-align: {text_align};">VAT:</td>
            <td style="text-align: {text_align};">{round(vat_total, 2)} {currency_sumbol}</td>
        </tr>
        <tr>
            <td colspan='3' style="text-align: {text_align};">Total Order Price With VAT:</td>
            <td style="text-align: {text_align};">{round(total_with_vat, 2)} {currency_sumbol}</td>
        </tr>
    """

    if email_type == 'payment_mail':
        products_html += f"""
            <tr>
                <td colspan='3' style="text-align: {text_align};">You paid:</td>
                <td style="text-align: {text_align};">{round(provided_sum, 2)} {currency_sumbol}</td>
            </tr>
        </table>
        """
    elif email_type == 'purchase_mail':
        products_html += "</table>"

    shipping_id, order_id, email, first_name, last_name, town, address, phone, country_code_id = shipping_details
    shipping_html = f"""
    <table border="{border}" cellpadding="5" cellspacing="3" style="border-collapse: {border_collapse};">
        <tr>
            <th style="background-color: {background_color};">Order ID</th><td>{order_id}</td>
        </tr>
        <tr>
            <th style="background-color: {background_color};">Recipient</th><td>{first_name} {last_name}</td>
        </tr>
        <tr>
            <th style="background-color: {background_color};">Email</th><td>{email}</td>
        </tr>
        <tr>
            <th style="background-color: {background_color};">Address</th><td>{address}, {town}</td>
        </tr>
        <tr>
            <th style="background-color: {background_color};">Phone</th><td>{phone}</td>
        </tr>
    </table>
    """

    if email_type == 'payment_mail':
        body_filled = body.format(
            first_name=first_name,
            last_name=last_name,
            products=products_html,
            shipping_details=shipping_html,
        )
    elif email_type == 'purchase_mail':
        body_filled = body.format(
            first_name=first_name,
            last_name=last_name,
            cart=products_html,
            shipping_details=shipping_html,
        )
    else:
        pass

    with app.app_context():
        msg = Message(subject,
                sender = sender,
                recipients = [user_email])
    msg.html = body_filled
    mail.send(msg)