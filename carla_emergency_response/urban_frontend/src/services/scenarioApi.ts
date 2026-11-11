import { useSystemStore } from '@/store/useSystemStore';

export interface FirePayload {
  id?: string;
  position: { x: number; y: number; z: number };
  kind?: string;
  severity?: string;
  blueprint?: string;
}

export interface FireResponse {
  status: string;
  incident_id: string;
  spawned_actor_id?: number;
  spawned_at_sim_time?: number;
  run_id?: number;
}

export interface ResetResponse {
  status: string;
  run_id: number;
  reset_at_sim_time?: number;
  cancelled_commands?: string[];
  destroyed_incidents?: string[];
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const text = await res.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { error: text };
    }
  }
  if (!res.ok) {
    const errMsg =
      (data && typeof data === 'object' && 'error' in (data as Record<string, unknown>)
        ? String((data as Record<string, unknown>).error)
        : null) ?? `HTTP ${res.status}`;
    throw new Error(errMsg);
  }
  return data as T;
}

export async function triggerFire(
  payload: FirePayload = { id: 'fire-001', position: { x: 25.3, y: 24.4, z: 0 } },
): Promise<FireResponse> {
  const sys = useSystemStore.getState();
  try {
    const resp = await postJson<FireResponse>('/scenario/fire', payload);
    sys.pushEvent({
      severity: 'ok',
      source: 'SCENARIO',
      message: `点火 ${resp.incident_id} 已下发 ${
        resp.run_id != null ? ` · run=${resp.run_id}` : ''
      }`,
    });
    return resp;
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    sys.pushEvent({
      severity: 'danger',
      source: 'SCENARIO',
      message: `点火失败 · ${msg}`,
    });
    throw err;
  }
}

export async function triggerReset(): Promise<ResetResponse> {
  const sys = useSystemStore.getState();
  try {
    const resp = await postJson<ResetResponse>('/scenario/reset', {});
    const cancelled = resp.cancelled_commands?.length ?? 0;
    const destroyed = resp.destroyed_incidents?.length ?? 0;
    sys.pushEvent({
      severity: 'warn',
      source: 'SCENARIO',
      message: `场景已重置 · run=${resp.run_id} · 取消命令×${cancelled} · 清除事件×${destroyed}`,
    });
    return resp;
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    sys.pushEvent({
      severity: 'danger',
      source: 'SCENARIO',
      message: `场景重置失败 · ${msg}`,
    });
    throw err;
  }
}
