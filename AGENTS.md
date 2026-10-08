# EdgePay Repository Instructions

Before any planning, edit, implementation, review, test, branch/PR, QA, migration or release operation, load and follow the canonical ProcessEdge Frappe/ERPNext Product Engineering Skill:

https://github.com/olayemigod/processedge-qa/blob/main/skills/processedge-frappe-product-engineering/SKILL.md

Re-read it at the start of each new work session and when the task changes materially. Before modifying code, inspect the authoritative base, open PRs, native ERPNext/Frappe payment/accounting behavior, existing EdgeSuite/shared components, required permission personas/tests and the smallest bounded mergeable slice.

EdgePay may orchestrate payment-provider and product payment workflows, but ERPNext remains authoritative for ERP accounting documents and ledger truth where ERPNext is the accounting system. Product-specific rules may extend the canonical skill but must not silently weaken its governance, permission, workflow, EdgeSuite, testing or PR-discipline requirements.
