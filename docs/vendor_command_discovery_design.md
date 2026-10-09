# HCI Vendor Command Discovery 設計

## 1. 目的

HCI Vendor Command Discoveryは、最大2つのシリアルポートからHCI通信を
リアルタイム取得し、標準・ベンダー固有HCI CommandをOpcode別に比較する
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

HCI CommandはOGFにかかわらず解析対象として保存する。既存パーサーが
`UNKNOWN_OPCODE`を返しても、H4ヘッダーとParameter Total Lengthが正しければ
RAWからOpcodeとパラメーターを抽出する。H4 Packet Indicator `0x04`の
HCI Eventは解析成否にかかわらず一覧表示し、パラメーター推定対象にはしない。
RACEはType、Command ID、Payloadを一覧表示するが、現時点ではパラメーター
推定対象にしない。

## 3. キャプチャー一覧

標準表示は重複をまとめず、Timestamp順に1キャプチャー1行で表示する。
オプション`Group duplicate captures`を有効にした場合だけ、Protocol、
Opcode、Event名と関連Opcode、またはRACE Type／Command ID、
Parameter／Payloadが同じ行を集約する。

`選択Opcodeのみ表示`を有効にした場合、現在選択中のHCI Commandと、
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
標準コマンドも同じ方法で取り込み、Command Complete／Command StatusをOpcodeで関連付ける。

## 7. ユーザー定義パラメーターと既知値

利用者はパラメーターごとに次の情報を定義する。

```text
Name / Display Name / Kind / Unit / JSON Number Format / Default / Choices / Description
```

Kindは`auto`、`unsigned`、`signed`、`enum`、`boolean`、`bit_field`、
`raw_bytes`を持つ。初版の自動推定は`auto`、整数、Enumを対象とし、
Bit FieldとRaw Bytesの自動候補は生成しない。
Raw Bytesは固定長の配置を手動設定してConsole用定義へ出力する。

JSON Number Formatは`decimal`または`hex`とし、パラメーターごとに指定する。
既存プロジェクトでこの項目がない場合は`decimal`として読み込む。

数値型のDefaultには10進数または`0x`付き16進数を指定する。空欄の場合は、出力時に先頭の
キャプチャーから値を取得する。Choicesは従来の名前だけの指定に加え、
`0x01=LE 1M, 0x02=LE 2M`のように数値と名前を指定できる。
明示した数値はキャプチャーから求めたEnum値より優先する。型の範囲外の値や、
選択肢にない明示Defaultは出力エラーとする。

### 7.1 標準HCIコマンドの初期定義

標準Opcodeを初めて選択したとき、`standard_defaults.py`が編集用プロジェクトを作成する。
組み込み定義があるReceiver v1～v3、Transmitter v1～v4、Test End、Reset、
Supported Commands v1/v2では、名前・型・Enum選択肢・説明を流用する。
Defaultには先頭キャプチャーの値を設定する。キャプチャーに現れなかったEnum選択肢も保持する。

可変長のAntenna IDsは、キャプチャー時の配列長で個別の1バイト項目へ展開する。
Switching Pattern Lengthも独立した項目とし、v4のTX Power Levelは配列末尾の次に配置する。
画面専用のTX Power Modeは出力せず、最小・最大出力の指定値もTX Power Levelで扱う。

未登録Opcodeや既知のパラメーター長に合わないフレームでは、各バイトを
`Parameter_0`、`Parameter_1`などの`uint8`として作成する。意味や複数バイトの境界は推測しない。
利用者は項目の追加・編集・削除と配置の手動設定で定義を変更する。
初期定義はOpcodeごとに一度だけ作り、追加受信やOpcode再選択で変更内容を上書きしない。
自動作成した項目は配置確定済みとして扱い、既知値による推定をせずに出力できる。

一覧から複数キャプチャーを選択し、現在選択中のパラメーターについて既知値を
一括で割り当てる。割り当て後に一覧を再描画しても、対象キャプチャーの選択状態を
復元する。RACE行とHCI Event行には既知値を割り当てない。

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

### 8.2 固定長バイト列の手動設定

Kindを`raw_bytes`にしたパラメーターでは、Offsetとバイト数を指定する。
OffsetはParameter先頭を0とする。バイト数は1～255の整数で、
キャプチャーの範囲外や他の確定フィールドと重複する配置は拒否する。
プロジェクトには型・Offset・バイト数・初期値を保存する。

Defaultは`01 AB 00 FF`のようなHex文字列とする。空白なしの`01AB00FF`も受け付ける。
空欄の場合は先頭キャプチャーの該当範囲を使う。入力したDefaultの長さは、
手動設定したバイト数と一致する必要がある。配置確定後に長さを変える場合は、
Defaultをいったん空欄にして配置を変更し、新しい長さのDefaultを入力する。

RAWではJSON数値表記を16進に固定し、Enum選択肢は使用しない。
定義案・完成定義とも、手動で確定したRAWフィールドを次の形式で出力する。

```json
{
  "name": "data",
  "offset": 2,
  "type": "raw_bytes",
  "size": 4,
  "number_format": "hex",
  "default": "01 AB 00 FF"
}
```

Consoleでは固定長のHex入力欄として扱い、バイト順を変えずに送信する。
ログにも大文字・空白区切りのHex文字列を表示する。整数への変換や
Descriptionの`value`計算は行わない。Command Completeの応答定義でも
同じ型を使用できる。可変長バイト列とビット単位の手動配置は対象外とする。
RAWパラメーターで解析ボタンを押しても、自動推定は行わず確定済み配置を維持する。

## 9. 解析プロジェクト

`vendor_projects/*.json`へ次を保存する。

- 対象OpcodeとCommand Name
- ユーザー定義パラメーター
- パラメーターごとの候補と確定結果
- 標準・ベンダー固有HCI Command、HCI EventおよびRACEのキャプチャー
- キャプチャーへ割り当てた既知値と関連応答

プロジェクトを再度開くことで、パラメーターを1項目ずつ追加解析できる。
`vendor_projects/*.json`はGit管理対象外とする。

## 10. 定義案・完成定義出力

既定保存先は`vendor_definitions/`とし、ファイル名は
ベンダー固有では`vendor_0xXXXX_definition_draft.json`、標準コマンドでは
`hci_0xXXXX_definition_draft.json`とする。完成定義では末尾の`_draft`を外す。
定義案は次の情報を持つ。

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

Command Consoleは接続設定欄の`外部定義読込`からJSONを選択する。
Schema、Opcode、Template長、Field Offset、型、範囲、Field重複を検証し、
不正な定義は読み込まない。

`review_required: true`を含む場合は、Command名とOpcodeを示す確認ダイアログを
表示する。利用者が承認した場合だけ定義を追加する。ベンダー固有コマンドは
`Vendor Specific`、標準コマンドは`External HCI`カテゴリへ追加する。

送信Parameterは`parameter_template_hex`を複製し、各FieldのOffsetへGUI入力値を
指定型・Byte Orderで上書きして生成する。これにより、意味が未解明の固定Byteを
元キャプチャと同じ値で保持する。

`decimal`指定時はDefaultをJSON数値、Enum Choicesのキーを10進文字列で出力する。
`hex`指定時はDefaultとEnum Choicesのキーを型サイズに合わせてゼロ埋めした
`"0x0123"`形式の文字列で出力する。Command ConsoleはJSON数値、10進文字列、
16進文字列を内部整数へ正規化してから範囲とChoicesを検証する。送信コマンドの
可読ログでは、`hex`指定された外部定義パラメーターを同じ桁数の16進文字列で
表示する。Command Consoleの数値入力欄でもDefaultと復元値へ同じ表記を適用する。

完成定義にはユーザーが入力した`description`も出力する。外部コマンド定義の
Descriptionの最終の`=`より右側に`value`を含む場合、Command Consoleは`value`を現在の入力値へ
置き換えて計算し、元の説明に`→ 計算結果`を付けて即時表示する。
許可する構文は数値定数、`value`、`+`、`-`、`*`、`/`、`//`、`%`、単項符号、
括弧のみとし、関数呼出し、属性参照、その他の名前は実行しない。式が不正な場合は
計算せず、元のDescriptionだけを表示する。

Command Consoleは外部定義JSONへ手動追加されたCommand Completeの
`response.parameter_length`および`response.parameters`を読み込み、Return
Parametersをデコードできる。Vendor Discoveryから応答パラメーターの位置・型を
推定してResponse定義を生成する機能は、この段階では対象外とする。

同じByteを複数Fieldが使用する定義と、同一カテゴリ内でCommand Name・Versionが重複する定義は拒否する。
組み込みと同じOpcodeは別カテゴリの外部定義として追加し、組み込み定義やクイック送信は変更しない。
パラメーター値のキャッシュもカテゴリごとに分離する。同一OpcodeでもCommand
NameまたはVersionが異なる定義は別バリアントとして読み込める。読み込んだ定義は永続化せず、
Command Consoleを再起動した場合は再読込する。

全注釈から従来形式のレビュー必須定義案を出力できる。さらに、ユーザーが
候補を確定したパラメーターだけを使用して、Command Consoleが直接読み込める
完成定義を出力できる。未解明Byteは先頭キャプチャーのTemplate値を維持する。
Parameter Lengthが`0`のCommandに限り、確定パラメーターがなくても
`parameters: []`の完成定義を出力できる。Parameter Byteを持つCommandでは、
従来どおり少なくとも1つの確定パラメーターを必要とする。

標準コマンドの定義案にも、編集済みの初期定義を使用して`review_required: true`を付ける。
OGFはOpcodeから算出する。既存ファイルとの互換性のため、Schema Versionと
`hci_vendor_command_definition`などの`kind`は従来どおりとする。
Consoleは読み込んだ外部Opcodeについて、既存パーサーが解釈できないCommand／
Command Complete／Command StatusをH4ヘッダー検証後にRAWとして受理する。
Analyzer単体の未知Opcodeエラー動作は変更しない。

出力定義は固定長である。同一Opcodeのキャプチャーに複数の長さが混在する場合は、
不要な長さの行を除外してから出力する。配列長と項目数の連動変更は行わない。

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
