import { Component, ReactNode, ErrorInfo } from 'react';

function ErrorFallback({ error, resetError }: { error: Error | unknown; resetError: () => void; }) {
  const errorMessage = error instanceof Error ? error.message : 'An unexpected error occurred';
  const errorStack = error instanceof Error ? error.stack : '';
  const isTelegram = !!(window as any).Telegram?.WebApp?.initData;

  const handleCopyError = () => {
    const text = `OXYCODE AI Error\n\nMessage: ${errorMessage}\n\nStack:\n${errorStack}`;
    navigator.clipboard.writeText(text).catch(() => {});
  };

  return (
    <div className="flex min-h-screen items-center justify-center p-4 bg-kumo-base">
      <div className="max-w-md w-full space-y-6 text-center">
        <div className="text-6xl">!</div>
        <div className="space-y-2">
          <h1 className="text-2xl font-bold text-kumo-default">Something went wrong</h1>
          <p className="text-kumo-subtle">An unexpected error occurred.</p>
        </div>
        <details className="bg-kumo-elevated p-4 rounded-lg text-left">
          <summary className="cursor-pointer text-sm text-kumo-subtle hover:text-kumo-default mb-2">
            Error details
          </summary>
          <p className="font-mono text-sm text-red-400 break-all whitespace-pre-wrap">{errorMessage}</p>
          {errorStack && (
            <pre className="mt-2 font-mono text-xs text-neutral-500 break-all whitespace-pre-wrap max-h-40 overflow-auto">
              {errorStack}
            </pre>
          )}
        </details>
        <div className="flex gap-3 justify-center flex-wrap">
          <button onClick={resetError} className="px-4 py-2 rounded-lg bg-kumo-brand text-white">Try Again</button>
          <button onClick={handleCopyError} className="px-4 py-2 rounded-lg border border-kumo-line text-kumo-default">Copy Error</button>
          {!isTelegram && (
            <a
              href="https://t.me/OXYCODE_AI_BOT?startapp"
              className="px-4 py-2 rounded-lg bg-[#2AABEE] text-white text-sm"
            >
              Open in Telegram
            </a>
          )}
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
