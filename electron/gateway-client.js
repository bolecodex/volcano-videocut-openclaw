const WebSocket = require('ws');
const { randomUUID, createPrivateKey, createPublicKey, sign } = require('crypto');
const { readFileSync, existsSync } = require('fs');
const { join } = require('path');
const { homedir } = require('os');

const PROTOCOL_VERSION = 3;
const RECONNECT_BASE_MS = 1000;
const RECONNECT_MAX_MS = 30000;
const CONNECT_DELAY_MS = 750;
const TICK_TIMEOUT_MULTIPLIER = 2;
const ED25519_SPKI_PREFIX = Buffer.from('302a300506032b6570032100', 'hex');

function loadGatewayConfig() {
  const configPath = join(homedir(), '.openclaw', 'openclaw.json');
  if (!existsSync(configPath)) {
    throw new Error(`OpenClaw config not found at ${configPath}`);
  }
  const raw = JSON.parse(readFileSync(configPath, 'utf-8'));
  return {
    port: raw.gateway?.port ?? 18789,
    auth: {
      mode: raw.gateway?.auth?.mode ?? 'token',
      token: raw.gateway?.auth?.token ?? '',
    },
  };
}

function loadDeviceIdentity() {
  const identityPath = join(homedir(), '.openclaw', 'identity', 'device.json');
  if (!existsSync(identityPath)) return null;
  try {
    const raw = JSON.parse(readFileSync(identityPath, 'utf-8'));
    if (raw.deviceId && raw.publicKeyPem && raw.privateKeyPem) {
      return { deviceId: raw.deviceId, publicKeyPem: raw.publicKeyPem, privateKeyPem: raw.privateKeyPem };
    }
    return null;
  } catch { return null; }
}

function base64UrlEncode(buf) {
  return buf.toString('base64').replaceAll('+', '-').replaceAll('/', '_').replace(/=+$/g, '');
}

function derivePublicKeyRaw(publicKeyPem) {
  const spki = createPublicKey(publicKeyPem).export({ type: 'spki', format: 'der' });
  if (spki.length === ED25519_SPKI_PREFIX.length + 32 &&
      spki.subarray(0, ED25519_SPKI_PREFIX.length).equals(ED25519_SPKI_PREFIX)) {
    return spki.subarray(ED25519_SPKI_PREFIX.length);
  }
  return spki;
}

function publicKeyRawBase64Url(publicKeyPem) {
  return base64UrlEncode(derivePublicKeyRaw(publicKeyPem));
}

function signPayload(privateKeyPem, payload) {
  const key = createPrivateKey(privateKeyPem);
  const sig = sign(null, Buffer.from(payload, 'utf8'), key);
  return base64UrlEncode(sig);
}

function buildDeviceAuthPayload(opts) {
  const version = opts.nonce ? 'v2' : 'v1';
  const base = [
    version, opts.deviceId, opts.clientId, opts.clientMode,
    opts.role, opts.scopes.join(','), String(opts.signedAtMs),
    opts.token ?? '',
  ];
  if (version === 'v2') base.push(opts.nonce ?? '');
  return base.join('|');
}

class OpenClawGateway {
  constructor() {
    this.ws = null;
    this.config = null;
    this.device = null;
    this.pending = new Map();
    this.eventListeners = new Map();
    this.closed = false;
    this.connected = false;
    this.connectSent = false;
    this.connectNonce = null;
    this.backoffMs = RECONNECT_BASE_MS;
    this.tickIntervalMs = 30000;
    this.lastTick = null;
    this.tickTimer = null;
    this.instanceId = randomUUID();
  }

  get isConnected() {
    return this.connected;
  }

  start() {
    if (this.closed) return;
    try {
      this.config = loadGatewayConfig();
      this.device = loadDeviceIdentity();
      if (!this.device) {
        console.warn('[gateway-client] no device identity found, auth may be limited');
      }
    } catch (err) {
      console.error('[gateway-client]', err.message);
      return;
    }

    const url = `ws://127.0.0.1:${this.config.port}`;
    this.ws = new WebSocket(url, {
      maxPayload: 25 * 1024 * 1024,
      origin: `http://127.0.0.1:${this.config.port}`,
    });

    this.ws.on('open', () => {
      this._queueConnect();
    });

    this.ws.on('message', (data) => {
      const raw = typeof data === 'string' ? data : Buffer.from(data).toString();
      this._handleMessage(raw);
    });

    this.ws.on('close', () => {
      this.ws = null;
      this.connected = false;
      this.connectSent = false;
      this._flushPendingErrors(new Error('gateway connection closed'));
      this._scheduleReconnect();
    });

    this.ws.on('error', (err) => {
      console.error('[gateway-client] ws error:', err.message);
    });
  }

  stop() {
    this.closed = true;
    if (this.tickTimer) {
      clearInterval(this.tickTimer);
      this.tickTimer = null;
    }
    this.ws?.close();
    this.ws = null;
    this.connected = false;
    this._flushPendingErrors(new Error('gateway client stopped'));
  }

  async sendPrompt(message, opts = {}) {
    if (!this.connected) {
      return { error: 'Gateway not connected' };
    }

    const idempotencyKey = randomUUID();
    const runId = idempotencyKey;
    const eventQueue = [];
    let resolveWait = null;

    const listenerId = randomUUID();
    this.eventListeners.set(listenerId, (evtRunId, event) => {
      if (evtRunId !== runId) return;
      eventQueue.push(event);
      resolveWait?.();
    });

    const cleanup = () => this.eventListeners.delete(listenerId);

    const requestPromise = this._request('agent', {
      message,
      agentId: opts.agentId ?? 'main',
      sessionKey: opts.sessionKey,
      idempotencyKey,
      extraSystemPrompt: opts.extraSystemPrompt,
      timeout: opts.timeout,
    }, { expectFinal: true });

    requestPromise
      .then(() => { eventQueue.push({ type: 'done' }); resolveWait?.(); })
      .catch((err) => { eventQueue.push({ type: 'error', error: err.message || String(err) }); resolveWait?.(); })
      .finally(cleanup);

    return { runId, eventQueue, waitForEvent: () => new Promise((r) => { resolveWait = r; }), cleanup };
  }

  async listSessions() {
    if (!this.connected) return [];
    try {
      const result = await this._request('sessions.list', {});
      const entries = result?.sessions ?? result;
      if (!Array.isArray(entries)) return [];
      return entries.map(normalizeSessionInfo);
    } catch (err) {
      console.error('[gateway-client] sessions.list failed:', err.message);
      return [];
    }
  }

  async getSession(sessionKey) {
    if (!this.connected) return null;
    try {
      const result = await this._request('sessions.get', { sessionKey });
      if (!result) return null;
      return normalizeSessionInfo(result);
    } catch { return null; }
  }

  async deleteSession(sessionKey) {
    if (!this.connected) return false;
    try {
      await this._request('sessions.delete', { sessionKey });
      return true;
    } catch { return false; }
  }

  async resetSession(sessionKey) {
    if (!this.connected) return false;
    try {
      await this._request('sessions.reset', { sessionKey });
      return true;
    } catch { return false; }
  }

  _queueConnect() {
    this.connectNonce = null;
    this.connectSent = false;
    setTimeout(() => this._sendConnect(), CONNECT_DELAY_MS);
  }

  _sendConnect() {
    if (this.connectSent) return;
    this.connectSent = true;

    const clientId = 'openclaw-control-ui';
    const clientMode = 'backend';
    const role = 'operator';
    const scopes = ['operator.admin', 'operator.read', 'operator.write', 'operator.approvals', 'operator.pairing'];
    const authToken = this.config.auth.token;
    const signedAtMs = Date.now();
    const nonce = this.connectNonce ?? undefined;

    let devicePayload;
    if (this.device) {
      const payload = buildDeviceAuthPayload({
        deviceId: this.device.deviceId,
        clientId,
        clientMode,
        role,
        scopes,
        signedAtMs,
        token: authToken || null,
        nonce,
      });
      const signature = signPayload(this.device.privateKeyPem, payload);
      devicePayload = {
        id: this.device.deviceId,
        publicKey: publicKeyRawBase64Url(this.device.publicKeyPem),
        signature,
        signedAt: signedAtMs,
        nonce,
      };
    }

    const params = {
      minProtocol: PROTOCOL_VERSION,
      maxProtocol: PROTOCOL_VERSION,
      client: {
        id: clientId,
        version: '1.0.0',
        platform: process.platform,
        mode: clientMode,
        instanceId: this.instanceId,
      },
      caps: ['tool-events'],
      role,
      scopes,
      auth: { token: authToken },
    };

    if (devicePayload) {
      params.device = devicePayload;
    }

    this._request('connect', params)
      .then((result) => {
        this.connected = true;
        this.backoffMs = RECONNECT_BASE_MS;
        const policy = result?.policy;
        if (policy?.tickIntervalMs) this.tickIntervalMs = policy.tickIntervalMs;
        this.lastTick = Date.now();
        this._startTickWatch();
        console.log('[gateway-client] connected to OpenClaw Gateway');
      })
      .catch((err) => {
        console.error('[gateway-client] connect failed:', err.message);
        this.ws?.close(1008, 'connect failed');
      });
  }

  _handleMessage(raw) {
    let frame;
    try { frame = JSON.parse(raw); } catch { return; }

    if (frame.type === 'event') {
      if (frame.event === 'connect.challenge') {
        const nonce = frame.payload?.nonce;
        if (typeof nonce === 'string') {
          this.connectNonce = nonce;
          this.connectSent = false;
          this._sendConnect();
        }
        return;
      }

      if (frame.event === 'tick') {
        this.lastTick = Date.now();
        return;
      }

      this._dispatchAgentEvent(frame);
      return;
    }

    if (frame.type === 'res') {
      const pending = this.pending.get(frame.id);
      if (!pending) return;

      const status = frame.payload?.status;
      if (pending.expectFinal && status === 'accepted') return;

      this.pending.delete(frame.id);
      if (frame.ok) pending.resolve(frame.payload);
      else pending.reject(new Error(frame.error?.message ?? 'unknown gateway error'));
    }
  }

  _dispatchAgentEvent(evt) {
    const payload = evt.payload;
    if (!payload) return;

    const runId = payload.runId;
    const stream = payload.stream;
    const data = payload.data;
    if (!runId || !stream) return;

    let event = null;

    switch (stream) {
      case 'assistant': {
        const delta = data?.delta ?? '';
        if (delta) event = { type: 'text', delta, content: delta };
        break;
      }
      case 'lifecycle': {
        const phase = data?.phase;
        if (phase === 'start') event = { type: 'lifecycle', phase: 'start' };
        else if (phase === 'end') event = { type: 'lifecycle', phase: 'end' };
        else if (phase === 'error') event = { type: 'error', error: data?.error ?? 'Agent error' };
        break;
      }
      case 'tool': {
        const phase = data?.phase;
        const toolName = data?.name ?? data?.tool ?? 'tool';
        const toolId = data?.id ?? data?.toolCallId ?? data?.callId ?? randomUUID();

        if (phase === 'start' || phase === 'invoke') {
          const inputRaw = data?.input ?? data?.args ?? data?.arguments;
          event = {
            type: 'tool_start',
            toolCall: {
              id: toolId, title: toolName, status: 'running',
              input: inputRaw ? (typeof inputRaw === 'string' ? inputRaw : JSON.stringify(inputRaw)) : undefined,
            },
          };
        } else if (phase === 'end' || phase === 'result') {
          const output = data?.result ?? data?.output ?? data?.meta;
          event = {
            type: 'tool_update',
            toolCall: {
              id: toolId, title: toolName,
              status: (data?.error || data?.isError) ? 'failed' : 'completed',
              output: output ? (typeof output === 'string' ? output : JSON.stringify(output)) : undefined,
            },
          };
        } else if (phase === 'output' || phase === 'stream' || phase === 'chunk') {
          const chunk = data?.text ?? data?.delta ?? data?.output ?? '';
          if (chunk) {
            event = {
              type: 'tool_output',
              toolCall: { id: toolId, title: toolName, status: 'running' },
              content: chunk,
            };
          }
        }
        break;
      }
      case 'reasoning':
      case 'thinking': {
        const text = data?.delta ?? data?.text ?? '';
        if (text) event = { type: 'thinking', content: text, delta: text };
        break;
      }
    }

    if (event) {
      for (const listener of this.eventListeners.values()) {
        try { listener(runId, event); } catch {}
      }
    }
  }

  _request(method, params, opts = {}) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return Promise.reject(new Error('gateway not connected'));
    }

    const id = randomUUID();
    const frame = { type: 'req', id, method, params };
    const expectFinal = opts.expectFinal ?? false;

    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject, expectFinal });
      this.ws.send(JSON.stringify(frame));
    });
  }

  _scheduleReconnect() {
    if (this.closed) return;
    if (this.tickTimer) {
      clearInterval(this.tickTimer);
      this.tickTimer = null;
    }
    const delay = this.backoffMs;
    this.backoffMs = Math.min(this.backoffMs * 2, RECONNECT_MAX_MS);
    console.log(`[gateway-client] reconnecting in ${delay}ms...`);
    setTimeout(() => this.start(), delay);
  }

  _startTickWatch() {
    if (this.tickTimer) clearInterval(this.tickTimer);
    this.tickTimer = setInterval(() => {
      if (this.closed || !this.lastTick) return;
      if (Date.now() - this.lastTick > this.tickIntervalMs * TICK_TIMEOUT_MULTIPLIER) {
        console.warn('[gateway-client] tick timeout, closing');
        this.ws?.close(4000, 'tick timeout');
      }
    }, Math.max(this.tickIntervalMs, 1000));
  }

  _flushPendingErrors(err) {
    for (const [, p] of this.pending) p.reject(err);
    this.pending.clear();
  }
}

function normalizeSessionInfo(raw) {
  const usage = raw.tokenUsage;
  return {
    sessionKey: raw.sessionKey ?? raw.key ?? '',
    sessionId: raw.sessionId,
    updatedAt: raw.updatedAt,
    createdAt: raw.createdAt,
    messageCount: raw.messageCount ?? raw.turns,
    tokenUsage: usage ? {
      input: usage.inputTokens ?? usage.input ?? 0,
      output: usage.outputTokens ?? usage.output ?? 0,
      total: usage.totalTokens ?? usage.total ?? 0,
      context: usage.contextTokens ?? usage.context ?? 0,
    } : undefined,
    title: raw.title,
  };
}

let gateway = null;

function getGateway() {
  if (!gateway) {
    gateway = new OpenClawGateway();
    gateway.start();
  }
  return gateway;
}

module.exports = { OpenClawGateway, getGateway };
