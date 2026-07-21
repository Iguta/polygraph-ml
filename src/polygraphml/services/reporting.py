from __future__ import annotations

from typing import Literal

from polygraphml.domain.models import Audit, Finding, Project


def render_report(
    audit: Audit,
    project: Project,
    findings: list[Finding],
    audience: Literal["technical", "executive"],
) -> str:
    if audience == "executive":
        return _executive_report(audit, project, findings)
    return _technical_report(audit, project, findings)


def _executive_report(audit: Audit, project: Project, findings: list[Finding]) -> str:
    comparison = audit.metric_comparison
    verdict = audit.verdict
    confirmed = [finding for finding in findings if finding.status.value == "confirmed"]
    limitations = [finding for finding in findings if finding.status.value == "inconclusive"]
    performance = "No comparable performance result was available."
    impact = "No measured correction was available."
    if comparison and comparison.reproduced:
        performance = f"Reproduced {comparison.metric}: **{comparison.reproduced.value:.4f}**."
        if comparison.corrected:
            delta = comparison.reproduced.value - comparison.corrected.value
            performance += f" Corrected {comparison.metric}: **{comparison.corrected.value:.4f}**."
            impact = (
                f"The smallest supported correction reduced the evaluated score by **{delta:.4f}** "
                "under the declared decision scenario."
            )
    issue_lines = [
        f"- {finding.mechanism.value.replace('_', ' ').title()}: {finding.conclusion}"
        for finding in confirmed
    ] or ["- No tested mechanism reached confirmed status."]
    limitation_lines = [
        "- This decision applies only to the submitted artifacts and declared scenario.",
        "- It does not guarantee future production performance.",
        *[f"- {finding.conclusion}" for finding in limitations],
    ]
    return "\n".join(
        [
            f"# Executive decision brief: {project.name}",
            "",
            "## Decision",
            "",
            verdict.summary if verdict else "The audit did not produce a final verdict.",
            "",
            "## Business impact",
            "",
            impact,
            "",
            "## Performance",
            "",
            performance,
            "",
            "## Material findings",
            "",
            *issue_lines,
            "",
            "## Limitations",
            "",
            *limitation_lines,
            "",
        ]
    )


def _technical_report(audit: Audit, project: Project, findings: list[Finding]) -> str:
    comparison = audit.metric_comparison
    metric_lines = ["Metric comparison is unavailable."]
    if comparison is not None:
        metric_lines = [f"- Metric: `{comparison.metric}`"]
        for label in ("reported", "reproduced", "corrected"):
            value = getattr(comparison, label)
            rendered = "unavailable" if value is None else f"{value.value:.4f}"
            detail = (
                ""
                if value is None
                else (
                    f" — protocol `{value.protocol_id}`, tier `{value.reproduction_tier}`, "
                    f"source `{value.provenance}`"
                )
            )
            metric_lines.append(f"- {label.title()}: **{rendered}**{detail}")

    finding_sections = []
    for finding in findings:
        finding_sections.append(
            "\n".join(
                [
                    f"### {finding.mechanism.value.replace('_', ' ').title()}: {', '.join(finding.features) or 'protocol'}",
                    f"- Status: **{finding.status.value}**",
                    f"- Severity: {finding.severity.value}",
                    f"- Confidence: {finding.confidence:.2f}",
                    f"- Evidence IDs: {', '.join(finding.evidence_ids) or 'none'}",
                    f"- Conclusion: {finding.conclusion}",
                    f"- Falsifier / what would change this: {finding.what_would_change_this}",
                ]
            )
        )
    findings_text = "\n\n".join(finding_sections) or "No findings were recorded."
    provenance = audit.provenance
    agent = provenance.agent_execution
    compute = provenance.compute_execution
    agent_lines = ["- Semantic agent execution was not recorded."]
    if agent:
        agent_lines = [
            f"- Mode: `{agent.mode}`",
            f"- Requested model: `{agent.requested_model}`",
            f"- Resolved model: `{agent.resolved_model or 'unavailable'}`",
            f"- Harness: `{agent.harness_version}`",
            f"- Reasoning effort: `{agent.reasoning_effort}`",
            f"- Tokens: input {agent.input_tokens}, output {agent.output_tokens}, total {agent.total_tokens}",
            f"- Latency: {agent.latency_ms} ms",
            f"- Trace ID: `{agent.trace_id or 'unavailable'}`",
        ]
    compute_lines = ["- Compute execution provenance was not recorded."]
    if compute:
        compute_lines = [
            f"- Mode: `{compute.mode}`; security sandbox: `{compute.sandboxed}`",
            f"- Harness: `{compute.harness_version}`",
            f"- Limits: wall {compute.wall_timeout_seconds}s, CPU {compute.cpu_limit_seconds}s, memory {compute.memory_limit_bytes} bytes",
            f"- Rows: train {compute.train_rows}, test {compute.test_rows}, positives {compute.test_positive}, negatives {compute.test_negative}",
        ]
    package_lines = [
        f"- `{name}`: `{version}`" for name, version in sorted(provenance.package_versions.items())
    ] or ["- Package versions unavailable."]
    hash_lines = [f"- `{digest}`" for digest in provenance.artifact_hashes] or [
        "- Artifact hashes unavailable."
    ]
    return "\n".join(
        [
            f"# PolygraphML technical audit: {project.name}",
            "",
            f"**Audit ID:** `{audit.audit_id}`",
            f"**Source commit:** `{provenance.source_commit or 'not applicable'}`",
            f"**Split hash:** `{provenance.split_hash or 'unavailable'}`",
            "",
            "## Reported, reproduced, and corrected performance",
            "",
            *metric_lines,
            "",
            "## Findings and falsifiers",
            "",
            findings_text,
            "",
            "## Evaluation protocol",
            "",
            f"- Scenario revision: {audit.scenario_revision}",
            f"- Reproduction tier: `{audit.reproduction_tier or 'unavailable'}`",
            f"- Feature order: `{', '.join(provenance.feature_order)}`",
            f"- Random seed: {provenance.random_seed}",
            "",
            "## Artifact hashes",
            "",
            *hash_lines,
            "",
            "## Package versions",
            "",
            *package_lines,
            "",
            "## Semantic agent provenance",
            "",
            *agent_lines,
            "",
            "## Deterministic compute provenance",
            "",
            *compute_lines,
            "",
            "## Scope and limitations",
            "",
            "This report applies to the submitted artifacts and declared prediction scenario. "
            "It does not expose raw chain-of-thought and does not guarantee future production "
            "performance. Bounded subprocess execution reduces resource risk but is not a security "
            "sandbox.",
            "",
        ]
    )
