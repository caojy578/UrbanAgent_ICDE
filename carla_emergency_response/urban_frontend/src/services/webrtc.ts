/**
 * Minimal WebRTC client for aiortc / Pixel Streaming style backends that
 * expose a JSON HTTP endpoint accepting an SDP offer and returning an answer.
 *
 *   POST <signalingUrl>
 *   body:  { sdp, type: 'offer' }
 *   reply: { sdp, type: 'answer' }
 *
 * The returned MediaStream is suitable for `videoElement.srcObject = stream`.
 */

export interface WebRTCSession {
  stream: MediaStream;
  pc: RTCPeerConnection;
  close: () => void;
}

const DEFAULT_ICE: RTCIceServer[] = [{ urls: 'stun:stun.l.google.com:19302' }];

export async function connectWebRTC(
  signalingUrl: string,
  options: { iceServers?: RTCIceServer[]; signal?: AbortSignal } = {},
): Promise<WebRTCSession> {
  const pc = new RTCPeerConnection({
    iceServers: options.iceServers ?? DEFAULT_ICE,
  });

  const stream = new MediaStream();
  pc.addTransceiver('video', { direction: 'recvonly' });
  pc.addTransceiver('audio', { direction: 'recvonly' });

  pc.addEventListener('track', (e) => {
    e.streams.forEach((s) => s.getTracks().forEach((t) => stream.addTrack(t)));
    if (!e.streams.length) stream.addTrack(e.track);
  });

  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);

  // Wait for ICE gathering to finish (simpler than trickle for one-shot signaling).
  await new Promise<void>((resolve) => {
    if (pc.iceGatheringState === 'complete') return resolve();
    const onChange = () => {
      if (pc.iceGatheringState === 'complete') {
        pc.removeEventListener('icegatheringstatechange', onChange);
        resolve();
      }
    };
    pc.addEventListener('icegatheringstatechange', onChange);
    setTimeout(() => resolve(), 2000);
  });

  const local = pc.localDescription!;
  const res = await fetch(signalingUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sdp: local.sdp, type: local.type }),
    signal: options.signal,
  });
  if (!res.ok) {
    pc.close();
    throw new Error(`Signaling failed: HTTP ${res.status}`);
  }
  const answer = (await res.json()) as RTCSessionDescriptionInit;
  await pc.setRemoteDescription(answer);

  return {
    stream,
    pc,
    close: () => {
      pc.getReceivers().forEach((r) => r.track?.stop());
      pc.close();
    },
  };
}
