import { Component, ReactNode, ErrorInfo } from 'react';

function ErrorFallback({ error, resetError }: { error: Error | unknown; resetError: () => void; }) {
  const errorMessage = error instanceof Error ? error.message : String(error);
  const errorStack = error instanceof Error ? error.stack : '';
  const componentStack = (error as any)?.componentStack || '';
  const isTelegram = !!(window as any).Telegram?.WebApp?.initData;

  // Log full error to console for debugging
  console.error('[OXYCODE ERROR]', {
    message: errorMessage,
    stack: errorStack,
    componentStack,
    timestamp: new Date().toISOString(),
    url: window.location.href,
  });

  const handleCopyError = () => {
    const text = [
      'OXYCODE AI Error Report',
      '',
      `Time: ${new Date().toISOString()}`,
      `URL: ${window.location.href}`,
      `Telegram: ${isTelegram}`,
      '',
      'Message:',
      errorMessage,
      '',
      'Stack:',
      errorStack || 'N/A',
      '',
      'Component Stack:',
      componentStack || 'N/A',
    ].join('\n');
    navigator.clipboard.writeText(text).catch(() => {});
  };

  return (
    <div className="flex min-h-screen items-center justify-center p-4 bg-[#0a0a0a]">
      <div className="max-w-lg w-full space-y-5 text-center">
        <div className="text-5xl">💥</div>
        <div className="space-y-2">
          <h1 className="text-xl font-bold text-white">Something went wrong</h1>
          <p className="text-neutral-400 text-sm">An unexpected error occurred.</p>
        </div>

        <div className="bg-[#1a1a1a] border border-[#333] p-4 rounded-lg text-left">
          <p className="font-mono text-xs text-red-400 break-all whitespace-pre-wrap leading-relaxed">
            {errorMessage}
          </p>
          {errorStack && (
            <details className="mt-3">
              <summary className="cursor-pointer text-xs text-neutral-500 hover:text-neutral-300">
                Stack trace
              </summary>
              <pre className="mt-2 font-mono text-[10px] text-neutral-600 break-all whitespace-pre-wrap max-h-32 overflow-auto leading-relaxed">
                {errorStack}
              </pre>
            </details>
          )}
        </div>

        <div className="flex gap-3 justify-center flex-wrap">
          <button
            onClick={resetError}
            className="px-5 py-2.5 rounded-lg bg-white text-black font-medium text-sm hover:bg-neutral-200 transition-colors"
          >
            Try Again
          </button>
          <button
            onClick={handleCopyError}
            className="px-5 py-2.5 rounded-lg border border-[#444] text-neutral-300 text-sm hover:bg-[#222] transition-colors"
          >
            Copy Error
          </button>
        </div>

        {isTelegram && (
          <button
            onClick={() => {
              try {
                (window as any).Telegram?.WebApp?.close();
              } catch {}
            }}
            className="text-xs text-neutral-600 hover:text-neutral-400 transition-colors"
          >
            Close Mini App
          </button>
        )}
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
    console.error('[OXYCODE ERRORBOUNDARY] Caught:', error.message);
    console.error('[OXYCODE ERRORBOUNDARY] Stack:', error.stack);
    console.error('[OXYCODE ERRORBOUNDARY] Component Stack:', errorInfo.componentStack);

    // Report to backend for debugging
    try {
      fetch('/api/error', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: error.message,
          stack: error.stack,
          componentStack: errorInfo.componentStack,
          url: window.location.href,
        }),
        keepalive: true,
      }).catch(() => {});
    } catch {}

    // Store last error for debugging
    try {
      localStorage.setItem('oxycode_last_error', JSON.stringify({
        message: error.message,
        stack: error.stack,
        componentStack: errorInfo.componentStack,
        time: new Date().toISOString(),
        url: window.location.href,
      }));
    } catch {}
  }

  render() {
    if (this.state.hasError) {
      return <ErrorFallback error={this.state.error} resetError={() => this.setState({ hasError: false, error: null })} />;
    }
    return this.props.children;
  }
}

export { ErrorFallback };
