from __future__ import annotations

import hashlib
from pathlib import Path

import nbformat
import numpy as np
import pandas as pd
import skops.io as skops_io
from nbformat.v4 import new_code_cell, new_notebook, new_output
from pydantic import HttpUrl
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

from polygraphml.domain.ids import new_id
from polygraphml.domain.models import (
    AdapterStatus,
    Artifact,
    ArtifactKind,
    ArtifactMapping,
    BenchmarkDefinition,
    BenchmarkExpectation,
    FeatureContext,
    FindingMechanism,
    FindingStatus,
    Project,
    ProjectSource,
    ProjectStatus,
    ReportedMetricSource,
    Scenario,
    SourceType,
)
from polygraphml.errors import PolygraphError
from polygraphml.storage.artifacts import ArtifactStore

SYNTHETIC_BENCHMARK_ID = "synthetic_campaign_leak_v1"
POST_OUTCOME_BENCHMARK_ID = "synthetic_post_outcome_only_v1"
GROUP_CONTAMINATION_BENCHMARK_ID = "synthetic_group_contamination_only_v1"
COVID_BENCHMARK_ID = "uci_covid_surveillance_clean_v1"
UCI_BANK_BENCHMARK_ID = "uci_bank_marketing_duration_v1"
TARGET_PROXY_BENCHMARK_ID = "synthetic_semantic_proxy_v1"
HARD_NEGATIVE_BENCHMARK_ID = "synthetic_suspicious_hard_negative_v1"
UCI_BANK_SOURCE = "https://archive.ics.uci.edu/dataset/222/bank%2Bmarketing"
UCI_BANK_ARTIFACT_HASHES = {
    "bank_marketing_evaluation.csv": "060671f9dcf10dbf76cda0dec39e8ab1b9c0787c4b93e31f1ca7fab95c508b39",
    "bank_marketing_model.skops": "5c23908310184d18ce20f5a40cd2f16e19455ff7c9029d5fa86268b0e3ac8d90",
    "bank_marketing_evaluation.ipynb": "365fac335a5e0b430ab42e591da7660713f1979b680bdc5451132c116d782af1",
    "derivation.txt": "61563a20dec3f395d2c57c9c673bdb744b71fc5f453c4d121a4f69b181c09d34",
}
COVID_SOURCE = """A01,A02,A03,A04,A05,A06,A07,Categories
+,+,+,+,+,-,-,PUS
+,+,-,+,+,-,-,PUS
+,+,+,+,-,+,-,PUS
+,+,-,+,-,+,-,PUS
+,-,-,-,-,-,+,PUS
+,+,+,-,-,-,+,PUS
+,+,-,-,-,-,+,PUS
+,+,+,+,-,-,-,PUS
+,-,-,+,+,-,-,PIM
-,+,-,+,+,-,-,PIM
+,-,-,+,-,+,-,PIM
-,+,-,+,-,+,-,PIM
-,+,-,-,-,-,+,PIM
-,-,-,-,-,-,+,PWS
"""


class BenchmarkCatalog:
    def definitions(self) -> list[BenchmarkDefinition]:
        return [
            self._uci_bank_definition(),
            self._definition(),
            self._definition(POST_OUTCOME_BENCHMARK_ID),
            self._definition(GROUP_CONTAMINATION_BENCHMARK_ID),
            self._definition(TARGET_PROXY_BENCHMARK_ID),
            self._definition(HARD_NEGATIVE_BENCHMARK_ID),
            self._covid_definition(),
        ]

    def get(self, benchmark_id: str) -> BenchmarkDefinition:
        if benchmark_id in {
            SYNTHETIC_BENCHMARK_ID,
            POST_OUTCOME_BENCHMARK_ID,
            GROUP_CONTAMINATION_BENCHMARK_ID,
            TARGET_PROXY_BENCHMARK_ID,
            HARD_NEGATIVE_BENCHMARK_ID,
        }:
            return self._definition(benchmark_id)
        if benchmark_id == UCI_BANK_BENCHMARK_ID:
            return self._uci_bank_definition()
        if benchmark_id == COVID_BENCHMARK_ID:
            return self._covid_definition()
        raise PolygraphError("INVALID_REQUEST", "Benchmark was not found.", status_code=404)

    def materialize(
        self,
        benchmark_id: str,
        project_id: str,
        session_id: str,
        store: ArtifactStore,
    ) -> tuple[Project, list[Artifact]]:
        definition = self.get(benchmark_id)
        if benchmark_id == COVID_BENCHMARK_ID:
            return self._materialize_covid(project_id, session_id, store)
        if benchmark_id == UCI_BANK_BENCHMARK_ID:
            return self._materialize_uci_bank(project_id, session_id, store)
        rng = np.random.default_rng(42)
        rows = 600
        monthly_spend = rng.normal(75, 18, rows).clip(15, 160)
        tenure_months = rng.integers(1, 84, rows)
        support_tickets = rng.poisson(2.2, rows)
        latent = (
            0.025 * (monthly_spend - 75)
            - 0.018 * (tenure_months - 36)
            + 0.22 * support_tickets
            + rng.normal(0, 1.0, rows)
        )
        target = (latent > np.quantile(latent, 0.58)).astype(int)
        if benchmark_id == TARGET_PROXY_BENCHMARK_ID:
            semantic_feature = "engagement_band"
            semantic_values = target.copy()
        elif benchmark_id == HARD_NEGATIVE_BENCHMARK_ID:
            semantic_feature = "previous_call_duration"
            semantic_values = 125 + 35 * latent + rng.normal(0, 25, rows)
        else:
            semantic_feature = "call_duration"
            semantic_values = 95 + 240 * target + rng.normal(0, 20, rows)
        indices = rng.permutation(rows)
        split = np.full(rows, "train", dtype=object)
        split[indices[int(rows * 0.72) :]] = "test"
        frame = pd.DataFrame(
            {
                "customer_id": [f"C{index:05d}" for index in range(rows)],
                "household_id": [f"H{index // 2:05d}" for index in range(rows)],
                "monthly_spend": monthly_spend.round(2),
                "tenure_months": tenure_months,
                "support_tickets": support_tickets,
                semantic_feature: np.asarray(semantic_values).round(1),
                "churned": target,
                "split": split,
            }
        )
        features = ["monthly_spend", "tenure_months", "support_tickets", semantic_feature]
        train = frame["split"] == "train"
        test = frame["split"] == "test"
        model = LogisticRegression(max_iter=1000, random_state=42)
        model.fit(frame.loc[train, features], frame.loc[train, "churned"])
        reported_auc = float(
            roc_auc_score(
                frame.loc[test, "churned"], model.predict_proba(frame.loc[test, features])[:, 1]
            )
        )

        project_root = store.root / project_id / "benchmark"
        project_root.mkdir(parents=True, exist_ok=True)
        dataset_path = project_root / "campaign_evaluation.csv"
        model_path = project_root / "campaign_model.skops"
        notebook_path = project_root / "training.ipynb"
        frame.to_csv(dataset_path, index=False)
        skops_io.dump(model, model_path)
        notebook = new_notebook(
            cells=[
                new_code_cell(
                    "import pandas as pd\n"
                    "from sklearn.linear_model import LogisticRegression\n"
                    "from sklearn.metrics import roc_auc_score\n"
                    "df = pd.read_csv('campaign_evaluation.csv')"
                ),
                new_code_cell(
                    "features = ['monthly_spend', 'tenure_months', "
                    f"'support_tickets', '{semantic_feature}']\n"
                    "train = df['split'] == 'train'\n"
                    "test = df['split'] == 'test'\n"
                    "model = LogisticRegression(max_iter=1000, random_state=42)\n"
                    "model.fit(df.loc[train, features], df.loc[train, 'churned'])"
                ),
                new_code_cell(
                    "auc = roc_auc_score(df.loc[test, 'churned'], "
                    "model.predict_proba(df.loc[test, features])[:, 1])\n"
                    "print(f'AUC: {auc:.6f}')",
                    outputs=[
                        new_output(
                            output_type="stream",
                            name="stdout",
                            text=f"AUC: {reported_auc:.6f}\n",
                        )
                    ],
                    execution_count=3,
                ),
            ]
        )
        nbformat.write(notebook, notebook_path)

        storage_keys = {
            path: f"{project_id}/benchmark/{path.name}"
            for path in (dataset_path, model_path, notebook_path)
        }
        for path, storage_key in storage_keys.items():
            store.write(storage_key, path.read_bytes(), 100 * 1024 * 1024)

        artifacts = [
            self._artifact(
                project_id,
                dataset_path,
                storage_keys[dataset_path],
                benchmark_id,
                ArtifactKind.DATASET,
                "csv",
                AdapterStatus.SUPPORTED,
            ),
            self._artifact(
                project_id,
                model_path,
                storage_keys[model_path],
                benchmark_id,
                ArtifactKind.MODEL,
                "skops",
                AdapterStatus.SUPPORTED,
            ),
            self._artifact(
                project_id,
                notebook_path,
                storage_keys[notebook_path],
                benchmark_id,
                ArtifactKind.NOTEBOOK,
                "ipynb-static",
                AdapterStatus.SUPPORTED,
            ),
        ]
        by_kind = {artifact.kind: artifact for artifact in artifacts}
        project = Project(
            project_id=project_id,
            session_id=session_id,
            name=(
                "Campaign timing benchmark"
                if benchmark_id == SYNTHETIC_BENCHMARK_ID
                else definition.name
            ),
            source=ProjectSource(type=SourceType.BENCHMARK, benchmark_id=benchmark_id),
            status=ProjectStatus.READY,
            artifact_ids=[artifact.artifact_id for artifact in artifacts],
            mapping=ArtifactMapping(
                dataset_artifact_id=by_kind[ArtifactKind.DATASET].artifact_id,
                model_artifact_id=by_kind[ArtifactKind.MODEL].artifact_id,
                notebook_artifact_id=by_kind[ArtifactKind.NOTEBOOK].artifact_id,
                target_column="churned",
                entity_column=definition.scenario.split_unit,
                split_column="split",
                reported_metric_source=ReportedMetricSource(
                    artifact_id=by_kind[ArtifactKind.NOTEBOOK].artifact_id,
                    location="training.ipynb#cell=2",
                ),
            ),
            scenarios=[definition.scenario],
            feature_context={
                semantic_feature: FeatureContext(
                    description=(
                        "An engagement segment code included in the submitted evaluation table."
                        if benchmark_id == TARGET_PROXY_BENCHMARK_ID
                        else "Duration of a completed previous campaign call."
                        if benchmark_id == HARD_NEGATIVE_BENCHMARK_ID
                        else "Duration of the current campaign call."
                    ),
                    source_refs=[f"benchmark:{benchmark_id}/data-dictionary"],
                )
            },
        )
        return project, artifacts

    def _materialize_uci_bank(
        self,
        project_id: str,
        session_id: str,
        store: ArtifactStore,
    ) -> tuple[Project, list[Artifact]]:
        definition = self._uci_bank_definition()
        source_root = Path(__file__).parent / "data" / "uci_bank"
        specifications = (
            ("bank_marketing_evaluation.csv", ArtifactKind.DATASET, "csv"),
            ("bank_marketing_model.skops", ArtifactKind.MODEL, "skops"),
            ("bank_marketing_evaluation.ipynb", ArtifactKind.NOTEBOOK, "ipynb-static"),
            ("derivation.txt", ArtifactKind.SOURCE, "static-source"),
        )
        artifacts: list[Artifact] = []
        for filename, kind, adapter in specifications:
            source_path = source_root / filename
            content = source_path.read_bytes()
            digest = hashlib.sha256(content).hexdigest()
            if digest != UCI_BANK_ARTIFACT_HASHES[filename]:
                raise PolygraphError(
                    "INVALID_ARTIFACT", "Pinned UCI Bank benchmark artifact hash changed."
                )
            storage_key = f"{project_id}/benchmark/{filename}"
            store.write(storage_key, content, 100 * 1024 * 1024)
            artifacts.append(
                self._artifact(
                    project_id,
                    source_path,
                    storage_key,
                    UCI_BANK_BENCHMARK_ID,
                    kind,
                    adapter,
                    AdapterStatus.SUPPORTED,
                )
            )
        by_kind = {artifact.kind: artifact for artifact in artifacts}
        project = Project(
            project_id=project_id,
            session_id=session_id,
            name=definition.name,
            source=ProjectSource(type=SourceType.BENCHMARK, benchmark_id=UCI_BANK_BENCHMARK_ID),
            status=ProjectStatus.READY,
            artifact_ids=[artifact.artifact_id for artifact in artifacts],
            mapping=ArtifactMapping(
                dataset_artifact_id=by_kind[ArtifactKind.DATASET].artifact_id,
                model_artifact_id=by_kind[ArtifactKind.MODEL].artifact_id,
                notebook_artifact_id=by_kind[ArtifactKind.NOTEBOOK].artifact_id,
                target_column="subscribed",
                entity_column="row_id",
                split_column="split",
                reported_metric_source=ReportedMetricSource(
                    artifact_id=by_kind[ArtifactKind.NOTEBOOK].artifact_id,
                    location="bank_marketing_evaluation.ipynb#cell=3",
                ),
            ),
            scenarios=[definition.scenario],
            feature_context={
                "duration": FeatureContext(
                    description="Duration in seconds of the current campaign's last contact",
                    source_refs=[f"{UCI_BANK_SOURCE}#Additional-Variable-Information"],
                ),
                "poutcome": FeatureContext(
                    description="Outcome of the previous marketing campaign",
                    source_refs=[f"{UCI_BANK_SOURCE}#Additional-Variable-Information"],
                ),
            },
        )
        return project, artifacts

    @staticmethod
    def _artifact(
        project_id: str,
        path: Path,
        storage_key: str,
        benchmark_id: str,
        kind: ArtifactKind,
        adapter: str,
        status: AdapterStatus,
    ) -> Artifact:
        content = path.read_bytes()
        return Artifact(
            artifact_id=new_id("art"),
            project_id=project_id,
            kind=kind,
            filename=path.name,
            sha256=hashlib.sha256(content).hexdigest(),
            size_bytes=len(content),
            media_type="application/octet-stream",
            storage_key=storage_key,
            adapter=adapter,
            adapter_status=status,
            source_ref=f"benchmark:{benchmark_id}/{path.name}",
        )

    def _materialize_covid(
        self,
        project_id: str,
        session_id: str,
        store: ArtifactStore,
    ) -> tuple[Project, list[Artifact]]:
        from io import StringIO

        frame = pd.read_csv(StringIO(COVID_SOURCE))
        features = [f"A0{index}" for index in range(1, 8)]
        frame[features] = frame[features].replace({"+": 1, "-": 0}).astype(int)
        frame["suspected_case"] = (frame["Categories"] == "PUS").astype(int)
        frame.insert(0, "case_id", [f"UCI-{index:02d}" for index in range(len(frame))])
        frame["split"] = "train"
        frame.loc[[0, 2, 8, 13], "split"] = "test"
        train = frame["split"] == "train"
        test = frame["split"] == "test"
        model = LogisticRegression(max_iter=1000, random_state=42)
        model.fit(frame.loc[train, features], frame.loc[train, "suspected_case"])
        reported_auc = float(
            roc_auc_score(
                frame.loc[test, "suspected_case"],
                model.predict_proba(frame.loc[test, features])[:, 1],
            )
        )

        project_root = store.root / project_id / "benchmark"
        project_root.mkdir(parents=True, exist_ok=True)
        dataset_path = project_root / "uci_covid_surveillance.csv"
        model_path = project_root / "covid_surveillance_model.skops"
        notebook_path = project_root / "covid_surveillance.ipynb"
        frame.to_csv(dataset_path, index=False)
        skops_io.dump(model, model_path)
        notebook = new_notebook(
            metadata={
                "polygraphml": {
                    "source": "https://doi.org/10.24432/C5TC85",
                    "license": "CC BY 4.0",
                }
            },
            cells=[
                new_code_cell(
                    "import pandas as pd\n"
                    "from sklearn.linear_model import LogisticRegression\n"
                    "from sklearn.metrics import roc_auc_score\n"
                    "df = pd.read_csv('uci_covid_surveillance.csv')"
                ),
                new_code_cell(
                    f"features = {features!r}\n"
                    "train = df['split'] == 'train'\n"
                    "test = df['split'] == 'test'\n"
                    "model = LogisticRegression(max_iter=1000, random_state=42)\n"
                    "model.fit(df.loc[train, features], df.loc[train, 'suspected_case'])"
                ),
                new_code_cell(
                    "auc = roc_auc_score(df.loc[test, 'suspected_case'], "
                    "model.predict_proba(df.loc[test, features])[:, 1])\n"
                    "print(f'AUC: {auc:.6f}')",
                    outputs=[
                        new_output(
                            output_type="stream",
                            name="stdout",
                            text=f"AUC: {reported_auc:.6f}\n",
                        )
                    ],
                    execution_count=3,
                ),
            ],
        )
        nbformat.write(notebook, notebook_path)
        storage_keys = {
            path: f"{project_id}/benchmark/{path.name}"
            for path in (dataset_path, model_path, notebook_path)
        }
        for path, storage_key in storage_keys.items():
            store.write(storage_key, path.read_bytes(), 100 * 1024 * 1024)
        artifacts = [
            self._artifact(
                project_id,
                dataset_path,
                storage_keys[dataset_path],
                COVID_BENCHMARK_ID,
                ArtifactKind.DATASET,
                "csv",
                AdapterStatus.SUPPORTED,
            ),
            self._artifact(
                project_id,
                model_path,
                storage_keys[model_path],
                COVID_BENCHMARK_ID,
                ArtifactKind.MODEL,
                "skops",
                AdapterStatus.SUPPORTED,
            ),
            self._artifact(
                project_id,
                notebook_path,
                storage_keys[notebook_path],
                COVID_BENCHMARK_ID,
                ArtifactKind.NOTEBOOK,
                "ipynb-static",
                AdapterStatus.SUPPORTED,
            ),
        ]
        by_kind = {artifact.kind: artifact for artifact in artifacts}
        project = Project(
            project_id=project_id,
            session_id=session_id,
            name="UCI COVID-19 surveillance clean control",
            source=ProjectSource(type=SourceType.BENCHMARK, benchmark_id=COVID_BENCHMARK_ID),
            status=ProjectStatus.READY,
            artifact_ids=[artifact.artifact_id for artifact in artifacts],
            mapping=ArtifactMapping(
                dataset_artifact_id=by_kind[ArtifactKind.DATASET].artifact_id,
                model_artifact_id=by_kind[ArtifactKind.MODEL].artifact_id,
                notebook_artifact_id=by_kind[ArtifactKind.NOTEBOOK].artifact_id,
                target_column="suspected_case",
                entity_column="case_id",
                split_column="split",
                reported_metric_source=ReportedMetricSource(
                    artifact_id=by_kind[ArtifactKind.NOTEBOOK].artifact_id,
                    location="covid_surveillance.ipynb#cell=2",
                ),
            ),
            scenarios=[self._covid_definition().scenario],
        )
        return project, artifacts

    @staticmethod
    def _definition(
        benchmark_id: str = SYNTHETIC_BENCHMARK_ID,
    ) -> BenchmarkDefinition:
        includes_post_outcome = benchmark_id not in {
            GROUP_CONTAMINATION_BENCHMARK_ID,
            TARGET_PROXY_BENCHMARK_ID,
            HARD_NEGATIVE_BENCHMARK_ID,
        }
        includes_group_contamination = benchmark_id not in {
            POST_OUTCOME_BENCHMARK_ID,
            TARGET_PROXY_BENCHMARK_ID,
            HARD_NEGATIVE_BENCHMARK_ID,
        }
        names = {
            SYNTHETIC_BENCHMARK_ID: "Campaign timing leak",
            POST_OUTCOME_BENCHMARK_ID: "Post-outcome feature only",
            GROUP_CONTAMINATION_BENCHMARK_ID: "Group contamination only",
            TARGET_PROXY_BENCHMARK_ID: "Semantic target-proxy",
            HARD_NEGATIVE_BENCHMARK_ID: "Suspicious-looking hard negative",
        }
        expectations = []
        if includes_post_outcome:
            expectations.append(
                BenchmarkExpectation(
                    mechanism=FindingMechanism.POST_OUTCOME,
                    feature="call_duration",
                    expected_status=FindingStatus.CONFIRMED,
                )
            )
        if includes_group_contamination:
            expectations.append(
                BenchmarkExpectation(
                    mechanism=FindingMechanism.GROUP_CONTAMINATION,
                    feature="household_id",
                    expected_status=FindingStatus.CONFIRMED,
                )
            )
        if benchmark_id == TARGET_PROXY_BENCHMARK_ID:
            expectations.append(
                BenchmarkExpectation(
                    mechanism=FindingMechanism.TARGET_PROXY,
                    feature="engagement_band",
                    expected_status=FindingStatus.CONFIRMED,
                )
            )
        return BenchmarkDefinition(
            benchmark_id=benchmark_id,
            name=names[benchmark_id],
            description=(
                "Deterministic model-plus-data-plus-notebook campaign case. The scenario and mapping "
                "isolate the registry's predeclared finding mechanisms."
            ),
            license_name="CC0-1.0",
            version="1.0.0",
            artifact_manifest={
                ArtifactKind.DATASET: "campaign_evaluation.csv",
                ArtifactKind.MODEL: "campaign_model.skops",
                ArtifactKind.NOTEBOOK: "training.ipynb",
            },
            artifact_hashes={
                "generation_spec_sha256": hashlib.sha256(
                    f"{benchmark_id}-seed-42".encode()
                ).hexdigest()
            },
            scenario=Scenario(
                revision=1,
                target_definition="Customer churns within 30 days",
                row_entity="One customer campaign snapshot",
                decision_time="Before the campaign chooses whom to call",
                prediction_horizon="30 days",
                split_unit=("household_id" if includes_group_contamination else "customer_id"),
                intended_metric="roc_auc",
                positive_label="1",
                notes=(
                    "The engagement-band provenance must be confirmed by the user."
                    if benchmark_id == TARGET_PROXY_BENCHMARK_ID
                    else "Previous-call duration is fixed before the current decision."
                    if benchmark_id == HARD_NEGATIVE_BENCHMARK_ID
                    else "Call-duration availability must be confirmed by the user."
                ),
            ),
            expectations=expectations,
            metric_tolerance=0.005,
            expected_corrected_metric=(
                0.8145254629629629
                if benchmark_id == TARGET_PROXY_BENCHMARK_ID
                else 0.8627956989247312
                if includes_post_outcome
                else None
            ),
            prohibited_claims=[
                "This synthetic benchmark proves performance on a real campaign.",
                "The corrected score guarantees production performance.",
            ],
            fixture=True,
        )

    @staticmethod
    def _uci_bank_definition() -> BenchmarkDefinition:
        return BenchmarkDefinition(
            benchmark_id=UCI_BANK_BENCHMARK_ID,
            name="UCI Bank Marketing current-call duration",
            description=(
                "Pinned full public UCI Bank Marketing dataset, trained model, and notebook. "
                "The declared use case scores a client before the current call begins."
            ),
            source_url=HttpUrl(UCI_BANK_SOURCE),
            license_name="CC BY 4.0",
            license_url=HttpUrl("https://creativecommons.org/licenses/by/4.0/"),
            version="uci-2012+polygraphml-1.0.0",
            artifact_manifest={
                ArtifactKind.DATASET: "bank_marketing_evaluation.csv",
                ArtifactKind.MODEL: "bank_marketing_model.skops",
                ArtifactKind.NOTEBOOK: "bank_marketing_evaluation.ipynb",
                ArtifactKind.SOURCE: "derivation.txt",
            },
            artifact_hashes=UCI_BANK_ARTIFACT_HASHES,
            scenario=Scenario(
                revision=1,
                target_definition="Whether the client subscribes to a term deposit",
                row_entity="One client contact in a direct-marketing campaign",
                decision_time="Before the current marketing call begins",
                prediction_horizon="Response to the current marketing contact",
                split_unit="row_id",
                intended_metric="roc_auc",
                positive_label="1",
                notes=(
                    "UCI Bank Marketing, DOI 10.24432/C5K306; all 45,211 source rows are "
                    "retained in the deterministic derived evaluation table."
                ),
            ),
            expectations=[
                BenchmarkExpectation(
                    mechanism=FindingMechanism.POST_OUTCOME,
                    feature="duration",
                    expected_status=FindingStatus.CONFIRMED,
                )
            ],
            metric_tolerance=0.005,
            expected_corrected_metric=0.7330845871361364,
            prohibited_claims=[
                "The corrected score proves future production performance.",
                "Current-call duration is available before the call begins.",
            ],
            fixture=False,
        )

    @staticmethod
    def _covid_definition() -> BenchmarkDefinition:
        return BenchmarkDefinition(
            benchmark_id=COVID_BENCHMARK_ID,
            name="UCI COVID-19 surveillance clean control",
            description=(
                "Public CC BY 4.0 symptom-classification dataset, paired with a reproducible "
                "PolygraphML model and notebook as a clean control."
            ),
            source_url=HttpUrl("https://archive.ics.uci.edu/dataset/567/covid%2B19%2Bsurveillance"),
            license_name="CC BY 4.0",
            license_url=HttpUrl("https://creativecommons.org/licenses/by/4.0/"),
            version="uci-2020+polygraphml-1.0.0",
            artifact_manifest={
                ArtifactKind.DATASET: "uci_covid_surveillance.csv",
                ArtifactKind.MODEL: "covid_surveillance_model.skops",
                ArtifactKind.NOTEBOOK: "covid_surveillance.ipynb",
            },
            artifact_hashes={
                "source_csv_sha256": hashlib.sha256(COVID_SOURCE.encode()).hexdigest()
            },
            scenario=Scenario(
                revision=1,
                target_definition="A surveillance record is classified as a suspected COVID-19 case",
                row_entity="One public surveillance symptom pattern",
                decision_time="At initial symptom screening, before a diagnostic outcome",
                prediction_horizon="Current screening encounter",
                split_unit="case_id",
                intended_metric="roc_auc",
                positive_label="1",
                notes=(
                    "Source: UCI DOI 10.24432/C5TC85. This 14-row teaching dataset is not a "
                    "clinical diagnostic validation set."
                ),
            ),
            expectations=[],
            metric_tolerance=0.005,
            prohibited_claims=[
                "This benchmark validates clinical diagnostic performance.",
                "No confirmed tested mechanism proves the model is universally leakage-free.",
            ],
            fixture=False,
        )
