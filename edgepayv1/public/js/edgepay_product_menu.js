(function () {
	"use strict";
	if (typeof window === "undefined") return;
	const hasRole = (...required) => window.frappe?.session?.user === "Administrator" || required.some((role) => (window.frappe?.user_roles || []).includes(role));
	function sections() {
		const items = [
			{label:"Overview",icon:"home",items:[{label:"EdgePay Home",icon:"home",route:"/app/edgepay-home"},{label:"Merchant Onboarding",icon:"check",route:"/app/merchant-onboarding"}]},
			{label:"Payments",icon:"wallet",items:[{label:"Payment Operations",icon:"list",route:"/app/edgepay-payments"},{label:"Payment Links",icon:"link",route:"/app/edgepay-payment-links"},{label:"Payment Attempts",icon:"repeat",route:"/app/edgepay-payment-attempt"},{label:"Transactions",icon:"credit-card",route:"/app/edgepay-payment-transaction"}]},
			{label:"Finance",icon:"chart",items:[{label:"Finance & Exceptions",icon:"chart",route:"/app/edgepay-finance"},{label:"Fees",icon:"dollar-sign",route:"/app/edgepay-fee-record"}]},
			{label:"Integrations",icon:"link",items:[{label:"Integration Operations",icon:"link",route:"/app/edgepay-integrations"},{label:"Deliveries",icon:"activity",route:"/app/edgepay-delivery"}]},
		];
		if (hasRole("EdgePay Admin", "EdgePay Manager")) items.push({label:"Platform Setup",icon:"settings",items:[{label:"Provider Accounts",icon:"settings",route:"/app/edgepay-provider-account"},{label:"API Clients",icon:"key",route:"/app/edgepay-api-client"},{label:"Delivery Endpoints",icon:"send",route:"/app/edgepay-delivery-endpoint"}]});
		return items;
	}
	function register() {
		window.frappe?.require?.("edgesuite_ui.bundle.js", () => {
			const runtime = window.EdgeSuiteUI || window.EdgeUI;
			if (!runtime?.registerProductMenu) return;
			runtime.registerProductMenu({product_key:"edgepay",product:"EdgePay",label:"EdgePay",icon:"wallet",home_route:"/app/edgepay-home",route_patterns:["/app/edgepay*","/app/merchant-onboarding"],order:40,subtitle:"Payments, settlement and integration operations",menu_source:"edgepay",sections:sections()});
			runtime.refreshProductMenu?.();
		});
	}
	window.EdgePayProductMenu = {register, sections};
	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", register, {once:true}); else register();
	document.addEventListener("page-change", register);
})();
