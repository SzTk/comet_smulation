# Visualization Enhancements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 木星・土星の軌道リング、オールト雲（球殻+トーラス）、シミュレーション年数UI（年数/周期数の双方向入力）を追加する。

**Architecture:** フロントエンド3ファイルのみ変更。`scene.js` に軌道リングとオールト雲のジオメトリを追加、`index.html` と `ui.js` に期間指定UIを追加する。バックエンド変更なし（`duration_years` は既に実装済み）。

**Tech Stack:** Three.js 0.165.0（`LineLoop`, `TorusGeometry`, `SphereGeometry`）、vanilla JS、FastAPI（バックエンド変更なし）

---

## File Map

| ファイル | 変更内容 |
|----------|----------|
| `static/js/scene.js` | `_addPlanets()` に軌道リング追加、`_addOortCloud()` 新規追加、`initScene()` から呼び出し |
| `static/index.html` | コントロールパネルに「シミュレーション期間」セクション追加 |
| `static/js/ui.js` | 軌道周期表示・年数⇔周期数連動・`duration_years` 送信を追加 |

---

## Task 1: 木星・土星 軌道リングの追加

**Files:**
- Modify: `static/js/scene.js`

### 背景

`AU_SCALE = 1/1000`（1 AU → 0.001 scene units）。x-z 平面が惑星軌道面（Three.js では y が上方向）。既存 `_addPlanets()` で t=0 の球マーカーを追加済み。

- [ ] **Step 1: `_addPlanets()` に `_buildOrbitRing()` ヘルパーと軌道リング呼び出しを追加**

`static/js/scene.js` の `_addPlanets()` 関数を以下に置き換える：

```javascript
function _buildOrbitRing(radiusAU, color) {
  const segments = 128;
  const pts = [];
  for (let i = 0; i < segments; i++) {
    const angle = (i / segments) * Math.PI * 2;
    pts.push(
      radiusAU * AU_SCALE * Math.cos(angle),
      0,
      radiusAU * AU_SCALE * Math.sin(angle)
    );
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.Float32BufferAttribute(pts, 3));
  return new THREE.LineLoop(geo, new THREE.LineBasicMaterial({ color }));
}

function _addPlanets() {
  // Jupiter sphere (t=0 position marker)
  const jGeo = new THREE.SphereGeometry(0.8, 16, 16);
  const jMat = new THREE.MeshStandardMaterial({ color: 0xc88b3a });
  const jupiter = new THREE.Mesh(jGeo, jMat);
  jupiter.position.set(5.2 * AU_SCALE * 1000, 0, 0);
  scene.add(jupiter);

  // Jupiter orbit ring
  scene.add(_buildOrbitRing(5.2, 0xc88b3a));

  // Saturn sphere (t=0 position marker)
  const sGeo = new THREE.SphereGeometry(0.6, 16, 16);
  const sMat = new THREE.MeshStandardMaterial({ color: 0xe4d191 });
  const saturn = new THREE.Mesh(sGeo, sMat);
  saturn.position.set(9.54 * AU_SCALE * 1000, 0, 0);

  // Saturn ring decoration
  const ringGeo = new THREE.RingGeometry(0.9, 1.5, 32);
  const ringMat = new THREE.MeshBasicMaterial({
    color: 0xd4b483,
    side: THREE.DoubleSide,
  });
  const ring = new THREE.Mesh(ringGeo, ringMat);
  ring.rotation.x = Math.PI / 3;
  saturn.add(ring);
  scene.add(saturn);

  // Saturn orbit ring
  scene.add(_buildOrbitRing(9.54, 0xe4d191));
}
```

- [ ] **Step 2: ブラウザで動作確認**

```bash
cd /home/taka/Documents/mygit/comet_simulation
.venv/bin/uvicorn main:app --reload
```

ブラウザで `http://localhost:8000` を開き、3Dシーンに以下を確認：
- 太陽付近に橙褐色の小円（木星軌道、半径 5.2 AU）
- その外側に淡黄色の小円（土星軌道、半径 9.54 AU）
- 既存の球マーカーが引き続き存在すること

- [ ] **Step 3: 既存テストが通ることを確認**

```bash
cd /home/taka/Documents/mygit/comet_simulation
.venv/bin/pytest -q
```

期待出力: `24 passed` （バックエンド変更なし）

- [ ] **Step 4: コミット**

```bash
git add static/js/scene.js
git commit -m "feat: add Jupiter and Saturn orbit rings to 3D scene"
```

---

## Task 2: オールト雲の可視化

**Files:**
- Modify: `static/js/scene.js`

### 背景

- 外側オールト雲: 球殻状、~20,000〜100,000 AU → 代表半径 60,000 AU（scene units: 60）
- 内側オールト雲（Hills Cloud）: トーラス状、~2,000〜20,000 AU
  - `TorusGeometry(mainRadius, tubeRadius, radialSegments, tubularSegments)`
  - mainRadius = 10,000 AU → 10 units、tubeRadius = 8,000 AU → 8 units
  - カバー範囲: 10,000 - 8,000 = 2,000 AU 〜 10,000 + 8,000 = 18,000 AU ✓
- トーラスのデフォルト向きは x-y 平面。惑星軌道面は x-z 平面なので `rotation.x = Math.PI / 2` で合わせる

- [ ] **Step 1: `_addOortCloud()` 関数を `scene.js` に追加し `initScene()` から呼び出す**

`static/js/scene.js` の `initScene()` 内、`_addPlanets()` の呼び出しの直後に `_addOortCloud();` を追加する。

ファイル末尾（`_buildLine` 関数の後）に以下を追加する：

```javascript
function _addOortCloud() {
  // Outer Oort Cloud — spherical shell (~20,000-100,000 AU, representative radius 60,000 AU)
  const outerGeo = new THREE.SphereGeometry(60000 * AU_SCALE, 32, 16);
  const outerMat = new THREE.MeshBasicMaterial({
    color: 0x8899cc,
    transparent: true,
    opacity: 0.06,
    side: THREE.DoubleSide,
  });
  scene.add(new THREE.Mesh(outerGeo, outerMat));

  // Inner Oort Cloud / Hills Cloud — torus/disk shape (~2,000-20,000 AU)
  // mainRadius=10,000 AU, tubeRadius=8,000 AU → covers 2,000-18,000 AU
  const innerGeo = new THREE.TorusGeometry(
    10000 * AU_SCALE,  // main radius
    8000 * AU_SCALE,   // tube radius
    16,                // radial segments
    64                 // tubular segments
  );
  const innerMat = new THREE.MeshBasicMaterial({
    color: 0x66aadd,
    transparent: true,
    opacity: 0.10,
    side: THREE.DoubleSide,
  });
  const innerTorus = new THREE.Mesh(innerGeo, innerMat);
  innerTorus.rotation.x = Math.PI / 2;  // align to x-z orbital plane
  scene.add(innerTorus);
}
```

`initScene()` の `_addPlanets();` の直後に追加：

```javascript
  _addPlanets();
  _addOortCloud();   // ← 追加
  _addStarField();
```

- [ ] **Step 2: ブラウザで動作確認**

`http://localhost:8000` を開き、カメラを引いて（マウスホイール）以下を確認：
- 半透明青白の大球殻（外側オールト雲、遠方）
- 半透明水色のトーラス（内側オールト雲、惑星軌道面に沿った円盤形）
- 彗星軌道の実行後、オールト雲の球殻内に彗星軌道が収まること（a=50,000 AU の場合）

- [ ] **Step 3: 既存テストが通ることを確認**

```bash
.venv/bin/pytest -q
```

期待出力: `24 passed`

- [ ] **Step 4: コミット**

```bash
git add static/js/scene.js
git commit -m "feat: add Oort Cloud visualization (outer sphere + inner Hills Cloud torus)"
```

---

## Task 3: シミュレーション期間 UI の追加

**Files:**
- Modify: `static/index.html`
- Modify: `static/js/ui.js`

### 背景

- 軌道周期の計算: `T = a^1.5`（年）。ケプラー第三法則。`a` は AU 単位。
- 例: a=50,000 AU → T = 50,000^1.5 ≈ 11,180,339 年 ≈ 1,118万年
- どちらかの入力欄が空欄の場合、`duration_years: null`（= 1周期分）を送信
- バックエンドの `SimulateRequest.duration_years: float | None` はそのまま使える

- [ ] **Step 1: `index.html` にシミュレーション期間セクションを追加**

`static/index.html` のコントロールパネル内、`<button id="runBtn">` の直前に以下を追加：

```html
      <div class="section-title">シミュレーション期間</div>
      <div id="periodDisplay" style="font-size:0.75em;color:#88aacc;min-height:1.2em;"></div>
      <label>年数 (年)</label>
      <input type="number" id="durationYearsInput" min="0" step="1000000" placeholder="自動（1周期）" />
      <label>周期数</label>
      <input type="number" id="durationPeriodsInput" min="0" step="0.5" placeholder="自動（1周期）" />
```

- [ ] **Step 2: `ui.js` に周期計算ヘルパーと連動ロジックを追加**

`static/js/ui.js` の `initUI()` 関数内に以下を追加する。`_populatePresets(presets)` の呼び出しの直後：

```javascript
  // --- Period display and duration sync ---
  let _period = Math.pow(parseFloat(document.getElementById("aInput").value) || 50000, 1.5);
  _updatePeriodDisplay(_period);

  document.getElementById("aInput").addEventListener("input", () => {
    const a = parseFloat(document.getElementById("aInput").value) || 50000;
    _period = Math.pow(a, 1.5);
    _updatePeriodDisplay(_period);
    const yVal = parseFloat(document.getElementById("durationYearsInput").value);
    if (!isNaN(yVal) && yVal > 0) {
      document.getElementById("durationPeriodsInput").value = (yVal / _period).toFixed(3);
    }
  });

  document.getElementById("durationYearsInput").addEventListener("input", () => {
    const years = parseFloat(document.getElementById("durationYearsInput").value);
    document.getElementById("durationPeriodsInput").value =
      (!isNaN(years) && years > 0) ? (years / _period).toFixed(3) : "";
  });

  document.getElementById("durationPeriodsInput").addEventListener("input", () => {
    const periods = parseFloat(document.getElementById("durationPeriodsInput").value);
    document.getElementById("durationYearsInput").value =
      (!isNaN(periods) && periods > 0) ? Math.round(periods * _period) : "";
  });
```

`initUI()` の外側（ファイル末尾）に以下を追加：

```javascript
function _updatePeriodDisplay(periodYears) {
  const periodM = (periodYears / 1e6).toFixed(2);
  document.getElementById("periodDisplay").textContent = `軌道周期: ${periodM}M年`;
}
```

- [ ] **Step 3: `_runSimulation()` で `duration_years` を送信するよう修正**

`static/js/ui.js` の `_runSimulation()` 内、`const payload = {` ブロックを以下に置き換える：

```javascript
  const durationYearsRaw = parseFloat(document.getElementById("durationYearsInput").value);
  const duration_years = (!isNaN(durationYearsRaw) && durationYearsRaw > 0)
    ? durationYearsRaw
    : null;

  const payload = {
    dark_matter: { rho0, rs },
    comet: { semi_major_axis_au: a, eccentricity: ecc, inclination_deg: inc },
    duration_years,
    timestep_years: Math.max(10, a * 0.002),
    n_output_points: 5000,
  };
```

- [ ] **Step 4: ブラウザで動作確認**

`http://localhost:8000` を開き以下を確認：

1. コントロールパネルに「シミュレーション期間」セクションが表示される
2. 初期表示で「軌道周期: 11.18M年」（a=50,000 のデフォルト値）が表示される
3. 年数欄に `2.24e7` を入力すると周期数欄が `2.000` に自動換算される
4. 周期数欄を `3` に変更すると年数欄が `33540000`（≈ 3 × 11,180,339）に更新される
5. 両欄が空欄の状態で「計算実行」→ 完了後ステータスに「軌道周期: NN.NNM年」が表示される（1周期分の計算）
6. 周期数欄に `2` を入力して「計算実行」→ 2周期分の軌道が描画される（DM なし軌道が閉じた楕円を 2周する）

- [ ] **Step 5: 既存テストが通ることを確認**

```bash
.venv/bin/pytest -q
```

期待出力: `24 passed`

- [ ] **Step 6: コミット**

```bash
git add static/index.html static/js/ui.js
git commit -m "feat: add simulation duration UI with year/period dual input and period display"
```

---

## 最終確認チェックリスト

- [ ] 木星軌道リング（橙褐色）と土星軌道リング（淡黄色）がスケール正しく表示される
- [ ] 外側オールト雲（青白球殻）が半透明で全軌道を包む
- [ ] 内側オールト雲（水色トーラス）が惑星軌道面に沿った円盤形で表示される
- [ ] `a` 変更時に軌道周期表示がリアルタイム更新される
- [ ] 年数⇔周期数が正しく相互換算される（誤差 < 1%）
- [ ] 空欄時は1周期分で動作する（従来動作と同じ）
- [ ] 全 24 pytest が通る
