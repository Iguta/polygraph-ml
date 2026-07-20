from __future__ import annotations

from polygraphml.domain.models import Audit, Finding, Project


def render_report(audit: Audit, project: Project, findings: list[Finding], audience: str) -> str:
    comparison = audit.metric_comparison
    metric_lines = ["Metric comparison is unavailable."]
    if comparison is not None:
        metric_lines = [f"- Metric: `{comparison.metric}`"]
        for label in ("reported", "reproduced", "corrected"):
            value = getattr(comparison, label)
            rendered = "unavailable" if value is None else f"{value.value:.4f}"
            provenance = "" if value is None else f" — {value.provenance}"
            metric_lines.append(f"- {label.title()}: **{rendered}**{provenance}")

    finding_sections = []
    for finding in findings:
        finding_sections.append(
            "\n".join(
                [
                    f"### {finding.mechanism.value.replace('_', ' ').title()}: {', '.join(finding.features)}",
                    f"- Status: **{finding.status.value}**",
                    f"- Severity: {finding.severity.value}",
                    f"- Conclusion: {finding.conclusion}",
                    f"- What would change this: {finding.what_would_change_this}",
                ]
            )
        )
    findings_text = "\n\n".join(finding_sections) or "No findings were recorded."
    summary = (
        audit.verdict.summary if audit.verdict else "The audit did not produce a final verdict."
    )
    return "\n".join(
        [
            f"# PolygraphML audit: {project.name}",
            "",
            f"**Audience:** {audience}",
            f"**Audit ID:** `{audit.audit_id}`",
            "",
            "## Executive summary",
            "",
            summary,
            "",
            "## Reported, reproduced, and corrected performance",
            "",
            *metric_lines,
            "",
            "## Findings",
            "",
            findings_text,
            "",
            "## Scope and limitations",
            "",
            "This report applies to the submitted artifacts and declared prediction scenario. "
            "It does not guarantee future production performance.",
            "",
        ]
    )
