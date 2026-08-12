frappe.pages['edgepay-integrations'].on_page_load = function (wrapper) {
	wrapper.page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __('Integrations'),
		single_column: true,
	});
};

frappe.pages['edgepay-integrations'].on_page_show = function (wrapper) {
	frappe.require('/assets/edgepayv1/js/edgepay_page_loader.js', () => {
		window.EdgePayPageLoader.mount(wrapper, 'integrations');
	});
};
