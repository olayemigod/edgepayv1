import EdgePayOperationalSearch from "./edgepay_workspace/EdgePayOperationalSearch.vue";
import EdgePayWorkspace from "./edgepay_workspace/EdgePayWorkspaceShell.vue";

export function mountEdgePayWorkspace(target, options = {}) {
	const runtime = window.EdgeSuiteUI || window.EdgeUI;
	if (!runtime || typeof runtime.createEdgeApp !== "function") {
		throw new Error("Standalone EdgeSuite UI runtime is unavailable.");
	}

	const workspaceComponents = EdgePayWorkspace.components || {};
	Object.values(workspaceComponents).forEach((component) => {
		if (!component || typeof component !== "object") return;
		component.components = { ...runtime.components, ...(component.components || {}) };
	});

	const showOperationalSearch = ["payments", "finance"].includes(options.mode);
	const workspaceTarget = document.createElement("div");
	target.replaceChildren();

	let searchApp = null;
	if (showOperationalSearch) {
		const searchTarget = document.createElement("div");
		target.appendChild(searchTarget);
		const SearchRoot = {
			...EdgePayOperationalSearch,
			components: { ...runtime.components, ...(EdgePayOperationalSearch.components || {}) },
		};
		searchApp = runtime.createEdgeApp(SearchRoot);
		searchApp.mount(searchTarget);
	}

	target.appendChild(workspaceTarget);
	const Root = {
		...EdgePayWorkspace,
		components: { ...runtime.components, ...workspaceComponents },
		data() {
			const base =
				typeof EdgePayWorkspace.data === "function"
					? EdgePayWorkspace.data.call(this)
					: {};
			return { ...base, workspaceMode: options.mode || "home" };
		},
	};
	const app = runtime.createEdgeApp(Root);
	const view = app.mount(workspaceTarget);
	return {
		view,
		unmount: () => {
			searchApp?.unmount?.();
			app.unmount();
		},
	};
}

if (typeof window !== "undefined") {
	window.mountEdgePayWorkspace = mountEdgePayWorkspace;
}
