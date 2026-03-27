# リリース手順

バージョンアップのたびに以下を実行する。

## 手順

1. **CHANGELOG.md を更新する**
   - `## [X.Y.Z] - YYYY-MM-DD` の形式で変更内容を記述

2. **コミットする**
   ```
   git add .
   git commit -m "chore: release vX.Y.Z"
   ```

3. **タグを作成してプッシュする**
   ```
   git tag vX.Y.Z
   git push origin master
   git push origin vX.Y.Z
   ```

4. **GitHub Actions が自動でexeをビルドしてリリースを作成する**
   - タグのプッシュをトリガーに `.github/workflows/release.yml` が起動する
   - Windows exe（zip）が GitHub Release に自動アップロードされる
   - 進捗は `https://github.com/gsr-4325/ai-chat-extractor/actions` で確認できる
   - リリースは `https://github.com/gsr-4325/ai-chat-extractor/releases` に公開される

## バージョン番号の規則（セマンティックバージョニング）

```
vMAJOR.MINOR.PATCH

例:
  v1.0.0 → 初回リリース
  v1.0.1 → バグ修正
  v1.1.0 → 後方互換のある機能追加
  v2.0.0 → 破壊的変更
```

## 別PCへのインストール方法

1. GitHub Releases ページから `ai-chat-extractor-vX.Y.Z-windows.zip` をダウンロード
2. 任意の場所に解凍する
3. `ai-chat-extractor.exe` を実行（初回はセットアップウィザードが起動）
4. タスクスケジューラやショートカットに登録して使用
