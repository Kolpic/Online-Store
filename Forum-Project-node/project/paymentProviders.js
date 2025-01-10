const front_office = require('./front_office');
const paypal = require('./paypal');
const backOfficeService = require('./backOfficeService');
const { AssertUser, AssertDev, WrongUserInputException } = require('./exceptions');

const statusАpprovalUrl = 'redirect';
const statusCapturePayment = 'success';
const messageCapturePayment = 'Payment captured successfully.';

class PaymentProvider {
    constructor({ order_id, client }) {
        this.orderId = order_id;
        this.client = client;
    }

    async executePayment() {
        throw new Error('executePayment() must be implemented by subclass');
    }

    async postPaymentProcessing(orderId, response, authenticatedUser) {
        // Common post-payment logic (e.g., update order status, add to email queue)
        await this.client.query(`UPDATE orders SET status = 'Paid' WHERE order_id = $1`, [orderId]);
        let orderRow = await this.client.query(`SELECT * FROM orders WHERE order_id = $1`, [orderId]);

        // Queue email logic here...
        console.log('Post-payment processing complete for order:', orderId);

        let shippingDetailsRow = await this.client.query(`
                SELECT 
                    shipping_id, 
                    order_id,
                    email,
                    first_name,
                    last_name,
                    town,
                    phone,
                    address,
                    country_code_id, 
                    code 
                FROM shipping_details 
                    JOIN country_codes ON country_code_id = country_codes.id 
                WHERE shipping_details.order_id = $1
                `, [orderId]);

        console.log("shippingDetailsRow.rows[0]", shippingDetailsRow.rows[0]);

        response.shipping_details = shippingDetailsRow.rows;

        const bodyTemplateRow = await this.client.query(`SELECT body FROM email_template WHERE name = $1`, ["Payment Email"]);
        const body = bodyTemplateRow.rows[0];

        const userRow = await this.client.query(`SELECT * FROM users WHERE email = $1`, [authenticatedUser.userRow.data]);
        const user = userRow.rows[0];
        AssertDev(userRow.rows.length == 1, "Expect one on user");

        response.user_first_name = user.first_name;
        response.user_last_name = user.last_name;

        const emailData = await backOfficeService.mapEmailData(this.client, authenticatedUser.userRow.data, "Payment Email", body, response, orderRow.rows[0]);

        await this.client.query(`INSERT INTO email_queue (name, data, status) VALUES ($1, $2, $3)`,
            [
            'Payment Email', 
            JSON.stringify(emailData),
            'pending'
            ]);
    }
}

class PayPal extends PaymentProvider {
    async executePayment(orderId) {
        console.log('Executing PayPal payment for order:', orderId);
        const approvalUrl = await paypal.createOrder(orderId, this.client);
        console.log("approvalUrl", approvalUrl);
        return {
            status: statusАpprovalUrl,
            approvalUrl: approvalUrl
        };
    }

    async capturePayment(token) {
        console.log('Capturing PayPal payment for token:', token);

        // Step 2: Capture Payment
        const paymentResult = await paypal.capturePayment(token);

        return {
            status: statusCapturePayment,
            message: messageCapturePayment
        };
    }
}

class Bobi extends PaymentProvider {
    constructor({ orderId, client }) {
        super({ orderId, client });
        // this.paymentAmount = payment_amount;
    }

    async executePayment(orderId, paymentAmount) {
        console.log('Executing Bobi payment for order:', orderId, 'with amount:', paymentAmount);
        return await front_office.payOrder(orderId, paymentAmount, this.client);
    }
}

module.exports = {
    Bobi,
    PayPal
}
