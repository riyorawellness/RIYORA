import React from "react";
import { AlertTriangle, RotateCcw, Home } from "lucide-react";

/**
 * Global React error boundary — catches uncaught render errors and shows a
 * friendly fallback with a "Retry" and "Home" button. Wrap the whole App with it.
 */
export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    // In prod you'd ship this to Sentry / your log endpoint
    console.error("[ErrorBoundary]", error, errorInfo);
    this.setState({ errorInfo });
  }

  reset = () => this.setState({ hasError: false, error: null, errorInfo: null });

  render() {
    if (!this.state.hasError) return this.props.children;

    return (
      <div className="grid min-h-screen place-items-center bg-neutral-50 p-6" data-testid="app-error-boundary">
        <div className="max-w-md rounded-2xl border bg-white p-8 shadow-sm">
          <div className="grid h-12 w-12 place-items-center rounded-full bg-red-100 text-red-600">
            <AlertTriangle className="h-6 w-6" />
          </div>
          <h1 className="mt-4 text-2xl font-semibold" style={{ fontFamily: "Fraunces, serif" }}>
            Something went wrong
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            An unexpected error occurred. Please retry — if it persists, contact support.
          </p>
          {this.state.error && (
            <pre className="mt-3 max-h-32 overflow-auto rounded-md bg-neutral-50 p-2 text-[10px] text-red-800">
              {String(this.state.error?.message || this.state.error)}
            </pre>
          )}
          <div className="mt-5 flex gap-2">
            <button
              onClick={this.reset}
              className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:opacity-90"
              data-testid="error-retry-btn"
            >
              <RotateCcw className="h-4 w-4" /> Retry
            </button>
            <a
              href="/"
              className="flex flex-1 items-center justify-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium hover:bg-neutral-50"
              data-testid="error-home-btn"
            >
              <Home className="h-4 w-4" /> Home
            </a>
          </div>
        </div>
      </div>
    );
  }
}
