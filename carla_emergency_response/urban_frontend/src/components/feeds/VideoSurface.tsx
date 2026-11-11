import { useEffect, useRef, useState } from 'react';
import { cn } from '@/lib/cn';
import { PlaceholderScene } from './PlaceholderScene';
import { Button } from '@/components/primitives/Button';
import { Input } from '@/components/primitives/Input';
import { Plug, X, Broadcast, FileVideo, Image as ImageIcon } from '@phosphor-icons/react';
import { connectWebRTC, type WebRTCSession } from '@/services/webrtc';

export type VideoMode = 'placeholder' | 'mjpeg' | 'webrtc' | 'video' | 'local';

interface Props {
  variant: 'aerial' | 'ground' | 'city';
  label?: string;
  className?: string;
  /** Optional default URL (env-provided). */
  defaultUrl?: string;
  /** Default protocol when defaultUrl is set. Auto-detects video files by extension. */
  defaultMode?: 'mjpeg' | 'webrtc' | 'video';
}

const VIDEO_FILE_EXT = /\.(mp4|webm|mov|m4v|ogv)(\?|$)/i;
/** Paths like /webrtc/aerial or webrtc://... use RTCPeerConnection, not <img>. */
const WEBRTC_PATH = /(^|\/)webrtc(\/|$)/i;
function autoMode(url: string, fallback: 'mjpeg' | 'webrtc' | 'video'): VideoMode {
  if (VIDEO_FILE_EXT.test(url)) return 'video';
  if (url.toLowerCase().startsWith('webrtc://') || WEBRTC_PATH.test(url)) return 'webrtc';
  return fallback;
}

const protoOptions: { mode: VideoMode; label: string; icon: typeof Plug }[] = [
  { mode: 'mjpeg', label: 'MJPEG', icon: ImageIcon },
  { mode: 'webrtc', label: 'WEBRTC', icon: Broadcast },
  { mode: 'video', label: 'VIDEO', icon: FileVideo },
  { mode: 'local', label: 'LOCAL', icon: FileVideo },
];

export function VideoSurface({
  variant,
  label,
  className,
  defaultUrl,
  defaultMode = 'mjpeg',
}: Props) {
  const [mode, setMode] = useState<VideoMode>(
    defaultUrl ? autoMode(defaultUrl, defaultMode) : 'placeholder',
  );
  const [url, setUrl] = useState(defaultUrl ?? '');
  const [draftUrl, setDraftUrl] = useState('');
  const [draftProto, setDraftProto] = useState<'mjpeg' | 'webrtc' | 'video'>(defaultMode);
  const [showInput, setShowInput] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const sessionRef = useRef<WebRTCSession | null>(null);

  // WebRTC lifecycle
  useEffect(() => {
    if (mode !== 'webrtc' || !url) return;
    let cancelled = false;
    setError(null);
    connectWebRTC(url)
      .then((session) => {
        if (cancelled) {
          session.close();
          return;
        }
        sessionRef.current = session;
        if (videoRef.current) {
          videoRef.current.srcObject = session.stream;
          videoRef.current.play().catch(() => {});
        }
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err.message ?? 'WebRTC failed');
        setMode('placeholder');
      });
    return () => {
      cancelled = true;
      sessionRef.current?.close();
      sessionRef.current = null;
      if (videoRef.current) videoRef.current.srcObject = null;
    };
  }, [mode, url]);

  // Local / video URL lifecycle
  useEffect(() => {
    if ((mode !== 'local' && mode !== 'video') || !url) return;
    if (videoRef.current) {
      videoRef.current.srcObject = null;
      videoRef.current.src = url;
      videoRef.current.play().catch(() => {});
    }
  }, [mode, url]);

  const apply = (next: string, proto: 'mjpeg' | 'webrtc' | 'video') => {
    if (!next) return;
    setUrl(next);
    // Auto-detect video files even if user chose mjpeg.
    setMode(autoMode(next, proto));
    setShowInput(false);
    setError(null);
  };

  const reset = () => {
    if (mode === 'local' && url.startsWith('blob:')) URL.revokeObjectURL(url);
    sessionRef.current?.close();
    sessionRef.current = null;
    setUrl('');
    setMode('placeholder');
    setError(null);
  };

  const ChipIcon = protoOptions.find((p) => p.mode === mode)?.icon ?? Plug;

  return (
    <div className={cn('relative w-full h-full bg-canvas overflow-hidden', className)}>
      {mode === 'placeholder' && <PlaceholderScene variant={variant} label={label} />}

      {mode === 'mjpeg' && (
        <img
          src={url}
          alt={label ?? variant}
          className="w-full h-full object-cover"
          onError={() => {
            setError('MJPEG stream unreachable');
            setMode('placeholder');
          }}
        />
      )}

      {(mode === 'webrtc' || mode === 'local' || mode === 'video') && (
        <video
          ref={videoRef}
          autoPlay
          muted
          loop={mode === 'local' || mode === 'video'}
          playsInline
          className="w-full h-full object-cover bg-surface-3"
          onError={() => {
            if (mode !== 'webrtc') {
              setError('Video unreachable');
              setMode('placeholder');
            }
          }}
        />
      )}

      {/* Status chip */}
      {mode !== 'placeholder' && (
        <button
          onClick={reset}
          className="absolute top-3 right-3 inline-flex items-center gap-1.5 h-6 px-2 rounded-full glass text-2xs font-mono uppercase tracking-[0.08em] text-fg-2 hover:text-fg-1 transition-colors duration-140"
          title="断开"
        >
          <span className="size-1.5 rounded-full bg-ok animate-breathe" />
          <ChipIcon size={10} weight="bold" />
          {mode.toUpperCase()}
          <X size={10} className="ml-1 opacity-60" />
        </button>
      )}

      {/* Connect popover */}
      {mode === 'placeholder' && (
        <div className="absolute right-3 top-3">
          {!showInput ? (
            <button
              onClick={() => setShowInput(true)}
              className="inline-flex items-center gap-1.5 h-6 px-2 rounded-full glass text-2xs font-mono uppercase tracking-[0.08em] text-fg-2 hover:text-fg-1 transition-colors duration-140"
            >
              <Plug size={10} />
              CONNECT
            </button>
          ) : (
            <div className="flex flex-col gap-1.5 p-2 rounded-md glass w-[320px]">
              <div className="flex gap-1">
                {(['mjpeg', 'webrtc', 'video'] as const).map((p) => (
                  <button
                    key={p}
                    onClick={() => setDraftProto(p)}
                    className={cn(
                      'flex-1 h-6 rounded font-mono text-2xs uppercase tracking-[0.08em] transition-all duration-140',
                      draftProto === p
                        ? 'bg-accent/16 text-accent border border-accent/30'
                        : 'bg-surface-2 text-fg-3 border border-hairline hover:text-fg-1',
                    )}
                  >
                    {p}
                  </button>
                ))}
              </div>
              <div className="flex items-center gap-1.5">
                <Input
                  placeholder={
                    draftProto === 'mjpeg'
                      ? '/video_feed?camera=...'
                      : draftProto === 'webrtc'
                        ? '/webrtc/offer'
                        : '/media/sample.mp4'
                  }
                  value={draftUrl}
                  onChange={(e) => setDraftUrl(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') apply(draftUrl, draftProto);
                    if (e.key === 'Escape') setShowInput(false);
                  }}
                  className="h-7 text-xs font-mono"
                  autoFocus
                />
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => apply(draftUrl, draftProto)}
                >
                  连接
                </Button>
              </div>
              <div className="flex items-center justify-between">
                <input
                  type="file"
                  accept="video/*"
                  hidden
                  id={`local-${variant}`}
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (!f) return;
                    const objUrl = URL.createObjectURL(f);
                    setUrl(objUrl);
                    setMode('local');
                    setShowInput(false);
                  }}
                />
                <label
                  htmlFor={`local-${variant}`}
                  className="cursor-pointer h-6 px-2 inline-flex items-center gap-1 rounded text-2xs uppercase tracking-[0.08em] font-mono text-fg-3 hover:text-fg-1 hover:bg-surface-2 transition-colors duration-140"
                >
                  <FileVideo size={10} />
                  本地视频
                </label>
                {error && (
                  <span className="font-mono text-2xs text-danger truncate max-w-[180px]">
                    {error}
                  </span>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
