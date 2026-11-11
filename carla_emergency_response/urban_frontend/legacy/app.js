/**
 * DIGITAL TWIN CITY COMMAND CENTER
 * 数字孪生城市指挥中心 — Frontend Logic
 */

'use strict';

/* ══════════════════════════════════════════
   CLOCK & DATE
══════════════════════════════════════════ */
function updateClock() {
  const now = new Date();
  const pad = n => String(n).padStart(2,'0');
  document.getElementById('live-time').textContent = `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
  document.getElementById('live-date').textContent = `${now.getFullYear()}/${pad(now.getMonth()+1)}/${pad(now.getDate())}`;
}
setInterval(updateClock, 1000);
updateClock();

/* ══════════════════════════════════════════
   FEED / STREAM MANAGEMENT
══════════════════════════════════════════ */

window.switchFeed = function(panel, mode) {
  const ue4Layer    = document.getElementById(`${panel}-ue4`);
  const streamLayer = document.getElementById(`${panel}-stream`);
  if (!ue4Layer || !streamLayer) return;

  const container = document.getElementById(`panel-${panel}`);
  if (container) {
    container.querySelectorAll('.ctrl-btn').forEach(btn => {
      const text = btn.textContent.trim();
      if (mode === 'ue4' && text === 'UE4') btn.classList.add('active');
      else if (mode === 'stream' && text === '流') btn.classList.add('active');
      else btn.classList.remove('active');
    });
  }

  if (mode === 'ue4') {
    ue4Layer.classList.remove('hidden');
    ue4Layer.style.display = 'block';
    streamLayer.style.display = 'none';
  } else {
    ue4Layer.classList.add('hidden');
    ue4Layer.style.display = 'none';
    streamLayer.style.display = 'block';
  }
};

window.loadLocalVideo = function(panel, input) {
  const file = input.files[0];
  if (!file) return;

  const video = document.getElementById(`${panel}-video`);
  const placeholder = document.getElementById(`${panel}-placeholder`);
  if (!video) return;

  const url = URL.createObjectURL(file);
  video.src = url;
  video.load();
  video.style.display = 'block';
  video.play().catch(err => console.error(err));

  if (placeholder) placeholder.style.display = 'none';
  switchFeed(panel, 'stream');
  appendEventLog('ok', `[${panel.toUpperCase()}] 本地视频已加载: ${file.name}`);
};

/* ── 各面板的活跃连接句柄 ── */
const _streamHandles = {}; // panel -> { type, cleanup }

/**
 * 断开指定面板当前连接（清理资源）
 */
window.disconnectStream = function(panel) {
  const handle = _streamHandles[panel];
  if (!handle) return;
  try { handle.cleanup(); } catch(e) {}
  delete _streamHandles[panel];
  appendEventLog('warn', `[${panel.toUpperCase()}] 连接已断开`);
};

/**
 * connectStream — 支持以下协议：
 *   • mp4/webm/ogv  — HTML5 <video>
 *   • .m3u8 / HLS   — hls.js（若已引入）或原生
 *   • mjpeg://       — MJPEG over HTTP (Motion JPEG)
 *   • http(s)://     带 ?mjpeg / ?format=mjpeg 参数，或响应类型判断
 *   • ws:// / wss:// — WebSocket 二进制帧 → canvas 渲染
 *   • webrtc://      — WebRTC（转换为 http/https 后走 RTCPeerConnection）
 *   • http(s)://     — UE4 Pixel Streaming iframe / 纯 HTTP MJPEG img
 */
window.connectStream = function(panel) {
  const input = document.getElementById(`${panel}-stream-url`);
  const url   = input ? input.value.trim() : '';
  if (!url) {
    appendEventLog('warn', `[${panel.toUpperCase()}] 未填写流地址`);
    return;
  }

  // 断开旧连接
  disconnectStream(panel);

  const placeholder = document.getElementById(`${panel}-placeholder`);
  const video       = document.getElementById(`${panel}-video`);
  const iframe      = document.getElementById(`${panel}-ue4-iframe`);
  const streamLayer = document.getElementById(`${panel}-stream`);

  const hide = el => { if (el) el.style.display = 'none'; };
  const show = (el, d='block') => { if (el) el.style.display = d; };

  /* ─────────────── 协议判断 ─────────────── */
  const lower = url.toLowerCase();

  const isMjpeg   = lower.startsWith('mjpeg://')
                 || lower.includes('?mjpeg')
                 || lower.includes('action=stream')
                 || lower.includes('format=mjpeg')
                 || lower.includes('/mjpeg')
                 || lower.includes('/stream.mjpg')
                 || lower.includes('/video.mjpg');

  const isWebSocket = lower.startsWith('ws://') || lower.startsWith('wss://');

  const isWebRTC  = lower.startsWith('webrtc://');

  const isHLS     = /\.m3u8(\?|$)/.test(lower);

  const isNativeVideo = /\.(mp4|webm|ogv)(\?|$)/.test(lower)
                     || lower.startsWith('blob:')
                     || lower.startsWith('mediastream:');

  /* ══════════════ 1. HTML5 原生视频 ══════════════ */
  if (isNativeVideo) {
    if (!video) return;
    video.src = url;
    video.load();
    show(video);
    hide(placeholder);
    video.play().catch(() => {});
    switchFeed(panel, 'stream');
    appendEventLog('ok', `[${panel.toUpperCase()}] 视频流已连接 (HTML5): ${url}`);
    _streamHandles[panel] = {
      type: 'html5',
      cleanup() { video.pause(); video.src = ''; hide(video); show(placeholder,'flex'); }
    };
    return;
  }

  /* ══════════════ 2. HLS (.m3u8) ══════════════ */
  if (isHLS) {
    if (!video) return;
    if (window.Hls && Hls.isSupported()) {
      const hls = new Hls();
      hls.loadSource(url);
      hls.attachMedia(video);
      hls.on(Hls.Events.MANIFEST_PARSED, () => video.play().catch(() => {}));
      hls.on(Hls.Events.ERROR, (_, d) => {
        if (d.fatal) appendEventLog('err', `[${panel.toUpperCase()}] HLS 错误: ${d.details}`);
      });
      show(video); hide(placeholder);
      switchFeed(panel, 'stream');
      appendEventLog('ok', `[${panel.toUpperCase()}] HLS 流已连接: ${url}`);
      _streamHandles[panel] = {
        type: 'hls',
        cleanup() { hls.destroy(); video.src = ''; hide(video); show(placeholder,'flex'); }
      };
    } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
      // Safari 原生 HLS
      video.src = url;
      video.load();
      show(video); hide(placeholder);
      video.play().catch(() => {});
      switchFeed(panel, 'stream');
      appendEventLog('ok', `[${panel.toUpperCase()}] HLS 流已连接 (原生): ${url}`);
      _streamHandles[panel] = {
        type: 'hls-native',
        cleanup() { video.pause(); video.src = ''; hide(video); show(placeholder,'flex'); }
      };
    } else {
      appendEventLog('err', `[${panel.toUpperCase()}] 浏览器不支持 HLS，请引入 hls.js`);
    }
    return;
  }

  /* ══════════════ 3. MJPEG ══════════════ */
  if (isMjpeg) {
    // 将 mjpeg:// scheme 替换为 http://
    const httpUrl = url.replace(/^mjpeg:\/\//i, 'http://');

    // 确保 stream 层里有一个 <img> 用于 MJPEG
    let mjpegImg = document.getElementById(`${panel}-mjpeg-img`);
    if (!mjpegImg) {
      mjpegImg = document.createElement('img');
      mjpegImg.id = `${panel}-mjpeg-img`;
      mjpegImg.style.cssText = 'width:100%;height:100%;object-fit:contain;display:none;position:absolute;top:0;left:0;';
      if (streamLayer) streamLayer.appendChild(mjpegImg);
    }

    mjpegImg.onload  = () => appendEventLog('ok', `[${panel.toUpperCase()}] MJPEG 帧已接收`);
    mjpegImg.onerror = () => appendEventLog('err', `[${panel.toUpperCase()}] MJPEG 连接失败`);

    // 加时间戳防缓存
    mjpegImg.src = httpUrl + (httpUrl.includes('?') ? '&' : '?') + '_t=' + Date.now();
    hide(video);
    show(mjpegImg);
    hide(placeholder);
    switchFeed(panel, 'stream');
    appendEventLog('ok', `[${panel.toUpperCase()}] MJPEG 流已连接: ${httpUrl}`);

    _streamHandles[panel] = {
      type: 'mjpeg',
      cleanup() {
        mjpegImg.src = '';
        hide(mjpegImg);
        show(placeholder, 'flex');
      }
    };
    return;
  }

  /* ══════════════ 4. WebSocket 二进制帧 ══════════════ */
  if (isWebSocket) {
    // 用 canvas 渲染 WS 推送的 JPEG/PNG 二进制帧
    let wsCanvas = document.getElementById(`${panel}-ws-canvas`);
    if (!wsCanvas) {
      wsCanvas = document.createElement('canvas');
      wsCanvas.id = `${panel}-ws-canvas`;
      wsCanvas.style.cssText = 'width:100%;height:100%;object-fit:contain;display:none;position:absolute;top:0;left:0;background:#000;';
      if (streamLayer) streamLayer.appendChild(wsCanvas);
    }
    const wsCtx = wsCanvas.getContext('2d');

    let ws;
    let frameCount = 0;
    let lastLogTime = 0;

    function wsConnect() {
      ws = new WebSocket(url);
      ws.binaryType = 'arraybuffer';

      ws.onopen = () => {
        appendEventLog('ok', `[${panel.toUpperCase()}] WebSocket 已连接: ${url}`);
        show(wsCanvas); hide(video); hide(placeholder);
        switchFeed(panel, 'stream');
      };

      ws.onmessage = (evt) => {
        frameCount++;
        const now = Date.now();
        if (now - lastLogTime > 5000) {
          appendEventLog('ok', `[${panel.toUpperCase()}] WS 接收帧 #${frameCount}`);
          lastLogTime = now;
        }

        let blob;
        if (evt.data instanceof ArrayBuffer) {
          // 尝试判断帧格式：JPEG (FF D8) 或 PNG (89 50)
          const arr = new Uint8Array(evt.data);
          const mime = (arr[0] === 0xFF && arr[1] === 0xD8) ? 'image/jpeg'
                     : (arr[0] === 0x89 && arr[1] === 0x50) ? 'image/png'
                     : 'image/jpeg';
          blob = new Blob([evt.data], { type: mime });
        } else if (typeof evt.data === 'string') {
          // Base64 编码帧：data:image/jpeg;base64,...
          const img = new Image();
          img.onload = () => {
            wsCanvas.width  = img.naturalWidth  || wsCanvas.clientWidth;
            wsCanvas.height = img.naturalHeight || wsCanvas.clientHeight;
            wsCtx.drawImage(img, 0, 0, wsCanvas.width, wsCanvas.height);
          };
          img.src = evt.data.startsWith('data:') ? evt.data : 'data:image/jpeg;base64,' + evt.data;
          return;
        } else {
          blob = evt.data; // Blob
        }

        const objUrl = URL.createObjectURL(blob);
        const img = new Image();
        img.onload = () => {
          wsCanvas.width  = img.naturalWidth  || wsCanvas.clientWidth;
          wsCanvas.height = img.naturalHeight || wsCanvas.clientHeight;
          wsCtx.drawImage(img, 0, 0, wsCanvas.width, wsCanvas.height);
          URL.revokeObjectURL(objUrl);
        };
        img.onerror = () => URL.revokeObjectURL(objUrl);
        img.src = objUrl;
      };

      ws.onerror = (e) => {
        appendEventLog('err', `[${panel.toUpperCase()}] WebSocket 错误，尝试重连...`);
      };

      ws.onclose = () => {
        const handle = _streamHandles[panel];
        if (handle && handle.type === 'websocket' && !handle._closed) {
          setTimeout(wsConnect, 3000); // 3s 后自动重连
        }
      };
    }

    wsConnect();
    _streamHandles[panel] = {
      type: 'websocket',
      _closed: false,
      cleanup() {
        this._closed = true;
        ws && ws.close();
        hide(wsCanvas);
        show(placeholder, 'flex');
      }
    };
    return;
  }

  /* ══════════════ 5. WebRTC ══════════════ */
  if (isWebRTC) {
    // webrtc://host:port/path → 转换为 https 信令地址
    const signalingUrl = url.replace(/^webrtc:\/\//i, 'https://');
    appendEventLog('ok', `[${panel.toUpperCase()}] 正在建立 WebRTC 连接: ${signalingUrl}`);

    let pc;

    async function startWebRTC() {
      pc = new RTCPeerConnection({
        iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
      });

      // 接收远端轨道 → 绑定到 <video>
      pc.ontrack = (evt) => {
        if (!video) return;
        if (evt.streams && evt.streams[0]) {
          video.srcObject = evt.streams[0];
        } else {
          const ms = video.srcObject || new MediaStream();
          ms.addTrack(evt.track);
          video.srcObject = ms;
        }
        show(video); hide(placeholder);
        video.play().catch(() => {});
        switchFeed(panel, 'stream');
        appendEventLog('ok', `[${panel.toUpperCase()}] WebRTC 轨道已接收`);
      };

      pc.oniceconnectionstatechange = () => {
        const state = pc.iceConnectionState;
        if (state === 'disconnected' || state === 'failed') {
          appendEventLog('err', `[${panel.toUpperCase()}] WebRTC ICE 状态: ${state}`);
        }
      };

      // 添加 recvonly transceiver（仅接收）
      pc.addTransceiver('video', { direction: 'recvonly' });
      pc.addTransceiver('audio', { direction: 'recvonly' });

      try {
        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);

        // 等待 ICE 收集完成
        await new Promise(resolve => {
          if (pc.iceGatheringState === 'complete') { resolve(); return; }
          pc.onicegatheringstatechange = () => {
            if (pc.iceGatheringState === 'complete') resolve();
          };
          setTimeout(resolve, 3000); // 最长等 3s
        });

        // 发送 Offer SDP 到信令服务器
        const resp = await fetch(signalingUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/sdp' },
          body: pc.localDescription.sdp
        });

        if (!resp.ok) throw new Error(`信令服务器响应 ${resp.status}`);
        const answerSdp = await resp.text();
        await pc.setRemoteDescription({ type: 'answer', sdp: answerSdp });
        appendEventLog('ok', `[${panel.toUpperCase()}] WebRTC SDP 协商完成`);

      } catch (err) {
        appendEventLog('err', `[${panel.toUpperCase()}] WebRTC 信令失败: ${err.message}`);
        // 回退：尝试 iframe 加载
        if (iframe) {
          iframe.src = signalingUrl;
          hide(placeholder);
          switchFeed(panel, 'ue4');
          appendEventLog('warn', `[${panel.toUpperCase()}] 已回退为 iframe 模式`);
        }
      }
    }

    startWebRTC();
    _streamHandles[panel] = {
      type: 'webrtc',
      cleanup() {
        if (pc) { pc.close(); pc = null; }
        if (video) { video.srcObject = null; hide(video); }
        show(placeholder, 'flex');
      }
    };
    return;
  }

  /* ══════════════ 6. HTTP(S) — UE4 Pixel Streaming iframe ══════════════ */
  if (lower.startsWith('http://') || lower.startsWith('https://')) {
    if (iframe) {
      iframe.src = url;
      hide(placeholder);
      switchFeed(panel, 'ue4');
      appendEventLog('ok', `[${panel.toUpperCase()}] UE4 Pixel Streaming 已连接: ${url}`);
      _streamHandles[panel] = {
        type: 'iframe',
        cleanup() { iframe.src = 'about:blank'; show(placeholder,'flex'); switchFeed(panel,'stream'); }
      };
    }
    return;
  }

  /* ══════════════ 未识别协议 ══════════════ */
  appendEventLog('warn', `[${panel.toUpperCase()}] 不支持的流地址格式，请检查 URL`);
};

/* ══════════════════════════════════════════
   FULLSCREEN
══════════════════════════════════════════ */
window.toggleFullscreen = function(panelId) {
  const panel = document.getElementById(panelId);
  if (!panel) return;
  panel.classList.toggle('is-fullscreen');
};

/* ══════════════════════════════════════════
   CITY CANVAS ANIMATION
══════════════════════════════════════════ */
function initCityCanvas() {
  const canvas = document.getElementById('city-canvas');
  if (!canvas) return;
  
  const ctx = canvas.getContext('2d');
  let W = 0, H = 0, animId;

  function resize() {
    const parent = canvas.parentElement;
    if (parent) {
      const rect = parent.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) {
        W = canvas.width  = rect.width;
        H = canvas.height = rect.height;
      }
    }
  }

  function drawGrid(t) {
    if (W <= 0 || H <= 0) return;
    ctx.clearRect(0, 0, W, H);

    const cx = W / 2;
    const hy = H * 0.45;
    const N  = 18;

    // Ground glow
    const grad = ctx.createLinearGradient(0, hy, 0, H);
    grad.addColorStop(0, 'rgba(0,30,60,0)');
    grad.addColorStop(1, 'rgba(0,60,100,0.25)');
    ctx.fillStyle = grad;
    ctx.fillRect(0, hy, W, H - hy);

    // Longitudinal lines
    for (let i = -N; i <= N; i++) {
      const x   = cx + i * (W / N / 2);
      const alpha = 0.15 + 0.04 * Math.sin(t * 0.002 + i * 0.3);
      ctx.strokeStyle = `rgba(0,180,220,${alpha})`;
      ctx.lineWidth   = 0.5;
      ctx.beginPath();
      ctx.moveTo(cx + (x - cx) * 0.01, hy);
      ctx.lineTo(x, H + 20);
      ctx.stroke();
    }

    // Horizontal lines (receding)
    const steps = 20;
    for (let j = 0; j < steps; j++) {
      const frac  = Math.pow(j / steps, 1.8);
      const yAnim = hy + ((H - hy) * ((frac + (t * 0.0003)) % 1));
      const alpha = 0.05 + 0.08 * (1 - frac);
      ctx.strokeStyle = `rgba(0,180,220,${alpha})`;
      ctx.lineWidth   = 0.5;
      const xLeft  = cx - (cx) * (1 - Math.pow(1 - frac, 0.5));
      const xRight = cx + (W - cx) * (1 - Math.pow(1 - frac, 0.5));
      ctx.beginPath();
      ctx.moveTo(xLeft, yAnim);
      ctx.lineTo(xRight, yAnim);
      ctx.stroke();
    }

    // Sky grid
    for (let i = -N/2; i <= N/2; i++) {
      const x   = cx + i * (W / N);
      const alpha = 0.04;
      ctx.strokeStyle = `rgba(0,150,180,${alpha})`;
      ctx.lineWidth   = 0.4;
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(cx + (x - cx) * 0.01, hy);
      ctx.stroke();
    }

    // Horizon line
    const hGrad = ctx.createLinearGradient(0, 0, W, 0);
    hGrad.addColorStop(0,   'rgba(0,212,255,0)');
    hGrad.addColorStop(0.3, 'rgba(0,212,255,0.4)');
    hGrad.addColorStop(0.5, 'rgba(0,212,255,0.8)');
    hGrad.addColorStop(0.7, 'rgba(0,212,255,0.4)');
    hGrad.addColorStop(1,   'rgba(0,212,255,0)');
    ctx.strokeStyle = hGrad;
    ctx.lineWidth   = 1.5;
    ctx.beginPath();
    ctx.moveTo(0, hy); ctx.lineTo(W, hy);
    ctx.stroke();

    // Floating particles
    ctx.fillStyle = 'rgba(0,212,255,0.6)';
    const seed = Math.floor(t * 0.01);
    for (let p = 0; p < 40; p++) {
      const px = ((p * 137.508 + seed * 7) % W);
      const py = H * 0.05 + ((p * 97.3 + seed * 3) % (hy * 0.9));
      const r  = 0.5 + ((p * 13) % 3) * 0.5;
      const alpha2 = 0.2 + 0.5 * Math.sin(t * 0.003 + p);
      ctx.globalAlpha = alpha2;
      ctx.beginPath();
      ctx.arc(px, py, r, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalAlpha = 1;
  }

  let startTime = null;
  function animate(ts) {
    if (!startTime) startTime = ts;
    drawGrid(ts - startTime);
    animId = requestAnimationFrame(animate);
  }

  resize();
  window.addEventListener('resize', resize);
  animId = requestAnimationFrame(animate);
}

/* ══════════════════════════════════════════
   SPARKLINE (realtime system telemetry)
══════════════════════════════════════════ */
const sparkData = Array.from({length: 60}, () => Math.random() * 100);

function drawSparkline() {
  const canvas = document.getElementById('sparkline-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const W   = canvas.width  = canvas.clientWidth * window.devicePixelRatio;
  const H   = canvas.height = canvas.clientHeight * window.devicePixelRatio;
  ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
  const cW  = canvas.clientWidth;
  const cH  = canvas.clientHeight;

  ctx.clearRect(0, 0, cW, cH);

  const n = sparkData.length;
  const step = cW / (n - 1);

  const grad = ctx.createLinearGradient(0, 0, 0, cH);
  grad.addColorStop(0, 'rgba(0,212,255,0.3)');
  grad.addColorStop(1, 'rgba(0,212,255,0)');
  ctx.fillStyle = grad;
  ctx.beginPath();
  ctx.moveTo(0, cH);
  sparkData.forEach((v, i) => {
    const x = i * step;
    const y = cH - (v / 100) * (cH - 4) - 2;
    i === 0 ? ctx.lineTo(x, y) : ctx.lineTo(x, y);
  });
  ctx.lineTo((n-1)*step, cH);
  ctx.closePath();
  ctx.fill();

  ctx.strokeStyle = 'rgba(0,212,255,0.9)';
  ctx.lineWidth   = 1.2;
  ctx.shadowColor = '#00d4ff';
  ctx.shadowBlur  = 4;
  ctx.beginPath();
  sparkData.forEach((v, i) => {
    const x = i * step;
    const y = cH - (v / 100) * (cH - 4) - 2;
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  });
  ctx.stroke();
  ctx.shadowBlur = 0;
}

function updateSparkline() {
  sparkData.shift();
  sparkData.push(30 + Math.random() * 60);
  drawSparkline();
}
setInterval(updateSparkline, 500);

/* ══════════════════════════════════════════
   SIMULATED TELEMETRY (HUD values)
══════════════════════════════════════════ */
function updateTelemetry() {
  const alt = (120 + Math.random() * 20).toFixed(1);
  const spd = (28 + Math.random() * 10).toFixed(1);
  const bat = Math.max(70, Math.min(100, parseInt(
    document.getElementById('uav-bat')?.textContent || '87'
  ) + (Math.random() > 0.8 ? -1 : 0)));
  setVal('uav-alt', alt);
  setVal('uav-spd', spd);
  setVal('uav-bat', bat);

  const ugvSpd = (22 + Math.random() * 15).toFixed(1);
  const hdgs   = ['N 000°','N 045°','E 090°','S 180°','W 270°'];
  setVal('ugv-spd', ugvSpd);
  if (Math.random() > 0.85) {
    const el = document.getElementById('ugv-hdg');
    if (el) el.textContent = hdgs[Math.floor(Math.random()*hdgs.length)];
  }
}

function setVal(id, val) {
  const el = document.getElementById(id);
  if (!el) return;
  const spans = el.querySelectorAll('span');
  const suffix = spans.length ? spans[0].outerHTML : '';
  el.textContent = val;
  if (suffix) el.innerHTML = val + suffix;
}

setInterval(updateTelemetry, 1200);

/* ══════════════════════════════════════════
   SIMULATED SYSTEM METRICS
══════════════════════════════════════════ */
const metricTargets = { cpu: 62, gpu: 78, mem: 55, net: 38 };

function updateMetrics() {
  ['cpu','gpu','mem','net'].forEach(key => {
    metricTargets[key] = Math.max(10, Math.min(99,
      metricTargets[key] + (Math.random() - 0.5) * 6
    ));
    const v = Math.round(metricTargets[key]);
    const bar = document.getElementById(`${key}-bar`);
    const val = document.getElementById(`${key}-val`);
    if (bar) bar.style.width = `${v}%`;
    if (val) val.textContent = `${v}%`;
  });

  const fps = Math.round(58 + Math.random() * 4);
  const fpsEl = document.getElementById('fps-val');
  if (fpsEl) fpsEl.innerHTML = `${fps}<span class="unit">fps</span>`;

  const lat = Math.round(8 + Math.random() * 8);
  const latEl = document.getElementById('latency');
  if (latEl) latEl.innerHTML = `${lat}<span class="unit">ms</span>`;
}
setInterval(updateMetrics, 2000);

/* ══════════════════════════════════════════
   EVENT LOG
══════════════════════════════════════════ */
const systemEvents = [
  { type: 'ok',   msg: 'UAV-01 任务航点更新完成' },
  { type: 'ok',   msg: 'UGV-02 路径规划已同步' },
  { type: 'warn', msg: 'UAV-03 电量低于 30%，建议返航' },
  { type: 'ok',   msg: '3D 地图数据已刷新 (LOD-5)' },
  { type: 'warn', msg: '路段 B7 检测到拥堵事件' },
  { type: 'ok',   msg: 'Pixel Streaming 会话保持心跳正常' },
  { type: 'ok',   msg: '智能体编队协同任务启动' },
  { type: 'err',  msg: 'UGV-04 通信超时，正在重连...' },
  { type: 'ok',   msg: '数字孪生场景同步完成' },
  { type: 'warn', msg: '区域 C3 气象告警: 风速 > 12m/s' },
];
let evIdx = 0;

window.appendEventLog = function(type, msg) {
  const log = document.getElementById('event-log');
  if (!log) return;
  const now  = new Date();
  const time = `${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}:${String(now.getSeconds()).padStart(2,'0')}`;
  const entry = document.createElement('div');
  entry.className = `log-entry ${type}`;
  entry.innerHTML = `<span class="log-time">[${time}]</span><span class="log-msg">${msg}</span>`;
  log.appendChild(entry);
  while (log.children.length > 52) log.removeChild(log.children[1]);
  log.scrollTop = log.scrollHeight;
};

function tickEventLog() {
  const ev = systemEvents[evIdx % systemEvents.length];
  evIdx++;
  appendEventLog(ev.type, ev.msg);
}
for (let i = 0; i < 4; i++) tickEventLog();
setInterval(tickEventLog, 4000 + Math.random() * 3000);

/* ══════════════════════════════════════════
   COMMAND TERMINAL
══════════════════════════════════════════ */
const cmdHistory = [];
let cmdHistIdx   = -1;

const cmdResponses = {
  '返回基地': ['[ACK] 指令已发送', '[INFO] 正在计算最优返航路径...', '[ACK] 预计 120s 抵达基地'],
  '悬停待命': ['[ACK] 指令已发送', '[INFO] 智能体已进入悬停状态'],
  '开始巡逻': ['[ACK] 指令已发送', '[INFO] 加载巡逻航点 WP-07...', '[ACK] 巡逻任务已启动'],
  '数据采集': ['[ACK] 指令已发送', '[INFO] 传感器阵列已激活', '[DATA] 开始采集: LiDAR / RGB / IR'],
  '紧急停止': ['[URGENT] ⚠ 紧急停止指令已广播', '[SYS] 所有运动模块已锁定'],
  '安全撤离': ['[URGENT] ⚠ 安全撤离程序启动', '[SYS] 正在广播撤离路径...', '[ACK] 编队已收到指令'],
};

function appendCmd(cls, text) {
  const stream = document.getElementById('cmd-stream');
  if (!stream) return;
  const line = document.createElement('div');
  line.className = `cmd-line ${cls}`;
  line.textContent = text;
  stream.appendChild(line);
  while (stream.children.length > 200) stream.removeChild(stream.firstChild);
  requestAnimationFrame(() => {
    stream.scrollTop = stream.scrollHeight;
  });
}

window.sendQuickCmd = function(cmd) {
  document.getElementById('cmd-input').value = cmd;
  sendCommand();
};

window.sendCommand = function() {
  const input    = document.getElementById('cmd-input');
  const target   = document.getElementById('cmd-target');
  const priority = document.getElementById('cmd-priority');
  const cmd      = input.value.trim();
  if (!cmd) return;

  const tgt  = target ? target.value : 'ALL';
  const prio = priority ? priority.value : 'NORMAL';
  const prioLabel = prio === 'URGENT' ? '🔴 [URGENT]' : prio === 'HIGH' ? '🟡 [HIGH]' : '[NORMAL]';

  const ts = new Date().toLocaleTimeString('zh-CN', {hour12: false});
  appendCmd('user', `[${ts}] ${prioLabel} → ${tgt}: ${cmd}`);
  cmdHistory.unshift(cmd);
  cmdHistIdx = -1;
  input.value = '';

  const responses = cmdResponses[cmd] || [`[ACK] 指令已转发: "${cmd}"`, '[SYS] 智能体正在处理...'];
  const cls = prio === 'URGENT' ? 'urgent' : prio === 'HIGH' ? 'warn' : 'ack';
  responses.forEach((res, i) => {
    setTimeout(() => appendCmd(cls, res), 300 + i * 400);
  });

  setTimeout(() => appendEventLog('ok', `[CMD→${tgt}] ${cmd}`), 200);
};

window.clearCommands = function() {
  const stream = document.getElementById('cmd-stream');
  if (stream) {
    stream.innerHTML = '';
    appendCmd('sys', '[SYSTEM] 指令日志已清空');
  }
};

window.handleCmdInput = function(e) {
  if (e.key === 'Enter') {
    sendCommand();
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    if (cmdHistIdx < cmdHistory.length - 1) {
      cmdHistIdx++;
      document.getElementById('cmd-input').value = cmdHistory[cmdHistIdx] || '';
    }
  } else if (e.key === 'ArrowDown') {
    e.preventDefault();
    if (cmdHistIdx > 0) {
      cmdHistIdx--;
      document.getElementById('cmd-input').value = cmdHistory[cmdHistIdx] || '';
    } else {
      cmdHistIdx = -1;
      document.getElementById('cmd-input').value = '';
    }
  }
};

/* ══════════════════════════════════════════
   ALERT COUNTER SIMULATION
══════════════════════════════════════════ */
let alertCount = 3;
setInterval(() => {
  if (Math.random() > 0.7) {
    alertCount = Math.max(0, Math.min(12,
      alertCount + (Math.random() > 0.5 ? 1 : -1)
    ));
    const el = document.getElementById('alert-count');
    if (el) {
      el.textContent = alertCount;
      el.className   = `cs-val ${alertCount >= 5 ? 'accent-red' : alertCount >= 3 ? 'accent-yellow' : 'accent-green'}`;
    }
  }
}, 5000);

/* ══════════════════════════════════════════
   INIT — 页面加载后立即执行
══════════════════════════════════════════ */

// 不在 DOMContentLoaded 里，直接立即执行初始化
(function initAllPanels() {
  // 如果 DOM 还没准备好，等待
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAllPanels);
    return;
  }

  // 初始化所有面板
  ['uav', 'ugv', 'city'].forEach(panel => {
    // 隐藏视频
    const video = document.getElementById(`${panel}-video`);
    if (video) {
      video.style.display = 'none';
      video.src = '';
    }
    
    // 显示占位符（强制 display:flex）
    const placeholder = document.getElementById(`${panel}-placeholder`);
    if (placeholder) {
      placeholder.style.display = 'flex';
      placeholder.style.visibility = 'visible';
      placeholder.style.opacity = '1';
      placeholder.style.zIndex = '10';
    }
    
    // 隐藏 UE4 层
    const ue4Layer = document.getElementById(`${panel}-ue4`);
    if (ue4Layer) {
      ue4Layer.classList.add('hidden');
      ue4Layer.style.display = 'none';
    }
    
    // 显示流层
    const streamLayer = document.getElementById(`${panel}-stream`);
    if (streamLayer) {
      streamLayer.style.display = 'block';
    }
    
    // 按钮状态
    const container = document.getElementById(`panel-${panel}`);
    if (container) {
      container.querySelectorAll('.ctrl-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.textContent.trim() === '流') {
          btn.classList.add('active');
        }
      });
    }
  });

  // 城市画布放在占位符后面
  const cityCanvas = document.getElementById('city-canvas');
  if (cityCanvas) {
    cityCanvas.style.pointerEvents = 'none';
    cityCanvas.style.zIndex = '0';
  }

  // 初始化动画
  initCityCanvas();
  drawSparkline();
  updateMetrics();
  updateTelemetry();

  // 入场动画
  document.querySelectorAll('.panel').forEach((p, i) => {
    p.style.opacity = '0';
    p.style.transform = 'translateY(8px)';
    p.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
    requestAnimationFrame(() => {
      setTimeout(() => {
        p.style.opacity = '';
        p.style.transform = '';
      }, 100 + i * 80);
    });
  });
})();

/* Handle window resize for sparkline */
window.addEventListener('resize', drawSparkline);

/* ══════════════════════════════════════════
   UE4 PIXEL STREAMING GUIDE (console)
══════════════════════════════════════════ */
console.log(`
╔══════════════════════════════════════════════════════════╗
║   数字孪生城市指挥中心 — 接入指南                        ║
╠══════════════════════════════════════════════════════════╣
║  UE4 Pixel Streaming (HTTP iframe):                     ║
║    http://<UE4-Server-IP>:<Port>/                       ║
║    例如: http://192.168.1.100:8080/                     ║
║                                                          ║
║  HTML5 视频流 (mp4 / webm / ogv):                       ║
║    https://example.com/city-feed.mp4                    ║
║                                                          ║
║  HLS 流 (.m3u8):                                        ║
║    https://example.com/live/stream.m3u8                 ║
║    (Safari 原生支持；其他浏览器需引入 hls.js)            ║
║                                                          ║
║  MJPEG 流:                                              ║
║    mjpeg://192.168.1.50:8080/stream.mjpg               ║
║    http://192.168.1.50:8080/video.mjpg                  ║
║    http://cam-ip/?action=stream                         ║
║    http://cam-ip/?format=mjpeg                          ║
║                                                          ║
║  WebSocket 二进制帧流 (JPEG/PNG/Base64):                ║
║    ws://192.168.1.50:9000/video                         ║
║    wss://secure-server.com/feed                         ║
║    (支持 ArrayBuffer / Blob / Base64 字符串帧)          ║
║    (断线后自动重连)                                      ║
║                                                          ║
║  WebRTC 流:                                             ║
║    webrtc://192.168.1.50:8889/stream                    ║
║    (转换为 https 信令地址，使用 WHEP/SDP 协商)          ║
║    (ICE 服务器: stun.l.google.com:19302)                ║
║    (信令失败时自动回退为 iframe 模式)                   ║
║                                                          ║
║  RTSP 流:                                               ║
║    需中转服务器将 RTSP 转为 WebSocket 或 HLS            ║
║    推荐: mediamtx / ffmpeg → ws/hls 中转               ║
╚══════════════════════════════════════════════════════════╝
`);