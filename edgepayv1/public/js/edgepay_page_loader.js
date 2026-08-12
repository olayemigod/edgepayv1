window.EdgePayPageLoader = (() => {
	const REQUIRED_COMPONENTS = [
		"EdgeAppShell",
		"EdgePageLayout",
		"EdgePageHeader",
		"EdgeDataTable",
		"EdgeModal",
		"EdgeInput",
		"EdgeLoadingState",
		"EdgeErrorState",
	];

	function showFailure(page, message) {
		$(page.body).empty();
		$('<div class="alert alert-danger p-4"></div>').text(message).appendTo(page.body);
	}

	function mount(wrapper, mode) {
		const page = wrapper.page;
		wrapper.edgepay_visit_id = (wrapper.edgepay_visit_id || 0) + 1;
		const visitId = wrapper.edgepay_visit_id;
		wrapper.vue_app?.unmount?.();
		wrapper.vue_app = null;
		$(page.body).empty();
		const loading = $('<div class="p-6 text-center text-muted"></div>')
			.text(__("Loading EdgePay..."))
			.appendTo(page.body);

		frappe.require("edgeui.bundle.js", () => {
			if (wrapper.edgepay_visit_id !== visitId) return;
			const runtime = window.EdgeSuiteUI || window.EdgeUI;
			const missing = REQUIRED_COMPONENTS.filter((name) => !runtime?.components?.[name]);
			if (!runtime?.createEdgeApp || missing.length) {
				loading.remove();
				showFailure(
					page,
					missing.length
						? __("EdgePay requires EdgeSuite UI 0.6.3 or newer. Missing: {0}", [
								missing.join(", "),
						  ])
						: __("The standalone EdgeSuite UI runtime is unavailable.")
				);
				return;
			}

			frappe.require("edgepay_workspace.bundle.js", () => {
				if (wrapper.edgepay_visit_id !== visitId) return;
				if (typeof window.mountEdgePayWorkspace !== "function") {
					loading.remove();
					showFailure(
						page,
						__("The EdgePay EdgeSuite workspace bundle failed to register.")
					);
					return;
				}
				try {
					loading.remove();
					const root = $(
						'<div class="edgepay-workspace-root" data-edge-product="edgepay"></div>'
					).appendTo(page.body);
					wrapper.vue_app = window.mountEdgePayWorkspace(root[0], { mode });
				} catch (error) {
					console.error("Error mounting EdgePay workspace:", error);
					loading.remove();
					showFailure(
						page,
						__("Error mounting EdgePay workspace: {0}", [
							error.message || String(error),
						])
					);
				}
			});
		});
	}

	return { mount };
})();
