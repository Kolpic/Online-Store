const config = require('./config');
const errors = require('./error_codes');
const { AssertUser, AssertDev, AssertPeer } = require('./exceptions');
const axios = require('axios');

const orderStatusReadyForPaying = 'Ready for Paying';

async function generateAccessToken() {
    const response = await fetch(config.PAYPAL_BASE_URL + "/v1/oauth2/token", {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': 'Basic ' + Buffer.from(config.CLIENT_ID + ':' + config.SECRET_KEY).toString('base64'),
        },
        body: 'grant_type=client_credentials'
    });

	AssertPeer(response.ok, "Failed to generate access token with paypal", errors.ERROR_GENERATING_ACCESS_TOKEN);
    
    const data = await response.json();
    console.log("Paypal generateAccessToken", data);
    return data.access_token;
}

async function createOrder(orderId, client) {
	const accessToken = await generateAccessToken();
    console.log("Paypal generateAccessToken", accessToken);
	
	let order = await client.query(`SELECT * FROM orders WHERE order_id = $1`, [orderId]);
    let orderRow = order.rows;                                                            

    AssertDev(orderRow.length === 1, "There can't be more than one row with same order id");

	let orderItems = await client.query(`
        SELECT 
    		order_items.id, 
    		order_items.order_id, 
    		order_items.product_id, 
    		order_items.quantity          AS cart_quantity, 
    		order_items.price, 
    		order_items.vat,
    		products.name                 AS name,
    		currencies.symbol             AS symbol
		FROM order_items
		JOIN products   ON products.id          = order_items.product_id
		JOIN currencies ON products.currency_id = currencies.id
		WHERE order_id = $1
		`,[orderId]);

	let orderItemsRows = orderItems.rows;

	console.log("orderItemsRows", orderItemsRows); 

	AssertUser(orderRow[0].status === orderStatusReadyForPaying, "This order can't be payed, due to it's status");

    let discount_percentage = parseFloat(orderRow[0].discount_percentage);
	let total = 0;
    let totalWithVat = 0;
    let totalSumToBePayed = 0;
	
	const items = orderItemsRows.map(row => {
        const price = parseFloat(row.price);
        const vatMultiplier = 1 + parseFloat(row.vat) / 100;

        const itemTotalWithVat = price * vatMultiplier;
        let itemTotalWithVatToFixed = 0;

		let totalWithVATProduct = (itemTotalWithVat * parseInt(row.cart_quantity)).toFixed(2);
		// let itemTotalWithoutVAT = price * parseInt(row.cart_quantity);
        total += price * parseInt(row.cart_quantity);
        totalWithVat += itemTotalWithVat * parseInt(row.cart_quantity);

		console.log("totalWithVATProduct", totalWithVATProduct);

        let totalFinalPrice;

        if (discount_percentage > 0) {
            totalFinalPrice = (totalWithVATProduct - (totalWithVATProduct * (discount_percentage / 100))).toFixed(2)
            itemTotalWithVatToFixed =  itemTotalWithVatToFixed - (itemTotalWithVatToFixed * (discount_percentage / 100)).toFixed(2)
        } else {
            totalFinalPrice = totalWithVATProduct.toFixed(2);
        }

        console.log("totalFinalPrice <->", totalFinalPrice, typeof totalFinalPrice);
        let dis = parseFloat(parseFloat(totalFinalPrice).toFixed(2));
        console.log("dis", dis, typeof dis);
        totalSumToBePayed += dis;
        console.log("totalSumToBePayed <->", totalSumToBePayed);
        console.log("itemTotalWithVatToFixed <->", itemTotalWithVatToFixed);

        return {
            name: row.name,
            description: `Product ID: ${row.product_id}`,
            quantity: row.cart_quantity.toString(),
            unit_amount: {
                currency_code: 'USD',
                value: itemTotalWithVatToFixed
            }
        };
    });

    totalSumToBePayed = totalSumToBePayed.toFixed(2);

	const breakdown = {
        item_total: {
            currency_code: 'USD',
            value: totalSumToBePayed
        }
    };

    console.log("totalSumToBePayed given in fetch", totalSumToBePayed);
	console.log("items", items);
	console.log("breakdown", breakdown);
	console.log("accessToken createOrder", accessToken);

    const returnUrl = generateUrl(config.BASE_URL_HOME_OFFICE, '/complete_order', { order_id: orderId });
    const cancelUrl = generateUrl(config.BASE_URL_HOME_OFFICE, '/cancel_order', { order_id: orderId });

	const responseOrder = await fetch(config.PAYPAL_BASE_URL + '/v2/checkout/orders', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + accessToken
        },
        body: JSON.stringify({
            intent: 'CAPTURE',
            purchase_units: [
                {
                    items,
                    amount: {
                        currency_code: 'USD',
                        value: totalSumToBePayed,
                        breakdown
                    }
                }
            ],
            application_context: {                                                               
                return_url: returnUrl,
                cancel_url: cancelUrl,
                shipping_preference: 'NO_SHIPPING',
                user_action: 'PAY_NOW',
                brand_name: 'Kolpic store'
            }
        })
    });
	console.log("responseOrder <->", responseOrder)
	AssertPeer(responseOrder.ok, "Failed to create order with paypal", errors.ERROR_GENERATING_ORDER);
	const orderData = await responseOrder.json();

	console.log("Paypal response for making order", orderData);
	return orderData.links.find(link => link.rel === 'approve').href;
}

async function capturePayment(orderId) {
	const accessToken = await generateAccessToken();

	const response = await fetch(config.PAYPAL_BASE_URL + `/v2/checkout/orders/${orderId}/capture`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + accessToken
        }
    });

	AssertPeer(response.ok, "Failed to capture payment with paypal", errors.ERROR_CAPTURE_ORDER);

	const data = await response.json();
	return data;
}

function generateUrl(baseUrl, path, params) {
    const query = new URLSearchParams(params).toString();
    return `${baseUrl}${path}?${query}`;
}

module.exports = {
	generateAccessToken: generateAccessToken,
	createOrder: createOrder,
	capturePayment: capturePayment,
}