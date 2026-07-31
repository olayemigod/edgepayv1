frappe.pages['merchant-onboarding'].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __('Merchant Onboarding'),
		single_column: true,
	});
	const body = $('<div class="p-4"></div>').appendTo(page.body);
	frappe.call({
		method: 'edgepayv1.edgepay.page.merchant_onboarding.merchant_onboarding.get_onboarding_page_data',
		callback: function (response) {
			const data = response.message || {};
			body.empty();
			if (!data.merchant) {
				$('<h4></h4>').text(__('No Merchant Context')).appendTo(body);
				$('<p></p>').text(__('Ask an EdgePay administrator to add you to a Merchant.')).appendTo(body);
				return;
			}
			$('<h3></h3>').text(data.merchant.merchant_name || data.merchant.name).appendTo(body);
			$('<p></p>').text(__('Onboarding Status') + ': ' + (data.merchant.onboarding_status || '')).appendTo(body);
			$('<p></p>').text(__('Verification Status') + ': ' + (data.merchant.verification_status || '')).appendTo(body);
			$('<p></p>').text(__('Live Payments') + ': ' + (data.merchant.live_payments_allowed ? __('Allowed') : __('Not Allowed'))).appendTo(body);
			$('<h4></h4>').text(__('Provider Accounts')).appendTo(body);
			(data.provider_accounts || []).forEach(function (row) {
				$('<p></p>').text(row.name + ' - ' + row.environment + ' - ' + row.status).appendTo(body);
			});
		},
	});
};
