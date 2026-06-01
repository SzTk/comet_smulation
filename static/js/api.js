// static/js/api.js
// Handles POST /simulate and SSE streaming.

import { clearTokenCache, getIdToken } from "./gsi-auth.js";

async function _authHeaders() {
    const token = await getIdToken();
    return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function startSimulation(payload, onProgress, onResult, onError) {
    const body = JSON.stringify(payload);

    async function _post() {
        return fetch("/simulate", {
            method: "POST",
            headers: { "Content-Type": "application/json", ...(await _authHeaders()) },
            body,
        });
    }

    let resp;
    try {
        resp = await _post();
    } catch (e) {
        onError("サーバーへの接続に失敗しました。");
        return;
    }

    if (resp.status === 401) {
        clearTokenCache();
        try {
            resp = await _post();
        } catch (e) {
            onError("サーバーへの接続に失敗しました。");
            return;
        }
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
    const resp = await fetch("/presets", { headers: await _authHeaders() });
    return resp.json();
}
