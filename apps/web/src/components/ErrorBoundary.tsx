import { Component, type ErrorInfo, type ReactNode } from "react";
import { DigitSectionMark } from "./DigitSectionMark";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("view error:", error, info.componentStack);
  }

  render(): ReactNode {
    if (this.state.error) {
      return (
        <section className="panel panel-error" role="alert">
          <h2 className="digit-heading">
            <DigitSectionMark role="skeptic" seed="error-title" />
            <span>界面错误</span>
          </h2>
          <p>{this.state.error.message}</p>
          <button
            type="button"
            className="button"
            onClick={() => this.setState({ error: null })}
          >
            重试
          </button>
        </section>
      );
    }
    return this.props.children;
  }
}
