(function () {
	"use strict";

	if (typeof window === "undefined") return;

	const PRODUCT_KEY = "edgepay";
	const PRODUCT_LABEL = "EdgePay";

	function roles() {
		return new Set(window.frappe?.user_roles || []);
	}

	function hasAnyRole(required) {
		if (window.frappe?.session?.user === "Administrator") return true;
		const userRoles = roles();
		return required.some((role) => userRoles.has(role));
	}

	function menuSections() {
		const sections = [
			{
				label: "Overview",
				description: "Payment readiness, activity and exceptions.",
				icon: "home",
				items: [
					{
						label: "EdgePay Home",
						description: "Review payment activity and registration readiness.",
						icon: "home",
						route: "/app/edgepay-home",
					},
				],
			},
			{
				label: "Payments",
				description: "Track payment requests and their verified status.",
				icon: "wallet",
				items: [
					{
						label: "Payment Requests",
						description: "Open payment requests, customer references and statuses.",
						icon: "list",
						route: "/app/edgepay-payment-request",
					},
				],
			},
			{
				label: "Registration & Settings",
				description: "Review tenant payment activation and safe setup information.",
				icon: "settings",
				items: [
					{
						label: "Registration Readiness",
						description: "Check activation, currency, provider and webhook readiness.",
						icon: "check",
						route: "/app/edgepay-home#registration-readiness",
					},
				],
			},
			{
				label: "Reports & Information",
				description: "Review payment status summaries and recent activity.",
				icon: "chart",
				items: [
					{
						label: "Payment Summary",
						description: "View successful, pending, failed and expired request totals.",
						icon: "chart",
						route: "/app/edgepay-home#payment-summary",
					},
				],
			},
		];

		if (hasAnyRole(["EdgePay Admin", "EdgePay Manager"])) {
			sections[2].items.push({
				label: "Tenant Payment Settings",
				description: "Open approved EdgePay tenant settings.",
				icon: "settings",
				route: "/app/edgepay-home#tenant-settings",
			});
		}
		return sections;
	}

	function profile() {
		const bootUser = window.frappe?.boot?.user || {};
		return {
			name: bootUser.full_name || window.frappe?.session?.user || "EdgePay User",
			email: window.frappe?.session?.user || "",
			company: window.frappe?.defaults?.get_default?.("company") || "",
		};
	}

	function register() {
		window.frappe?.require?.("edgesuite_ui.bundle.js", () => {
			const runtime = window.EdgeSuiteUI || window.EdgeUI;
			if (!runtime?.registerProductMenu) return;
			runtime.registerProductMenu({
				product_key: PRODUCT_KEY,
				product: PRODUCT_LABEL,
				label: PRODUCT_LABEL,
				icon: "wallet",
				home_route: "/app/edgepay-home",
				route_patterns: ["/app/edgepay*", "/app/query-report/EdgePay*"],
				order: 40,
				subtitle: "Payment operations and settlement intelligence",
				menu_source: "edgepay",
				sections: menuSections(),
				profile: profile(),
			});
			runtime.refreshProductMenu?.();
		});
	}

	window.EdgePayProductMenu = Object.assign(window.EdgePayProductMenu || {}, {
		register,
		sections: menuSections,
	});

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", register, { once: true });
	} else {
		register();
	}

	["desktop_screen", "sidebar_setup", "toolbar_setup", "page-change"].forEach((eventName) => {
		document.addEventListener(eventName, register);
	});
})();
