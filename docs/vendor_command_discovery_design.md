# HCI Vendor Command Discovery 設計

## 1. 目的

HCI Vendor Command Discoveryは、HCI Analyzerが保存したJSONLを入力として、
OGF `0x3F`のVendor Specific CommandをOpcode別に比較する補助ツールである。

利用者が各キャプチャへ実験時の既知パラメーター値を付与し、ツールはCommand
Parameter内の格納位置、整数型、符号、エンディアン、Enum候補を提示する。
推定結果だけでコマンド定義を確定せず、レビュー必須のJSON定義案を出力する。

## 2. 人とツールの役割

### 2.1 利用者が行うこと

- コマンドの目的とパラメーター名を把握する
- 安全な範囲で、原則1項目ずつ設定値を変更して通信を記録する
- 各キャプチャへ実際に設定した`name=value`を入力する
- 推定候補を確認し、実機仕様と照合する
- 定義を確定する前に実機で検証する

### 2.2 ツールが行うこと

- H4 CommandからOpcode、OGF、OCF、Parameterを抽出する
- 同一Opcodeのキャプチャをグループ化する
- Command Complete／Command StatusをOpcodeで関連付ける
- Vendor Specific Event `0xFF`を直前のVendor Commandへ参考情報として関連付ける
- キャプチャ間で変化したByte Offsetを抽出する
- 既知値と一致するデータ型候補を列挙する
- レビュー必須の外部JSON定義案を生成する

## 3. Analyzerの汎用ベンダー解析

### 3.1 Vendor Specific Command

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

### 3.2 Vendor Command Response

Command CompleteとCommand Statusに含まれるOpcodeのOGFが`0x3F`なら、
静的Command定義がなくても正常なEventとして受理する。

Command CompleteのReturn ParameterレイアウトはVendor依存であるため、
固定長検証を行わずRAWを保持する。先頭Byteが存在する場合はStatus候補としても
表示するが、その意味はVendor仕様で確認する。

### 3.3 Vendor Specific Event

Event Code `0xFF`は`HCI_Vendor_Specific_Event`として受理し、
Parameter Total LengthとParameter RAWを保持する。

Event内に元CommandのOpcodeが含まれる保証はない。Discoveryでは直前のVendor
Commandへ参考情報として関連付けるが、確定的な応答関連付けとは扱わない。

## 4. JSONL読込

複数のAnalyzer JSONLを同時に選択できる。新しい汎用ベンダー解析形式だけでなく、
過去ログの`UNKNOWN_OPCODE`レコードもH4 RAWから再抽出する。

不正JSON行は他の行の読込を止めず、読込警告として件数と内容を表示する。

## 5. 注釈

Treeviewで1つのキャプチャを選択し、次の形式で実験時の既知値を入力する。

```text
channel=19, power=-10, mode=tx
```

区切りにはカンマ、セミコロン、改行を使用できる。値は文字列として保持し、
整数推定時は10進数または`0x`付き16進数として解釈する。

同じパラメーターについて最低2キャプチャへ注釈が必要である。推定精度を上げる
ため、3種類以上の値を含む4キャプチャ以上を推奨する。

## 6. 自動推定

初版は次の型を、全Offsetに対して総当たりして既知値との完全一致を調べる。

- `uint8` / `int8`
- `uint16_le` / `int16_le`
- `uint16_be` / `int16_be`
- `uint32_le` / `int32_le`
- `uint32_be` / `int32_be`
- `enum_u8`

候補はOffset、型、サイズ、サンプル数、異なる値の数、Confidenceを持つ。

| Confidence | 条件 |
|---|---|
| high | 4サンプル以上かつ3種類以上の値 |
| medium | 2サンプル以上かつ2種類以上の値 |
| low | 上記以外 |

複数候補が一致する場合はすべて表示する。正値だけを使用した場合などは、
符号あり・なしを一意に判定できないためである。

## 7. 定義案出力

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

同じByteを複数Fieldが使用する定義、組み込みOpcodeを置換する定義、
同名Commandが重複する定義は拒否する。読み込んだ定義は永続化せず、
Command Consoleを再起動した場合は再読込する。

## 8. 制約

次の形式は初版の自動推定対象外、または一意に推定できない可能性がある。

- 複数パラメーターを同時に変更したキャプチャ
- Bit Field
- 倍率やOffsetによる変換値
- 可変長配列と条件依存レイアウト
- Sequence Number、Timestamp、乱数
- Checksum、CRC、暗号化、難読化
- 非同期Vendor Eventの確定的なCommand関連付け

推定結果は相関を示すもので、パラメーターの意味や送信安全性を保証しない。
