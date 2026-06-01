# 認証設計: Azure Easy Auth + Google JWT (単一コンテナ)

## 概要

Azure Container Apps の Easy Auth と Google JWT を組み合わせた4層認証をFastAPI単一コンテナで実装する。
参考テンプレート: https://github.com/SzTk/azure-easy-auth-google-template

## アーキテクチャ

```
[Browser]
    ↓ HTTPS
[Layer 1] Azure Easy Auth
    ↓ X-MS-CLIENT-PRINCIPAL-NAME ヘッダー付与
[Layer 2] FastAPI: EmailAllowlistMiddleware
    ↓ 許可リスト通過のみ
[Layer 3] Frontend (GSI): Authorization: Bearer <id_token>
    ↓
[Layer 4] FastAPI: require_authorized_user Depends (JWT検証)
```

- Layer 1–2: フロントエンド・静的ファイルを保護
- Layer 3–4: API エンドポイントを保護
- ローカル開発: `AUTH_ENABLED=false` (デフォルト) で全層スキップ

## ファイル構成

| ファイル | 役割 |
|---|---|
| `api/core/config.py` | 新規: Pydantic Settings (`AUTH_ENABLED`, `GOOGLE_CLIENT_ID`, `ALLOWED_EMAILS`) |
| `api/core/auth.py` | 新規: JWKS キャッシュ + JWT 検証 + `require_authorized_user` Depends |
| `api/core/middleware.py` | 新規: `EmailAllowlistMiddleware` (Layer 2, X-MS-CLIENT-PRINCIPAL-NAME 検証) |
| `api/routes.py` | 変更: 保護対象エンドポイントに `Depends(require_authorized_user)` 追加 |
| `main.py` | 変更: `EmailAllowlistMiddleware` 登録 |
| `static/js/gsi-auth.js` | 新規: GSI サイレントサインイン (`getIdToken()` 関数) |
| `static/index.html` | 変更: GSI ライブラリタグ追加 |
| `static/js/api.js` | 変更: `startSimulation` / `fetchPresets` にトークン付与、401 時リトライ |
| `requirements.txt` | 変更: `python-jose[cryptography]`, `pydantic-settings` 追加 |

## 各層の詳細

### Layer 2: EmailAllowlistMiddleware

- `AUTH_ENABLED=false` の場合は何もしない (通過)
- `X-MS-CLIENT-PRINCIPAL-NAME` ヘッダーが存在しない場合 → 403
- ヘッダー値が `ALLOWED_EMAILS` に含まれない場合 → 403
- 静的ファイルを含む全リクエストに適用

### Layer 4: require_authorized_user

- `Authorization: Bearer <token>` を優先、なければ `X-MS-TOKEN-GOOGLE-ID-TOKEN` を使用
- Google JWKS (`https://www.googleapis.com/oauth2/v3/certs`) でRS256署名検証
- JWKS は1時間キャッシュ、検証失敗時は1回だけ再取得してリトライ
- `email_verified` が `false` → 401
- email が `ALLOWED_EMAILS` に含まれない → 403
- 成功時は email 文字列を返す (`None` when `AUTH_ENABLED=false`)

### Frontend (GSI)

- `window.onGoogleLibraryLoad` で自動サイレントサインイン
- `getIdToken()` は有効なトークンをキャッシュして返す (有効期限60秒前に再取得)
- API 呼び出し前に `getIdToken()` を実行し `Authorization` ヘッダーに付与
- 401 レスポンス時: キャッシュクリア → 再取得 → 1回リトライ

## 環境変数

| 変数 | デフォルト | 説明 |
|---|---|---|
| `AUTH_ENABLED` | `false` | 認証を有効化 (本番では `true`) |
| `GOOGLE_CLIENT_ID` | `""` | Google OAuth 2.0 クライアントID |
| `ALLOWED_EMAILS` | `[]` | 許可するメールアドレスリスト (JSON配列またはカンマ区切り) |

## 保護対象エンドポイント

| エンドポイント | 認証 | 理由 |
|---|---|---|
| `POST /simulate` | 必須 | シミュレーション実行の入口 |
| `GET /presets` | 必須 | アプリ利用者のみに公開 |
| `GET /simulate/{job_id}/stream` | 不要 | SSE は `EventSource` でヘッダー付与不可。`job_id` (UUID) がケイパビリティトークンとして機能するため許容 |
| `GET /health` | 不要 | インフラ監視用 |

## テスト方針

- `api/core/tests/test_auth.py`: JWKS をスタブして JWT 検証ロジックをユニットテスト
  - 有効トークン → email 返却
  - 無効署名 → 401
  - 未検証メール → 401
  - 許可リスト外メール → 403
  - `AUTH_ENABLED=false` → None 返却
- `api/core/tests/test_middleware.py`: ミドルウェアの許可リスト検証をテスト

## Azure デプロイ手順 (概要)

1. Google Cloud Console で OAuth 2.0 クライアントID を作成
2. Container App に環境変数 (`AUTH_ENABLED`, `GOOGLE_CLIENT_ID`, `ALLOWED_EMAILS`) を設定
3. `deploy/enable-auth.sh` (テンプレートから流用) で Easy Auth を有効化
