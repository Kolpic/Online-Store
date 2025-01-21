const emailTemplates = require('./emailTemplates');
const config = require('./config');

class EmailDataMapper {
    constructor(settings) {
        this.settings = settings;
    }

    async mapVerificationEmail(email, data, bodyData) {
        const verificationURL = `${config.urlVerifyEmail}${data.verification_code}`;
        const html = emailTemplates.emailTemplates.verificationEmail(this.settings)
            .replaceAll('{verification_url}', verificationURL);

        const body = bodyData
            .replaceAll('{first_name}', data.first_name)
            .replaceAll('{last_name}', data.last_name)
            .replaceAll('{url}', html);

        return this.createEmailData(email, 'Verification Email', body);
    }

    async mapPurchaseEmail(email, data, bodyData, orderObj) {
        const productRows = this.generateProductRows(data.cart_items);
        const summaryRows = this.generateSummaryRows(data);
        const discountRows = this.generateDiscountRows(data, orderObj.discount_percentage);

        const purchaseTable = emailTemplates.emailTemplates.purchaseTable(this.settings)
            .replaceAll('{product_rows}', productRows)
            .replaceAll('{summary_rows}', summaryRows)
            .replaceAll('{discount_rows}', discountRows);

        const shippingTable = this.generateShippingTable(data.shipping_details[0]);

        const body = bodyData
            .replaceAll('{first_name}', data.user_first_name)
            .replaceAll('{last_name}', data.user_last_name)
            .replaceAll('{cart}', purchaseTable)
            .replaceAll('{shipping_details}', shippingTable);

        return this.createEmailData(email, 'Purchase Email', body);
    }

    generateProductRows(cartItems) {
        return cartItems.map(product => {
            const singleProductWithVAT = Math.round((parseFloat(product.price) + (parseFloat(product.price) * (parseFloat(product.vat) / 100))) * 100) / 100;
            const totalProductPriceWithVat = singleProductWithVAT * product.cart_quantity;

            return `
                <tr>
                    <td>${product.name}</td>
                    <td style="text-align: ${this.settings.send_email_template_text_align};">${product.cart_quantity}</td>
                    <td style="text-align: ${this.settings.send_email_template_text_align};">${singleProductWithVAT} ${product.symbol}</td>
                    <td style="text-align: ${this.settings.send_email_template_text_align};">${totalProductPriceWithVat} ${product.symbol}</td>
                </tr>
            `;
        }).join('');
    }

    generateSummaryRows(data) {
        return `
            <tr>
                <td colspan='3' style="text-align: ${this.settings.send_email_template_text_align};">Total Order Price Without VAT:</td>
                <td style="text-align: ${this.settings.send_email_template_text_align};">${data.total_sum} ${data.cart_items[0].symbol}</td>
            </tr>
            <tr>
                <td colspan='3' style="text-align: ${this.settings.send_email_template_text_align};">VAT:</td>
                <td style="text-align: ${this.settings.send_email_template_text_align};">${data.vat_in_persent} %</td>
            </tr>
        `;
    }

    generateDiscountRows(data, discountPercentage) {
        if (!discountPercentage || discountPercentage <= 0) return '';
        
        return `
            <tr>
                <td colspan='3' style="text-align: ${this.settings.send_email_template_text_align};">Discount Percentage:</td>
                <td style="text-align: ${this.settings.send_email_template_text_align};">${discountPercentage}%</td>
            </tr>
        `;
    }

    generateShippingTable(shippingDetails) {
        return emailTemplates.emailTemplates.shippingDetails(this.settings)
            .replaceAll('{order_id}', shippingDetails.order_id)
            .replaceAll('{recipient_name}', `${shippingDetails.first_name} ${shippingDetails.last_name}`)
            .replaceAll('{email}', shippingDetails.email)
            .replaceAll('{full_address}', `${shippingDetails.address}, ${shippingDetails.town}`)
            .replaceAll('{phone}', shippingDetails.phone);
    }

    createEmailData(email, subject, html) {
        return {
            from: "no-reply@pascal.com",
            to: email,
            subject,
            html
        };
    }
}

module.exports = { EmailDataMapper }