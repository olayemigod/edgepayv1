frappe.pages['merchant-onboarding'].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __('Merchant Onboarding'), single_column: true });
	const body = $('<div class="p-4"></div>').appendTo(page.body);
	let pageData = {};

	function refresh() {
		frappe.call({ method: 'edgepayv1.edgepay.page.merchant_onboarding.merchant_onboarding.get_onboarding_page_data', callback: function (response) {
			pageData = response.message || {}; body.empty();
			if (!pageData.merchant) { $('<h4></h4>').text(__('No Merchant Context')).appendTo(body); $('<p></p>').text(__('Ask an EdgePay administrator to add you to a Merchant.')).appendTo(body); return; }
			$('<h3></h3>').text(pageData.merchant.merchant_name || pageData.merchant.name).appendTo(body);
			$('<p></p>').text(__('Onboarding Status') + ': ' + (pageData.merchant.onboarding_status || '')).appendTo(body);
			$('<p></p>').text(__('Verification Status') + ': ' + (pageData.merchant.verification_status || '')).appendTo(body);
			$('<p></p>').text(__('Live Payments') + ': ' + (pageData.merchant.live_payments_allowed ? __('Allowed') : __('Not Allowed'))).appendTo(body);
			$('<button class="btn btn-primary mt-3"></button>').text(__('Verify Representative Identity')).appendTo(body).on('click', openIdentityDialog);
			$('<h4 class="mt-4"></h4>').text(__('Provider Accounts')).appendTo(body);
			(pageData.provider_accounts || []).forEach(row => $('<p></p>').text(row.name + ' - ' + row.environment + ' - ' + row.status).appendTo(body));
		} });
	}

	function openIdentityDialog() {
		const dialog = new frappe.ui.Dialog({
			title: __('Representative Identity Verification'),
			fields: [
				{ fieldname: 'merchant_verification', fieldtype: 'Link', options: 'EdgePay Merchant Verification', label: __('Merchant Verification'), reqd: 1, get_query: () => ({ filters: { merchant: pageData.merchant.name } }) },
				{ fieldname: 'provider', fieldtype: 'Link', options: 'EdgePay Verification Provider', label: __('Verification Provider'), reqd: 1, get_query: () => ({ filters: { enabled: 1 } }) },
				{ fieldname: 'first_name', fieldtype: 'Data', label: __('First Name'), reqd: 1 }, { fieldname: 'middle_name', fieldtype: 'Data', label: __('Middle Name') },
				{ fieldname: 'last_name', fieldtype: 'Data', label: __('Surname'), reqd: 1 }, { fieldname: 'date_of_birth', fieldtype: 'Date', label: __('Date of Birth'), reqd: 1 },
				{ fieldname: 'phone', fieldtype: 'Data', label: __('Phone'), reqd: 1 },
				{ fieldname: 'selfie_file', fieldtype: 'Attach Image', label: __('Live Selfie / Photo'), reqd: 1, description: __('A production provider must replace simple upload with its camera liveness SDK.') },
				{ fieldname: 'consent', fieldtype: 'Check', label: __('I consent to NIN, BVN, DOB, liveness and face verification for merchant onboarding.'), reqd: 1 },
				{ fieldname: 'nin', fieldtype: 'Password', label: __('NIN'), reqd: 1, description: __('Used only for this provider request and not stored by EdgePay.') },
				{ fieldname: 'bvn', fieldtype: 'Password', label: __('BVN'), reqd: 1, description: __('Used only for this provider request and not stored by EdgePay.') },
				{ fieldname: 'bvn_consent_token', fieldtype: 'Password', label: __('BVN Consent Token'), reqd: 1 },
			],
			primary_action_label: __('Verify Identity'),
			primary_action: function (values) {
				if (!values.consent) { frappe.msgprint(__('Consent is required.')); return; }
				const safeSessionArgs = {
					merchant_verification: values.merchant_verification, provider: values.provider,
					first_name: values.first_name, middle_name: values.middle_name, last_name: values.last_name,
					date_of_birth: values.date_of_birth, phone: values.phone, selfie_file: values.selfie_file,
				};
				frappe.call({ method: 'edgepayv1.edgepay.services.identity_verification_api.create_identity_session', args: safeSessionArgs, callback: function (created) {
					const session = created.message && created.message.session; if (!session) return;
					frappe.call({ method: 'edgepayv1.edgepay.services.identity_verification_api.submit_identity_values', args: { session_name: session, nin: values.nin, bvn: values.bvn, bvn_consent_token: values.bvn_consent_token }, callback: function (result) {
						dialog.hide(); frappe.msgprint(__('Identity verification status: {0}', [(result.message || {}).status || __('Unknown')])); refresh();
					} });
				} });
			},
		});
		dialog.show();
	}
	refresh();
};
