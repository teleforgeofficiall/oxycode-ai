/**
 * Simple Error Boundary — no Sentry dependency
 */

import { Component, ReactNode } from 'react';
import { useNavigate } from 'react-router';
import { AlertCircle } from 'lucide-react';

interface ErrorFallbackProps {
  error: Error | unknown;
  resetError: () => void;
}

function ErrorFallbackInner({ error, resetError, onGoHome }: ErrorFallbackProps & { onGoHome: () => void }) {
  const errorMessage = error instanceof Error ? error.message : 'An unexpected error occurred';
  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <div className="max-w-md w-full space-y-6 text-center">
        <div className="flex justify-center">
          <AlertCircle className="h-16 w-16 text-red-500" />
        </div>
        <div className="space-y-2">
          <h1 className="text-2xl font-bold">Something went wrong</h1>
          <p className="text-muted-foreground">
            An unexpected error occurred.
          </p>
        </div>
        {import.meta.env.DEV && (
          <div className="bg-muted p-4 rounded-lg text-left">
            <p className="font-mono text-sm text-red-600 break-all">
              {errorMessage}
            </p>
          </div>
        )}
        <div className="flex gap-3 justify-center">
          <button onClick={resetError} className="px-4 py-2 bg-primary text-primary-foreground rounded-lg">
            Try Again
          </button>
          <button onClick={onGoHome} className="px-4 py-2 border rounded-lg">
            Go Home
          </button>
        </div>
      </div>
    </div>
  );
}

function ErrorFallback(props: ErrorFallbackProps) {
  const navigate = useNavigate();
  return <ErrorFallbackInner {...props} onGoHome={() => navigate('/')} />;
}

interface ErrorBoundaryProps {
  children: ReactNode;
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

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      return (
        <ErrorFallback
          error={this.state.error}
          resetError={() => this.setState({ hasError: false, error: null })}
        />
      );
    }
    return this.props.children;
  }
}

export { ErrorFallback };
