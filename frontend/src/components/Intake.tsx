import { useRef, useState, type FormEvent } from "react";
import {
  ArrowRight,
  FileArchive,
  GitBranch,
  Sparkles,
  Upload,
} from "lucide-react";

interface Props {
  busy: boolean;
  onBenchmark: () => void;
  onPublicBenchmark: () => void;
  onGithub: (url: string, ref: string) => void;
  onUpload: (files: File[]) => void;
}

export function Intake({
  busy,
  onBenchmark,
  onPublicBenchmark,
  onGithub,
  onUpload,
}: Props) {
  const [repository, setRepository] = useState("");
  const [ref, setRef] = useState("main");
  const fileInput = useRef<HTMLInputElement>(null);

  function submitRepository(event: FormEvent) {
    event.preventDefault();
    onGithub(repository, ref);
  }

  return (
    <section className="intake enter" aria-labelledby="intake-title">
      <div className="hero-copy">
        <p className="eyebrow">
          <Sparkles aria-hidden="true" /> Model QA, with receipts
        </p>
        <h1 id="intake-title">
          Find out whether your model <em>earned</em> its score.
        </h1>
        <p className="hero-lede">
          Audit the model, evaluation data, and notebook together. PolygraphML
          reconstructs the claim, tests likely failure mechanisms, and shows the
          evidence behind every conclusion.
        </p>
        <div className="promise-row" aria-label="Audit guarantees">
          <span>Safe formats only</span>
          <span>Human context included</span>
          <span>Computed corrections</span>
        </div>
      </div>

      <div className="intake-grid">
        <article className="source-card benchmark-card">
          <div className="source-icon">
            <Sparkles aria-hidden="true" />
          </div>
          <p className="card-kicker">Best first run · 90 seconds</p>
          <h2>Try the campaign benchmark</h2>
          <p>
            A model, dataset, and notebook with a subtle post-decision feature.
            Fully reproducible.
          </p>
          <div className="benchmark-actions">
            <button
              className="button primary wide"
              disabled={busy}
              onClick={onBenchmark}
            >
              {busy ? "Preparing evidence…" : "Run the guided benchmark"}
              <ArrowRight aria-hidden="true" />
            </button>
            <button
              className="button ghost wide"
              disabled={busy}
              onClick={onPublicBenchmark}
            >
              Run public UCI COVID clean control
            </button>
          </div>
          <small>
            CC0 synthetic fixture · expected failure declared in advance
          </small>
        </article>

        <article className="source-card">
          <div className="source-icon">
            <GitBranch aria-hidden="true" />
          </div>
          <p className="card-kicker">Public repository</p>
          <h2>Audit from GitHub</h2>
          <p>
            We pin the ref to an immutable commit and inspect only supported
            evidence files.
          </p>
          <form onSubmit={submitRepository} className="stack-form">
            <label>
              Repository URL
              <input
                type="url"
                required
                placeholder="https://github.com/org/project"
                value={repository}
                onChange={(event) => setRepository(event.target.value)}
              />
            </label>
            <label>
              Branch, tag, or commit
              <input
                value={ref}
                onChange={(event) => setRef(event.target.value)}
              />
            </label>
            <button className="button secondary" disabled={busy} type="submit">
              Inspect repository <ArrowRight aria-hidden="true" />
            </button>
          </form>
        </article>

        <article className="source-card">
          <div className="source-icon">
            <Upload aria-hidden="true" />
          </div>
          <p className="card-kicker">Local evidence bundle</p>
          <h2>Upload model evidence</h2>
          <p>
            Choose CSV/Parquet, a safe model artifact, and a notebook. Pickle
            files are rejected.
          </p>
          <input
            ref={fileInput}
            className="sr-only"
            aria-label="Evidence files"
            type="file"
            multiple
            accept=".csv,.parquet,.skops,.json,.ubj,.onnx,.ipynb,.yaml,.yml"
            onChange={(event) => onUpload(Array.from(event.target.files ?? []))}
          />
          <button
            className="button secondary wide"
            disabled={busy}
            onClick={() => fileInput.current?.click()}
          >
            <FileArchive aria-hidden="true" /> Choose evidence files
          </button>
          <small>Dataset-only submissions are clearly labeled preflight.</small>
        </article>
      </div>
    </section>
  );
}
