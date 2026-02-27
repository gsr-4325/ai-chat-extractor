# プラグインのパラメータ設計 - Claude

Model Profile: claude
Extracted Date: 2026-02-27 18:26:29
---

## 1. User

プラグインを追加しようかと思っている。各プラグインのパラメータの設計などを提案してほしい。

## 2. AI

ファイルの内容を確認します。 ファイルを表示しました, コマンドを実行しました  アップロードディレクトリにファイルが見つかりませんでした。ただ、ファイルの内容がコンテキストに含まれている可能性があるので確認しますが、今回はテキストとしても表示されていないようです。

ファイルが正しくアップロードされていない可能性があります。お手数ですが、もう一度ファイルをアップロードしていただけますか？ファイルの内容を確認した上で、各プラグインのパラメータ設計を提案させていただきます。

もしファイルの内容を直接テキストで貼り付けていただいても対応できます。

## 3. User

貼りました。プラグインを追加しようかと思っている。各プラグインのパラメータの設計などを提案してほしい。

## 4. AI

ドキュメントをじっくり読みました。すでにClaude SonnetとGeminiの両方から提案が出ていて、かなり議論が進んでいますね。ここでは、既出の提案を踏まえつつ、もう一段具体的な設計判断を整理します。

### 前提の確認

3つのプラグインはすべて「プロンプト生成時に介入するモジュール」であり、分析・アウトライン・本文生成の3フェーズに注入するプロンプト断片を持つ。DBスキーマの話ではなく、**生成パイプラインの制御ノブ**の設計。

### 1. 反復と対比を統合すべきか

**別プラグインで正解。** 両方の提案が一致しているし、理由も明確なのでここは動かさなくていい。

ただし `patterning_pack` のような薄い束ね層は不要だと考える。理由は、プラグインのON/OFFはそもそも設定ファイルで列挙するだけなので、「2つ書く手間」と「束ね層の管理コスト」を比較すると後者の方が重い。やるなら単にドキュメントに「この2つはセットで使うことを推奨」と書けば済む。

### 2. 各プラグインのパラメータ設計

ここからが本題。既出の提案から**実際に効くもの**と**v1では過剰なもの**を切り分ける。

#### 設計原則

- パラメータは「プロンプトに変換できるもの」だけ入れる。分析出力用のフィールド（`occurrences`, `interpretive_vectors`など）はプラグインのパラメータではなく分析スキーマ側の話
- v1は「これがないと介入できない」最小セット。v2は「品質を上げる制御」

#### Plugin: `repetition`

**何をするプラグインか**: 反復モチーフの抽出指示、配置指示、表現制約を各フェーズのプロンプトに注入する。

##### v1 パラメータ

 yaml ``` yaml
repetition:# --- 分析フェーズ用 ---extract_top_k:3# 抽出する反復要素の上限数salience_threshold:0.5# これ以下は捨てる# --- アウトライン・本文フェーズ用 ---variation_mode:drift# drift（意味が変わる）/ intensify（強度が変わる）/ subvert（最後に裏切る）prose_echo_style:near_repeat# near_repeat / verbatim_fragment / implicitforbid_mechanical_counting:true# 「三度目の〜」のような機械的カウント表現を禁止
``` 

**各パラメータの意図:**

`variation_mode` は反復の「型」を1つ選ばせる。Claudeの `semantic_drift` (float) とGeminiの `repetition_trajectory` (enum) の両方が出ていたが、生成プロンプトに変換するなら**enum**の方が指示として明確に効く。floatはAIにとって「0.6の変容度」が何を意味するか曖昧になる。

`prose_echo_style` は本文生成への直接的な制約。`near_repeat` は「同じ文構造を使いつつ単語を変える」、`verbatim_fragment` は「一部のフレーズをそのまま再使用する」、`implicit` は「直接的な反復を避け読者が気づくかどうかの境界に置く」。

`forbid_mechanical_counting` は地味だが重要。AIは反復を指示されると「三度目のノック」「また同じ音が」のように**反復していることを説明する**癖がある。これを明示的に封じる。

##### v2 追加

 yaml ``` yaml
# --- 評価・監査用 ---semantic_drift_floor:0.2# subvertモードの場合、最終出現で最低これだけ意味が変わっていることreader_recognition:explicit# explicit（読者に気づかせる）/ subliminal（気づかなくても効く）max_occurrences:4# これ以上出すと冗長
```  

#### Plugin: `contrast`

**何をするプラグインか**: 対比構造の抽出指示、ビートへの配置指示、描写上の制約を注入する。

##### v1 パラメータ

 yaml ``` yaml
contrast:# --- 分析フェーズ用 ---extract_top_k:2salience_threshold:0.5# --- アウトライン・本文フェーズ用 ---axis:info# value / space / time / info / temperature / inner_outerevolution:diverging# static / diverging / converging / invertedprose_rendering:sensory# sensory / dialogue / juxtaposition / silenceforbid_explicit_comparison:true# 「〜とは対照的に」のような地の文での直接比較を禁止
``` 

**各パラメータの意図:**

`axis` と `evolution` は既出の通りで異論なし。

`prose_rendering` が鍵。`sensory` は「温度、光、音の対比で表現する」、`dialogue` は「台詞の温度差で表現する」、`juxtaposition` は「二つの場面を切り替えで並置する」、`silence` は「一方だけを描写し、もう一方の不在で対比を作る」。特に `silence` は強力で、AIが最も苦手とする手法（書かないことで書く）。

`forbid_explicit_comparison` は `repetition` の `forbid_mechanical_counting` と同じ思想。AIは対比を指示されると「一方では〜、他方では〜」と説明文を書く。これを封じる。

##### v2 追加

 yaml ``` yaml
visibility_at_climax:0.8# クライマックスでの対比の明示度（0=まだ暗示 / 1=完全に露出）resolution_type:inverted# resolved / unresolved / inverted / collapsedrelated_repetitions:[]# repetition プラグインの要素IDとのリンク
``` 

`visibility_at_climax` はGeminiの `contrast_visibility` とClaude Sonnetの同名パラメータの統合版。ただし「全体の明示度」ではなく「クライマックス時点での明示度」に限定した。理由は、対比の明示度は物語の進行に伴って変化するのが普通で、固定値にすると生成プロンプトで使いにくいから。「クライマックスまでにどこまで見せるか」なら一点指定で実用的。

#### Plugin: `motif_residual`

**何をするプラグインか**: 因果の外にある「意味未確定の物理的存在」の抽出指示、配置指示、そして**説明禁止の強制**を注入する。

これが3つの中で最も設計思想が独自で、かつ最もAIに対する制約が強いプラグイン。

##### v1 パラメータ

 yaml ``` yaml
motif_residual:# --- 分析フェーズ用 ---extract_top_k:2# 1作品から抽出する未確定モチーフの上限# --- アウトライン・本文フェーズ用 ---physical_form:null# 具体的な物体名（生成時に指定 or 分析から移植）intensity:0.5# 0.2=雰囲気 / 0.5=記憶に残る / 0.8=解釈の重心 / 1.0=作品の核structural_position:post-climax# opening / early / mid / late / post-climax / recurringexplanation_prohibition:true# **常にtrue。これがこのプラグインの存在理由**relation_to_causality:none# none / indirect（原則noneかindirectのみ）recurrence:2# 出現回数
``` 

**設計上の重要な判断:**

`explanation_prohibition` をパラメータにすること自体に意味がある。trueしか許さないなら定数でいいのでは？と思うかもしれないが、**「禁止されている」ということが設定ファイル上に可視化されている**ことが重要。このプラグインを使う人間（つまりGoxuさん自身）が、「このモチーフは説明禁止が前提だ」ということを毎回目にすることになる。

`physical_form` が `null` の場合、分析フェーズで原作から抽出されたものを使う。明示的に指定する場合は「割れた鏡」「位置がずれる椅子」のような具体物。抽象語（「孤独」「不安」など）が入った場合はバリデーションで弾く。

`intensity` はfloatにしている。ここだけ反復・対比と設計が違う理由は、未確定モチーフの「強さ」は「プロンプトでの出現回数や描写の長さ」に直接マッピングできるから。enumでは粒度が足りない。

##### v2 追加

 yaml ``` yaml
sensory_channel:sight# sight / sound / smell / touch / taste / proprioceptionphysicality_floor:0.7# 0=抽象 / 1=完全に物理的。これ以下なら警告narrative_layer:subtext# surface（人物も気づく）/ subtext（読者だけ）/ meta（構造言及）interpretive_vectors:[]# 監査用。生成には使わない。分析時に複数の解釈方向を列挙
``` 

`sensory_channel` はClaude Sonnetの提案。同意する。嗅覚・触覚のモチーフは視覚より説明しにくいため、residualとしての持続力が高い。生成時に「視覚に偏らない」制約として機能する。

`physicality_floor` は既存提案の `motif_physicality_level` を「下限」として再定義。上限を設ける意味はない（物理的であるほど良い）ので、下限だけ設定してバリデーションに使う。

### 3. 介入ポイントの整理（3プラグイン共通）

各プラグインが4フェーズのどこにどう介入するかを一覧にする。

 | フェーズ | `repetition` | `contrast` | `motif_residual` |
| --- | --- | --- | --- |
| **analyze** | level分類で反復候補を抽出、beat_id紐づけ必須 | axis分類で対比候補を抽出、carriers特定 | 因果に関与しないが印象的な物理的存在を抽出 |
| **outline** | どのbeatで再出現させるか、variation_modeに沿った変奏設計 | どのbeatで対置させるか、evolutionの方向設計 | 因果ラインの**外側**に配置。beat上の「空白」に置く |
| **prose** | echo_style制約 + mechanical_counting禁止 | rendering制約 + explicit_comparison禁止 | **explanation_prohibition** + 質感描写のみ許可 |
| **audit** | driftが設計通りか、冗長な反復がないか | 対比がテーマの説教に化けていないか | **AIが意味を説明していないか**（最重要チェック） | 

`motif_residual` のauditが最も重要で、ここでの検出ルールは厳格にすべき。具体的には：

- 地の文で「それは〜を象徴していた」「〜を意味するかのように」が出たら即リジェクト
- 登場人物が未確定モチーフについて「分析」「解釈」「説明」する台詞があればリジェクト
- モチーフへの言及が「知覚描写」（見える、触れる、匂う）以外の形をとっていたら警告

### 4. 実装優先順位

1. **`motif_residual`** — 概念の独自性が最も高く、かつ「AIの説明癖を封じる」という即効性がある。v1のパラメータ数が最小（6個）で実装が軽い
2. **`repetition`** — variation_modeとprose_echo_styleだけで生成品質に目に見える差が出る
3. **`contrast`** — prose_renderingの選択肢（特にsilence）が強力だが、効果を出すにはoutline設計の精度が必要なので、先の2つが安定してから

### 5. 統合しない代わりの「接着」について

Geminiが提案した `patterning_coupling` は筋が良いが、v1では不要。理由は、反復と対比の関係は `related_contrasts` / `related_repetitions` の相互参照IDで十分に表現でき、別途「接着層」のパラメータを管理するコストに見合わない。

v2以降で「反復が対比を増幅するパターン」が頻出して、相互参照IDだけでは生成プロンプトに十分な指示が出せないと判明した場合にのみ検討すればいい。

何か特定のプラグインについてさらに掘り下げたい部分があれば。
