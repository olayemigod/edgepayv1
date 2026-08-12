frappe.pages["merchant-onboarding"].on_page_load = function (wrapper) {
	wrapper.page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Merchant Onboarding"),
		single_column: true,
	});
};

frappe.pages["merchant-onboarding"].on_page_show = function (wrapper) {
	frappe.require("/assets/edgepayv1/js/edgepay_page_loader.js", () => {
		window.EdgePayPageLoader.mount(wrapper, "onboarding");
	});
};
