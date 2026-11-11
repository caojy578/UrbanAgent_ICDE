import { Component, type ErrorInfo, type ReactNode } from 'react';
import { Warning } from '@phosphor-icons/react';
import { Button } from '@/components/primitives/Button';

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

  componentDidCatch(error: Error, info: ErrorInfo) {
    // eslint-disable-next-line no-console
    console.error('[ErrorBoundary]', error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="h-screen w-screen flex items-center justify-center bg-canvas">
        <div className="max-w-md p-8 rounded-lg bg-surface-1 shadow-panel">
          <div className="flex items-center gap-2 text-warn">
            <Warning size={18} weight="duotone" />
            <span className="font-mono text-2xs uppercase tracking-[0.16em]">
              RUNTIME ERROR
            </span>
          </div>
          <h2 className="mt-3 text-base font-semibold text-fg-1">
            指挥中心遭遇异常,已隔离
          </h2>
          <pre className="mt-3 text-xs font-mono text-fg-3 whitespace-pre-wrap break-words max-h-40 overflow-auto">
            {this.state.error.message}
          </pre>
          <div className="mt-4 flex gap-2">
            <Button variant="primary" size="md" onClick={() => location.reload()}>
              重新载入
            </Button>
            <Button size="md" onClick={() => this.setState({ error: null })}>
              尝试恢复
            </Button>
          </div>
        </div>
      </div>
    );
  }
}
