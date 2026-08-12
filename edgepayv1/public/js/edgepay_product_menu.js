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
				description: "Merchant-scoped payment activity and readiness.",
				icon: "home",
				items: [
					{
						label: "EdgePay Home",
						description: "Review payment activity, onboarding and integration readiness.",
						icon: "home",
						route: "/app/edgepay-home",
					},
					{
						label: "Merchant Onboarding",
						description: "Complete merchant identity, account and verification setup.",
						icon: "check",
						route: "/app/merchant-onboarding",
					},
				],
			},
			{
				label: "Payments",
				description: "Track requests, attempts and immutable payment events.",
				icon: "wallet",
				items: [
					{
						label: "Payment Operations",
						description: "Review merchant payment requests, attempts and events in one workspace.",
						icon: "activity",
						route: "/app/edgepay-payments",
					},
				],
			},
		];

		if (hasAnyRole(["EdgePay Admin", "EdgePay Manager", "EdgePay Auditor"])) {
			sections.push({
				label: "Financial Operations",
				description: "Review refunds, settlements and payment exceptions.",
				icon: "chart",
				items: [
					{
						label: "Finance & Exceptions",
						icon: "report",
						route: "/app/edgepay-finance",
					},
				],
			});
		}

		if (hasAnyRole(["EdgePay Admin", "EdgePay Manager", "EdgePay Auditor"])) {
			sections.push({
				label: "Integrations",
				description: "Review provider, API and delivery integration health.",
				icon: "settings",
				items: [
					{
						label: "Integration Operations",
						icon: "link",
						route: "/app/edgepay-integrations",
					},
				],
			});
		}

		return sections;
	}

	function profile() {
		const bootUser = window.frappe?.boot?.user || {};
		return {
			name: bootUser.full_name || window.frappe?.session?.user || "EdgePay User",
			email: window.frappe?.session?.user || "",
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
				route_patterns: [
					"/app/edgepay*",
					"/app/merchant-onboarding*",
					"/app/query-report/EdgePay*",
				],
				order: 40,
				subtitle: "Payment operations, merchant readiness and settlement intelligence",
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
