# Chat Extractor (スタンドアロン版)

ver 1.0.0

クリップボード内のHTMLからAIとの会話を抽出し、Markdown形式に変換します。

> [!IMPORTANT]
> このツールは現在 **Windows専用** です。Windows固有のクリップボード形式と通知システムに依存しています。


## 特徴
- クリップボードから直接読み取り（手動でのファイル保存は不要）。
- Windows HTMLクリップボード形式をサポート。
- AIモデル（Gemini、ChatGPT、Claudeなど）を自動検出。
- HTML/テキストをクリーンなMarkdownに変換。
- Windowsのトースト通知をサポート。
- 出力ディレクトリやファイル名形式をカスタマイズ可能。

## クイックスタート (Windows)

1. **前提条件**:
   - **Python 3.10+**: Pythonがインストールされ、PATHに追加されていることを確認してください。ターミナルで `python --version` を実行して確認できます。

2. **依存関係のインストール**:
   ```bash
   pip install pyperclip beautifulsoup4 PyYAML
   ```

3. **スクリプトの実行**:
   ブラウザからAIとの会話をコピーし、以下のコマンドを実行します：
   ```bash
   python run.py
   ```
   > [!TIP]
   > **推奨**: クリーンなHTML構造を提供することで、最良のMarkdown出力を得られます。
   > 
   > **ワークフロー**: `すべて選択 (Ctrl+A)` -> `右クリック` -> `検証 (Inspect)` -> `チャット要素ツリーの最上部へ移動` -> `右クリック` -> `コピー` -> `外部HTMLをコピー (Copy outer HTML)`。

4. **(オプション) サイレントランチャー & ホットキー**:
   `launch.vbs` を使用して、コンソールウィンドウを表示せずにスクリプトを実行できます。
   - **ショートカットの作成**: `launch.vbs` を右クリック -> `送る` -> `デスクトップ (ショートカットを作成)`。
   - **ホットキーの設定**: 作成されたショートカットを右クリック -> `プロパティ` -> `ショートカット` タブ -> `ショートカット キー` をクリック -> 任意のキー（例: `Ctrl+Alt+X`）を押す -> `OK`。
   これで、ホットキーひとつで即座にチャットを抽出できるようになります。

## 設定
ツールは以下の順序で `config.yaml` を自動的に検索します：
1.  **ローカルディレクトリ**: `run.py` と同じフォルダ（ポータブル利用に便利）。
2.  **アプリデータ (App Data)**: `%APPDATA%\ai-chat-extractor\config.yaml` (Windowsの標準的な場所)。

### 初回起動セットアップ
`config.yaml` が見つからない場合、スクリプトは **対話型CLIセットアップ** を開始し、基本設定を案内します：
- **出力ディレクトリ**: 抽出したMarkdownファイルを保存する場所。
- **トースト通知**: Windowsシステム通知の有効/無効。

設定はデフォルトで `%APPDATA%` の場所に保存されます。

### 手動設定
`config.default.yaml` を `config.yaml` にコピーして、設定を直接変更することもできます：
- `output.dir`: Markdownファイルを保存する場所。
- `output.filename`: 保存するファイルの名前形式。
- `clip.enabled`: 結果をクリップボードに書き戻すかどうか。
- `clip.notice.toast.enabled`: Windowsの通知を表示するかどうか。

## 新しいモデルの追加
`models/` ディレクトリに YAML プロファイルを追加してください。既存のプロファイルを参考にしてください。

## リポジトリの管理
このツールを別のプロジェクトの一部として使用する場合は、**Git Submodule** として追加することを検討してください：
```bash
git submodule add https://github.com/gsr-4325/ai-chat-extractor.git scripts/chat_extractor
```
