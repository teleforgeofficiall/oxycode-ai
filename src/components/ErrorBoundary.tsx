import { Component, ReactNode, ErrorInfo } from 'react';

function ErrorFallback({ error, resetError }: { error: Error | unknown; resetError: () => void; }) {
  const errorMessage = error instanceof Error ? error.message : 'An unexpected error occurred';
  return (
    <div className="flex min-h-screen items-center justify-center p-4 bg-kumo-base">
      <div className="max-w-md w-full space-y-6 text-center">
        <div className="text-6xl">!</div>
        <div className="space-y-2">
          <h1 className="text-2xl font-bold text-kumo-default">Something went wrong</h1>
          <p className="text-kumo-subtle">An unexpected error occurred.</p>
        </div>
        {import.meta.env.DEV && (
          <div className="bg-kumo-elevated p-4 rounded-lg text-left">
            <p className="font-mono text-sm text-red-400 break-all">{errorMessage}</p>
          </div>
        )}
        <div className="flex gap-3 justify-center">
          <button onClick={resetError} className="px-4 py-2 rounded-lg bg-kumo-brand text-white">Try Again</button>
          <button onClick={() => window.location.href = '/'} className="px-4 py-2 rounded-lg border border-kumo-line text-kumo-default">Go Home</button>
        </div>
      </div>
    </div>
  );
}

interface ErrorBoundaryProps {
  children: ReactNode;
  showDialog?: boolean;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return <ErrorFallback error={this.state.error} resetError={() => this.setState({ hasError: false, error: null })} />;
    }
    return this.props.children;
  }
}

export { ErrorFallback };
