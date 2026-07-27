# HCI Vendor Command Discovery 設計

## 1. 目的

HCI Vendor Command Discoveryは、最大2つのシリアルポートからHCI通信を
リアルタイム取得し、OGF `0x3F`のVendor Specific CommandをOpcode別に比較する
補助ツールである。Analyzerが保存したJSONLの追加読込にも対応する。

利用者が各キャプチャへ実験時の既知パラメーター値を付与し、ツールはCommand
Parameter内の格納位置、整数型、符号、エンディアン、Enum候補を提示する。
利用者は解析対象Commandのパラメーターを自分で定義し、1項目ずつ既知値を
キャプチャーへ割り当てる。推定候補を確定した結果は解析プロジェクトへ蓄積し、
最終的にCommand Console用定義を出力する。

## 2. リアルタイム取得

- Analyzerと同じ`DualSerialMonitor`、`H4StreamDecoder`、`HciParser`を使用する
- 最大2ポートを同時監視する
- 同一ポートを2欄で選択した場合は1ポートだけ監視する
- 2ポート共通ボーレートは最大3 Mbpsとする
- 受信処理はGUIスレッドと分離し、Queue経由で画面へ反映する
- シリアル設定の保存形式はAnalyzerを踏襲する
- Discovery固有設定が存在しない初回はAnalyzerの保存値を初期値にする

Vendor HCI Commandは解析対象として保存する。H4 Packet Indicator `0x04`の
HCI Eventは解析成否にかかわらず一覧表示し、パラメーター推定対象にはしない。
RACEはType、Command ID、Payloadを一覧表示するが、現時点ではパラメーター
推定対象にしない。

## 3. キャプチャー一覧

標準表示は重複をまとめず、Timestamp順に1キャプチャー1行で表示する。
オプション`Group duplicate captures`を有効にした場合だけ、Protocol、
Opcode、Event名と関連Opcode、またはRACE Type／Command ID、
Parameter／Payloadが同じ行を集約する。

`選択Opcodeのみ表示`を有効にした場合、現在選択中のVendor Commandと、
Command Complete／Command Status内のOpcodeまたは直前Commandとの関連付けが
同じHCI Eventだけを表示する。関連Opcodeを特定できないEventとRACEは非表示にする。

利用者は1件または複数件を選択して解析対象から削除できる。削除操作は
Undo用スタックへ保持し、直前の削除単位で元の時系列位置へ復元できる。

## 4. 人とツールの役割

### 4.1 利用者が行うこと

- コマンドの目的とパラメーター名を把握する
- 安全な範囲で、原則1項目ずつ設定値を変更して通信を記録する
- PHY、Channelなどのパラメーター名、種別、選択肢を定義する
- 選択したキャプチャーへ実際に設定した既知値を割り当てる
- 推定候補を確認し、実機仕様と照合する
- 定義を確定する前に実機で検証する

### 4.2 ツールが行うこと

- H4 CommandからOpcode、OGF、OCF、Parameterを抽出する
- 同一Opcodeのキャプチャをグループ化する
- Command Complete／Command StatusをOpcodeで関連付ける
- Vendor Specific Event `0xFF`を直前のVendor Commandへ参考情報として関連付ける
- キャプチャ間で変化したByte Offsetを抽出する
- 既知値と一致するデータ型候補を列挙する
- レビュー必須の外部JSON定義案を生成する

## 5. Analyzerの汎用ベンダー解析

### 5.1 Vendor Specific Command

OpcodeはHCI標準と同じlittle-endianで読み、次式で分解する。

```text
OGF = (Opcode >> 10) & 0x3F
OCF = Opcode & 0x03FF
```

OGFが`0x3F`なら、静的Command定義に存在しなくても正常な
`HCI_Command`として受理する。

```json
{
  "opcode": "0xFC41",
  "ogf": 63,
  "ocf": 65,
  "parameter_total_length": 4,
  "vendor_specific": true,
  "parameters": {
    "raw_hex": "13 F6 34 12",
    "raw_bytes": [19, 246, 52, 18]
  }
}
```

### 5.2 Vendor Command Response

Command CompleteとCommand Statusに含まれるOpcodeのOGFが`0x3F`なら、
静的Command定義がなくても正常なEventとして受理する。

Command CompleteのReturn ParameterレイアウトはVendor依存であるため、
固定長検証を行わずRAWを保持する。先頭Byteが存在する場合はStatus候補としても
表示するが、その意味はVendor仕様で確認する。

### 5.3 Vendor Specific Event

Event Code `0xFF`は`HCI_Vendor_Specific_Event`として受理し、
Parameter Total LengthとParameter RAWを保持する。

Event内に元CommandのOpcodeが含まれる保証はない。Discoveryでは直前のVendor
Commandへ参考情報として関連付けるが、確定的な応答関連付けとは扱わない。

## 6. JSONL読込

複数のAnalyzer JSONLを同時に選択できる。新しい汎用ベンダー解析形式だけでなく、
過去ログの`UNKNOWN_OPCODE`レコードもH4 RAWから再抽出する。

不正JSON行は他の行の読込を止めず、読込警告として件数と内容を表示する。

## 7. ユーザー定義パラメーターと既知値

利用者はパラメーターごとに次の情報を定義する。

```text
Name / Display Name / Kind / Unit / JSON Number Format / Choices / Description
```

Kindは`auto`、`unsigned`、`signed`、`enum`、`boolean`、`bit_field`、
`raw_bytes`を持つ。初版の自動推定は`auto`、整数、Enumを対象とし、
Bit FieldとRaw Bytesはユーザー定義を保持するが自動候補を生成しない。

JSON Number Formatは`decimal`または`hex`とし、パラメーターごとに指定する。
既存プロジェクトでこの項目がない場合は`decimal`として読み込む。

一覧から複数キャプチャーを選択し、現在選択中のパラメーターについて既知値を
一括で割り当てる。RACE行には既知値を割り当てない。

同じパラメーターについて最低2キャプチャへ注釈が必要である。推定精度を上げる
ため、3種類以上の値を含む4キャプチャ以上を推奨する。

## 8. 自動推定

初版は次の型を、全Offsetに対して総当たりして既知値との完全一致を調べる。

- `uint8` / `int8`
- `uint16_le` / `int16_le`
- `uint16_be` / `int16_be`
- `uint32_le` / `int32_le`
- `uint32_be` / `int32_be`
- `uint48_le` / `int48_le`
- `uint48_be` / `int48_be`
- `enum_u8`
- `enum_u16_le` / `enum_u16_be`
- `enum_u24_le` / `enum_u24_be`
- `enum_u32_le` / `enum_u32_be`

候補はOffset、型、サイズ、サンプル数、異なる値の数、Confidenceを持つ。

| Confidence | 条件 |
|---|---|
| high | 4サンプル以上かつ3種類以上の値 |
| medium | 2サンプル以上かつ2種類以上の値 |
| low | 上記以外 |

複数候補が一致する場合はすべて表示する。正値だけを使用した場合などは、
符号あり・なしを一意に判定できないためである。

48 bit型はBluetooth Device Addressなどの6 byte整数を対象とする。例えば既知値
`0x00006BC6967E`に対して、Parameter内の`7E 96 C6 6B 00 00`を
`uint48_le`候補として検出する。

Enum値は連続している必要はない。例えば`A = 0x0123`、
`B = 0x2512`という対応を`enum_u16_le`として保持できる。この場合のByte列は
それぞれ`23 01`、`12 25`となる。

Enumの既知値として選択肢名だけを入力した場合、Byte列からLittle Endianと
Big Endianを一意に判定できないことがある。その場合は両方を候補として表示し、
利用者が候補確定または配置の手動設定で選択する。

### 8.1 配置の手動設定

自動推定候補が存在しない、または正しい候補が先頭にない場合、利用者は選択した
パラメーターについてOffsetと型を直接指定できる。

手動設定は`source: manual`を持つ確定候補として解析プロジェクトへ保存する。
完成定義出力時に、型とSizeの一致、Parameter Template範囲、他フィールドとの
Byte重複を検証する。

## 9. 解析プロジェクト

`vendor_projects/*.json`へ次を保存する。

- 対象OpcodeとCommand Name
- ユーザー定義パラメーター
- パラメーターごとの候補と確定結果
- Vendor HCI Command、HCI EventおよびRACEのキャプチャー
- キャプチャーへ割り当てた既知値と関連応答

プロジェクトを再度開くことで、パラメーターを1項目ずつ追加解析できる。
`vendor_projects/*.json`はGit管理対象外とする。

## 10. 定義案・完成定義出力

既定保存先は`vendor_definitions/`とし、ファイル名は
`vendor_0xXXXX_definition_draft.json`とする。定義案は次の情報を持つ。

- Schema Version
- Opcode、OGF、OCF
- 利用者が入力したCommand Name
- 固定Parameter Length候補
- 各パラメーターの全候補
- 先頭候補を使ったOffset／Type案
- 最初のキャプチャを使った`parameter_template_hex`
- 推定値から取得したDefaultとEnum Choices
- パラメーターごとのJSON Number Format
- `review_required: true`
- 未確定のResponse Kind

`vendor_definitions/*.json`はGit管理対象外とする。

Command Consoleは接続設定欄の`Vendor定義読込`からJSONを選択する。
Schema、Opcode、Template長、Field Offset、型、範囲、Field重複を検証し、
不正な定義は読み込まない。

`review_required: true`を含む場合は、Command名とOpcodeを示す確認ダイアログを
表示する。利用者が承認した場合だけ`Vendor Specific`カテゴリへ追加する。

送信Parameterは`parameter_template_hex`を複製し、各FieldのOffsetへGUI入力値を
指定型・Byte Orderで上書きして生成する。これにより、意味が未解明の固定Byteを
元キャプチャと同じ値で保持する。

`decimal`指定時はDefaultをJSON数値、Enum Choicesのキーを10進文字列で出力する。
`hex`指定時はDefaultとEnum Choicesのキーを型サイズに合わせてゼロ埋めした
`"0x0123"`形式の文字列で出力する。Command ConsoleはJSON数値、10進文字列、
16進文字列を内部整数へ正規化してから範囲とChoicesを検証する。送信コマンドの
可読ログでは、`hex`指定されたVendorパラメーターを同じ桁数の16進文字列で
表示する。Command Consoleの数値入力欄でもDefaultと復元値へ同じ表記を適用する。

同じByteを複数Fieldが使用する定義、組み込みOpcodeを置換する定義、
同一Command Name・Versionが重複する定義は拒否する。同一OpcodeでもCommand
NameまたはVersionが異なる定義は別バリアントとして読み込める。読み込んだ定義は永続化せず、
Command Consoleを再起動した場合は再読込する。

全注釈から従来形式のレビュー必須定義案を出力できる。さらに、ユーザーが
候補を確定したパラメーターだけを使用して、Command Consoleが直接読み込める
完成定義を出力できる。未解明Byteは先頭キャプチャーのTemplate値を維持する。
Parameter Lengthが`0`のCommandに限り、確定パラメーターがなくても
`parameters: []`の完成定義を出力できる。Parameter Byteを持つCommandでは、
従来どおり少なくとも1つの確定パラメーターを必要とする。

## 11. 制約

次の形式は初版の自動推定対象外、または一意に推定できない可能性がある。

- 複数パラメーターを同時に変更したキャプチャ
- Bit Field
- 倍率やOffsetによる変換値
- 可変長配列と条件依存レイアウト
- Sequence Number、Timestamp、乱数
- Checksum、CRC、暗号化、難読化
- 非同期Vendor Eventの確定的なCommand関連付け

推定結果は相関を示すもので、パラメーターの意味や送信安全性を保証しない。
