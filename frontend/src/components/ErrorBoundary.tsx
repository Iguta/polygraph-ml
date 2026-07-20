import { Component, type ErrorInfo, type ReactNode } from "react";
import { RotateCcw, ShieldAlert } from "lucide-react";

interface Props {
  children: ReactNode;
}

interface State {
  failed: boolean;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error(
      "PolygraphML interface failed",
      error.name,
      info.componentStack,
    );
  }

  render(): ReactNode {
    if (!this.state.failed) return this.props.children;
    return (
      <main className="fatal-shell">
        <div className="fatal-card" role="alert">
          <ShieldAlert aria-hidden="true" />
          <p className="eyebrow">Interface recovery</p>
          <h1>The audit is safe. This view needs a reset.</h1>
          <p>
            The backend audit continues independently. Reload to reconnect to
            its durable state.
          </p>
          <button
            className="button primary"
            onClick={() => window.location.reload()}
          >
            <RotateCcw aria-hidden="true" /> Reload workspace
          </button>
        </div>
      </main>
    );
  }
}
