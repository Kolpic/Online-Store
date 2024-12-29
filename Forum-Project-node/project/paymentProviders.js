const front_office = require('./front_office');
const paypal = require('./paypal');
const backOfficeService = require('./backOfficeService');
const { AssertUser, AssertDev, WrongUserInputException } = require('./exceptions');

class PaymentProvider {
    constructor(orderId, client) {
        this.orderId = orderId;
        this.client = client;
    }

    async executePayment() {
        throw new Error('executePayment() must be implemented by subclass');
    }

    async postPaymentProcessing(response, authenticatedUser) {
        // console.log("response in postPaymentProcessing", response);
        // Common post-payment logic (e.g., update order status, add to email queue)
        await this.client.query(`UPDATE orders SET status = 'Paid' WHERE order_id = $1`, [this.orderId]);

        // Queue email logic here...
        console.log('Post-payment processing complete for order:', this.orderId);

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
                `, [this.orderId]);

        console.log("shippingDetailsRow.rows[0]", shippingDetailsRow.rows[0]);

        response.shipping_details = shippingDetailsRow.rows;

        const bodyTemplateRow = await this.client.query(`SELECT body FROM email_template WHERE name = $1`, ["Payment Email"]);
        const body = bodyTemplateRow.rows[0];

        const userRow = await this.client.query(`SELECT * FROM users WHERE email = $1`, [authenticatedUser.userRow.data]);
        const user = userRow.rows[0];
        AssertDev(userRow.rows.length == 1, "Expect one on user");

        response.user_first_name = user.first_name;
        response.user_last_name = user.last_name;

        const emailData = await backOfficeService.mapEmailData(this.client, authenticatedUser.userRow.data, "Payment Email", body, response);

        await this.client.query(`INSERT INTO email_queue (name, data, status) VALUES ($1, $2, $3)`,
            [
            'Payment Email', 
            JSON.stringify(emailData),
            'pending'
            ]);
    }
}

class PayPal extends PaymentProvider {
    constructor(orderId, client) {
        super(orderId, client);
    }

    async executePayment() {
        console.log('Executing PayPal payment for order:', this.orderId);
        const approvalUrl = await paypal.createOrder(this.orderId, this.client);
        return {
            status: 'redirect',
            approvalUrl: approvalUrl
        };
    }

    async capturePayment(token) {
        console.log('Capturing PayPal payment for token:', token);

        // Step 2: Capture Payment
        const paymentResult = await paypal.capturePayment(token);

        return {
            status: 'success',
            message: 'Payment captured successfully.'
        };
    }
}

class Bobi extends PaymentProvider {
    constructor(orderId, client, paymentAmount) {
        super(orderId, client);
        this.paymentAmount = paymentAmount;
    }

    async executePayment() {
        console.log('Executing Bobi payment for order:', this.orderId, 'with amount:', this.paymentAmount);
        return await front_office.payOrder(this.orderId, this.paymentAmount, this.client);
    }
}

module.exports = {
    Bobi,
    PayPal
}
