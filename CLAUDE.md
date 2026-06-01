## 認証
以下のテンプレートのパターンを採用する:
https://github.com/SzTk/azure-easy-auth-google-template

テンプレートとの差異: テンプレートは Layer 2 (メールアドレス許可リスト検証) を nginx で実装しているが、このプロジェクトは単一 FastAPI コンテナ構成のため `api/core/middleware.py` の `EmailAllowlistMiddleware` で代替している。
