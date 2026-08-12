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
	const view = app.mount(target);
	return { view, unmount: () => app.unmount() };
}

if (typeof window !== "undefined") {
	window.mountEdgePayWorkspace = mountEdgePayWorkspace;
}
