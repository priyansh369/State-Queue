export function subscribeQueueUpdates(onEvent) {
  let ws = null;
  let stopped = false;
  let retry = 0;
  let pingTimer = null;
  let reconnectTimer = null;

  const clearTimers = () => {
    if (pingTimer) clearInterval(pingTimer);
    if (reconnectTimer) clearTimeout(reconnectTimer);
    pingTimer = null;
    reconnectTimer = null;
  };

  const connect = () => {
    if (stopped) return;

    const url = import.meta.env.VITE_WS_URL || "ws://127.0.0.1:8000/ws";
    ws = new WebSocket(url);

    ws.onopen = () => {
      retry = 0;
      clearTimers();
      pingTimer = setInterval(() => {
        try {
          ws?.send("ping");
        } catch {
          // ignore
        }
      }, 15000);
    };

    ws.onmessage = (evt) => {
      try {
        const parsed = JSON.parse(evt.data);
        onEvent(parsed);
      } catch {
        // ignore non-JSON payloads
      }
    };

    ws.onerror = () => {
      try {
        ws?.close();
      } catch {
        // ignore
      }
    };

    ws.onclose = () => {
      clearTimers();
      if (stopped) return;
      const delay = Math.min(10000, 500 * 2 ** retry);
      retry += 1;
      reconnectTimer = setTimeout(connect, delay);
    };
  };

  connect();

  return () => {
    stopped = true;
    clearTimers();
    try {
      ws?.close();
    } catch {
      // ignore
    }
  };
}

