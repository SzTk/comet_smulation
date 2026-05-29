// static/js/api.js
// Handles POST /simulate and SSE streaming.

export async function startSimulation(payload, onProgress, onResult, onError) {
  let resp;
  try {
    resp = await fetch("/simulate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch (e) {
    onError("サーバーへの接続に失敗しました。");
    return;
  }

  if (!resp.ok) {
    onError(`サーバーエラー: ${resp.status}`);
    return;
  }

  const { job_id } = await resp.json();

  const es = new EventSource(`/simulate/${job_id}/stream`);

  es.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.type === "progress") {
      onProgress(msg.percent);
    } else if (msg.type === "result") {
      es.close();
      onResult(msg);
    }
  };

  es.onerror = () => {
    es.close();
    onError("ストリーム接続エラー。");
  };
}

export async function fetchPresets() {
  const resp = await fetch("/presets");
  return resp.json();
}
