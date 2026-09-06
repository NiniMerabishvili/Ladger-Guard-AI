import { Component, type ErrorInfo, type ReactNode } from "react";
import { panelError } from "../lib/ui";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

export class RouteErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("Route render failed", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <p className={panelError}>
          This page crashed: {this.state.error.message}. Try refreshing, or open Projects and pick
          the project again.
        </p>
      );
    }
    return this.props.children;
  }
}
