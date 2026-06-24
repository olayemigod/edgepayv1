// Copyright (c) 2026, ProcessEdge Solutions Limited and contributors
// For license information, please see license.txt

frappe.ui.form.on('EdgePay Payment Request', {
	refresh: function(frm) {
		if (!frm.is_new()) {
			// Show 'Initialize Checkout' button if status is Draft or Initiated
			if (['Draft', 'Initiated'].includes(frm.doc.status)) {
				frm.add_custom_button(__('Initialize Checkout'), function() {
					frappe.call({
						method: 'edgepayv1.edgepay.services.api.initialize_payment_request_checkout',
						args: {
							payment_request_name: frm.doc.name
						},
						callback: function(r) {
							if (r.message && r.message.ok) {
								frappe.show_alert({
									message: __('Checkout initialized successfully.'),
									indicator: 'green'
								});
								frm.reload_doc();
								
								// If checkout URL is returned, open it in a new window/tab
								let data = r.message.data || {};
								if (data.checkout_url) {
									window.open(data.checkout_url, '_blank');
								}
							} else if (r.message && r.message.message) {
								frappe.msgprint(r.message.message);
							}
						}
					});
				});
			}

			// Show 'Verify Payment' button if status is Initiated
			if (frm.doc.status === 'Initiated') {
				frm.add_custom_button(__('Verify Payment'), function() {
					frappe.call({
						method: 'edgepayv1.edgepay.services.api.verify_payment_request_transaction',
						args: {
							payment_request_name: frm.doc.name
						},
						callback: function(r) {
							if (r.message && r.message.ok) {
								frappe.show_alert({
									message: __('Payment verification checked successfully.'),
									indicator: 'green'
								});
								frm.reload_doc();
							} else if (r.message && r.message.message) {
								frappe.msgprint(r.message.message);
							}
						}
					});
				});
			}

			// Show 'Go to Checkout' button if checkout_url is available and status is Initiated
			if (frm.doc.checkout_url && frm.doc.status === 'Initiated') {
				frm.add_custom_button(__('Go to Checkout'), function() {
					window.open(frm.doc.checkout_url, '_blank');
				}, __('Actions'));
			}
		}
	}
});
