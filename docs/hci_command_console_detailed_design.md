# HCI Command Console 詳細設計

## 1. 目的

HCI Command Consoleは、GUIからBluetooth HCIコマンドと全パラメーターを指定し、
UART HCI（H4）形式でControllerへ送信するアプリケーションである。

送信したHCI CommandとControllerから受信したHCI Eventは、既存のHCI Analyzerと
同じ解析結果を用いてGUI内の共通ログへ表示する。ログファイルへの保存は行わない。

## 2. 初期実装範囲

初期版では以下のコマンドを対象とする。

| Opcode | コマンド |
|---:|---|
| `0x201D` | `HCI_LE_Receiver_Test[v1]` |
| `0x2033` | `HCI_LE_Receiver_Test[v2]` |
| `0x204F` | `HCI_LE_Receiver_Test[v3]` |
| `0x201E` | `HCI_LE_Transmitter_Test[v1]` |
| `0x2034` | `HCI_LE_Transmitter_Test[v2]` |
| `0x2050` | `HCI_LE_Transmitter_Test[v3]` |
| `0x207B` | `HCI_LE_Transmitter_Test[v4]` |
| `0x201F` | `HCI_LE_Test_End` |
| `0x1002` | `HCI_Read_Local_Supported_Commands[v1]` |
| `0x1010` | `HCI_Read_Local_Supported_Commands[v2]` |

Channel Soundingコマンドと任意Hex直接送信は初期実装の対象外とする。ただし、
コマンド定義を追加することでGUI、検証、エンコードへ展開できる構造にする。

## 3. 非機能要件

- Python 3.11以上
- GUIはTkinter
- シリアル通信はpyserial
- 1つのシリアルポートを双方向で使用
- 8 data bits / no parity / 1 stop bit
- XON/XOFF、RTS/CTS、DSR/DTRは使用しない
- ボーレートは既存アプリと同じ選択肢を使用し、最大3 Mbps
- シリアル送受信はGUIスレッドで実行しない
- GUI更新はTkinterのメインスレッドだけで実行する
- 初期版は同時に1つの応答待ちトランザクションだけを許可する
- 応答タイムアウトの初期値は3.0秒
- コマンドごとに最後に入力したパラメーター値をアプリ実行中だけ保持する
- 同一コマンドのversion間では、同名の共通パラメーター値を共有する
- Hex直接送信機能は初期版に含めない
- ファイルログは作成しない

## 4. 全体構成

```text
CommandConsoleWindow
    │ ユーザー操作 / 表示
    ▼
HciCommandConsoleApplication
    ├── CommandValidator
    ├── HciCommandEncoder
    ├── HciParser（既存）
    └── HciSerialTransport
            ├── TX Queue
            ├── Serial Worker Thread
            ├── H4StreamDecoder（既存）
            └── Pending Transaction
```

### 4.1 モジュール責務

| モジュール | 責務 |
|---|---|
| `command_builder/definitions.py` | コマンド、パラメーター、応答形式の宣言 |
| `command_builder/validation.py` | GUI入力の型変換、範囲、依存関係検証 |
| `command_builder/encoder.py` | 検証済み値からH4 Commandを生成 |
| `serial/transport.py` | 接続、切断、送信キュー、受信、応答待ち |
| `gui/command_console.py` | GUI部品生成、入力取得、ログ表示 |
| `console_application.py` | 各層の統合とGUIスレッドへのイベント配送 |
| 既存`parser/` | 送信Commandと受信Eventの解析 |

## 5. GUI詳細設計

### 5.1 画面レイアウト

```text
┌──────────────────────────────────────────────────────────────┐
│ 接続設定                                                     │
│ Port [COM3 ▼] Baud [115200 ▼] [更新] [接続] [切断] 状態     │
├───────────────────────┬──────────────────────────────────────┤
│ コマンド選択          │ パラメーター設定                     │
│ Category [LE Test ▼]  │ パラメーター名 [入力部品] 単位       │
│ Command  [TX Test ▼]  │ 説明 / 派生値 / 入力エラー           │
│ Version  [v2 ▼]       │                                      │
│ Opcode   0x2034       │                                      │
├───────────────────────┴──────────────────────────────────────┤
│ Packet Preview                                               │
│ 01 34 20 04 13 25 00 01                                     │
│                                             [初期値] [送信]   │
├──────────────────────────────────────────────────────────────┤
│ 送受信ログ                         [すべて▼] [ログクリア]     │
│ [timestamp] [TX] [Transaction 1] ...                         │
│ [timestamp] [RX] [Transaction 1] ...                         │
└──────────────────────────────────────────────────────────────┘
```

### 5.2 接続設定

| 項目 | 仕様 |
|---|---|
| Port | `list_serial_ports()`の結果を表示 |
| Baud | 既存`SUPPORTED_BAUD_RATES`を使用 |
| 更新 | 未接続時のみ有効 |
| 接続 | Port選択時かつ未接続時のみ有効 |
| 切断 | 接続中のみ有効 |
| 状態 | `未接続`、`接続中`、`切断処理中`、`エラー` |

接続中はPortとBaudを変更できない。切断時には未完了トランザクションを
`cancelled`として終了させる。

### 5.3 コマンド選択

選択順序はCategory、Command、Versionとする。

- Category変更時にCommand候補を再構成する
- Command変更時にVersion候補を再構成する
- Version変更時にパラメーターフォームを再生成する
- Opcodeは読み取り専用表示とする
- 初めて選択したコマンドには定義済み初期値を設定する
- 再選択したコマンドには、そのコマンドで最後に入力した値を復元する
- version固有パラメーターはOpcode単位で保持する
- 同一Command名のversion間では、同名パラメーターの最新値を共有する

Categoryは`LE RF PHY Test`と`Informational Parameters`を用意する。

`Informational Parameters`では
`HCI_Read_Local_Supported_Commands` v1/v2を選択でき、どちらも
パラメーターなしで送信する。

### 5.4 パラメーター入力部品

| `ParameterKind` | GUI部品 |
|---|---|
| `INTEGER` | `Spinbox`または数値`Entry` |
| `SIGNED_INTEGER` | 符号付き数値`Entry` |
| `ENUM` | 読み取り専用`Combobox` |
| `BOOLEAN` | `Checkbutton` |
| `BIT_FIELD` | ビットごとの`Checkbutton`群 |
| `BYTE_ARRAY` | 行追加・削除可能なバイト配列 |
| `INTEGER_ARRAY` | 行追加・削除可能な整数配列 |
| `HEX_BYTES` | Hex String入力 |

### 5.5 共通入力動作

- 数値入力は原則10進数で表示する
- `0x`付き入力も受け付ける
- 列挙値は`表示名 (0xXX)`形式で表示する
- 入力変更から150 ms後に検証とプレビュー更新を行う
- プレビューを手動更新するボタンは設けない
- 検証エラーがある項目は背景色と項目下メッセージで示す
- エラーが1件でもある場合、送信ボタンを無効化する
- 未接続時も送信ボタンを無効化する
- 応答待ちトランザクションが存在する間も送信ボタンを無効化する
- プレビューは未接続でも利用できる

### 5.6 パラメーター値の保持

入力値はApplication層でOpcodeごとのキャッシュと、Command名ごとの共通値を
組み合わせて保持する。

```python
parameter_value_cache = {
    0x2034: {
        "TX_Channel": 19,
        "Test_Data_Length": 37,
        "Packet_Payload": 0,
        "PHY": 2,
    },
}

shared_parameter_values = {
    "HCI_LE_Transmitter_Test": {
        "TX_Channel": 19,
        "Test_Data_Length": 37,
        "Packet_Payload": 0,
        "PHY": 2,
    },
}
```

- 入力変更時に現在選択中Opcodeのキャッシュを更新する
- 同時に、Command名とパラメーター名が一致する共通値を更新する
- コマンド再選択時はキャッシュ値をフォームへ設定する
- version切り替え時は、切り替え先にも存在する共通パラメーター値を上書き適用する
- キャッシュがない場合はコマンド定義の初期値を使用する
- version固有パラメーターは各Opcodeで個別に保持する
- ReceiverとTransmitterのようにCommand名が異なる場合、同じ`PHY`という名前でも共有しない
- アプリ終了後の永続化は行わない
- 「初期値」ボタンを押した場合、現在versionの初期値をキャッシュへ設定し、
  共通パラメーターの初期値も他versionへ反映する

### 5.7 配列入力

`Antenna_IDs`は以下のUIとする。

```text
Antenna IDs
No.  Value
 0   [1 ] [削除]
 1   [2 ] [削除]
              [追加]
Switching Pattern Length: 2
```

- `Switching_Pattern_Length`は配列要素数から自動計算する
- ユーザーが長さを個別入力する欄は作らない
- 要素追加時の初期値は`1`
- 各要素は`0x00`～`0xFF`
- Receiver/Transmitter v3/v4では配列数を`2`～`75`とする

## 6. コマンド定義スキーマ

### 6.1 `ConsoleCommandDefinition`

以下の情報を保持する。

```text
opcode
name
version
category
parameters
response_kind
completion_event_code
description
```

実装時には次の情報を追加する。

| フィールド | 用途 |
|---|---|
| `parameter_encoder` | 特殊な並びや派生値が必要な場合のエンコード関数 |
| `command_validator` | 複数項目にまたがる検証関数 |
| `response_timeout_seconds` | コマンド別タイムアウト |
| `default_parameter_values` | フォーム初期値 |

### 6.2 `ParameterDefinition`

既存フィールドに加えて、実装時には以下を追加する。

| フィールド | 用途 |
|---|---|
| `byte_order` | 複数octet値の`little` / `big` |
| `signed` | signed整数としてエンコードするか |
| `visible_when` | 他項目による表示条件 |
| `enabled_when` | 他項目による編集可否 |
| `derived_from` | 派生値の生成元 |
| `formatter` | 補助表示生成 |

初期対象コマンドでは基本的に1 octet値と可変長配列だけを使用する。

## 7. 初期対象コマンドのフォーム定義

### 7.1 Receiver Test v1

| Parameter | Kind | Range | Default | 補助表示 |
|---|---|---:|---:|---|
| `RX_Channel` | INTEGER | 0～39 | 19 | `2402 + 2N MHz` |

### 7.2 Receiver Test v2

| Parameter | Kind | Values | Default |
|---|---|---|---|
| `RX_Channel` | INTEGER | 0～39 | 19 |
| `PHY` | ENUM | 1M、2M、Coded | 1M |
| `Modulation_Index` | ENUM | standard、stable | standard |

### 7.3 Receiver Test v3

| Parameter | Kind | Values / Range | Default |
|---|---|---|---|
| `RX_Channel` | INTEGER | 0～39 | 19 |
| `PHY` | ENUM | 1M、2M、Coded | 1M |
| `Modulation_Index` | ENUM | standard、stable | standard |
| `Expected_CTE_Length` | ENUM/INTEGER | 0、2～20 | 2 |
| `Expected_CTE_Type` | ENUM | AoA、AoD 1 us、AoD 2 us | AoA |
| `Slot_Durations` | ENUM | 1 us、2 us | 1 us |
| `Antenna_IDs` | INTEGER_ARRAY | 2～75要素 | `[1, 2]` |

`Switching_Pattern_Length`は`len(Antenna_IDs)`で生成する。

### 7.4 Transmitter Test v1

| Parameter | Kind | Values / Range | Default |
|---|---|---|---|
| `TX_Channel` | INTEGER | 0～39 | 19 |
| `Test_Data_Length` | INTEGER | 0～255 | 37 |
| `Packet_Payload` | ENUM | 0～7の定義済みパターン | PRBS9 |

### 7.5 Transmitter Test v2

v1に以下を追加する。

| Parameter | Kind | Values | Default |
|---|---|---|---|
| `PHY` | ENUM | 1M、2M、Coded S=8、Coded S=2 | 1M |

### 7.6 Transmitter Test v3

| Parameter | Kind | Values / Range | Default |
|---|---|---|---|
| `TX_Channel` | INTEGER | 0～39 | 19 |
| `Test_Data_Length` | INTEGER | 0～255 | 37 |
| `Packet_Payload` | ENUM | 0～7 | PRBS9 |
| `PHY` | ENUM | 1～4 | 1M |
| `CTE_Length` | ENUM/INTEGER | 0、2～20 | 2 |
| `CTE_Type` | ENUM | AoA、AoD 1 us、AoD 2 us | AoD 1 us |
| `Antenna_IDs` | INTEGER_ARRAY | 2～75要素 | `[1, 2]` |

### 7.7 Transmitter Test v4

v3に`TX_Power_Level`を追加する。

UIはモード選択と値入力を組み合わせる。

```text
TX Power Mode [Numeric ▼]
TX Power      [-5] dBm
```

| Mode | エンコード |
|---|---|
| Numeric | -127～20をsigned 1 octet |
| Minimum | `0x7E` |
| Maximum | `0x7F` |

Numericで`0x7E`または`0x7F`と同じ正値を入力することは許可しない。

### 7.8 Test End

パラメーター入力はない。説明、Opcode、プレビュー、送信ボタンだけを表示する。

### 7.9 Read Local Supported Commands v1/v2

両versionともパラメーター入力はない。

| Version | Opcode | 生成パケット | 応答 |
|---|---:|---|---|
| v1 | `0x1002` | `01 02 10 00` | Status + 64 octets |
| v2 | `0x1010` | `01 10 10 00` | Status + 251 octets |

応答ログにはSupported Commands全体のHexと、PHY試験関連bitの判定結果を表示する。

## 8. 入力検証設計

### 8.1 検証順序

1. 必須値の存在
2. 文字列から型への変換
3. 個別項目の範囲
4. 列挙値への包含
5. 配列要素数と各要素
6. 複数項目の依存関係
7. Parameter Total Lengthが1 octetに収まること

### 8.2 検証結果

`ValidationResult`は以下を返す。

- `valid`
- `normalized_values`
- `issues`

`normalized_values`にはエンコード可能な型だけを格納する。

```python
{
    "TX_Channel": 19,
    "Test_Data_Length": 37,
    "Packet_Payload": 0,
    "PHY": 1,
}
```

### 8.3 エラーコード例

| Code | 内容 |
|---|---|
| `REQUIRED` | 必須値なし |
| `INVALID_INTEGER` | 整数変換不可 |
| `OUT_OF_RANGE` | 範囲外 |
| `INVALID_ENUM` | 未定義列挙値 |
| `ARRAY_LENGTH` | 配列要素数不正 |
| `INVALID_ARRAY_ITEM` | 配列要素不正 |
| `DEPENDENCY_ERROR` | 項目間条件不成立 |
| `PARAMETER_TOTAL_LENGTH_OVERFLOW` | 255 octets超過 |

## 9. エンコード設計

### 9.1 処理手順

1. `CommandValidator.validate()`を実行
2. 無効ならエンコードせず検証結果を返す
3. 定義順にパラメーターをbytesへ変換
4. 派生値を所定位置へ挿入
5. `Parameter_Total_Length`を計算
6. Opcodeをlittle-endianで格納
7. H4 Command Indicator `0x01`を付加
8. 既存`HciParser`で生成結果を自己検証

```text
01 Opcode_LSB Opcode_MSB Parameter_Total_Length Parameters...
```

### 9.2 可変長コマンド

Receiver v3:

```text
fixed fields
+ Switching_Pattern_Length
+ Antenna_IDs
```

Transmitter v3:

```text
fixed fields
+ Switching_Pattern_Length
+ Antenna_IDs
```

Transmitter v4:

```text
fixed fields
+ Switching_Pattern_Length
+ Antenna_IDs
+ TX_Power_Level
```

配列長フィールドはユーザー入力値ではなく、エンコーダーが配列から生成する。

## 10. シリアル送受信設計

### 10.1 スレッド構成

```text
Tkinter Main Thread
    │ send request
    ▼
TX Queue
    │
Serial Worker Thread
    ├── serial.write()
    ├── serial.read()
    ├── H4StreamDecoder.feed()
    └── TransportEvent Queue
            │
            ▼
Tkinter Main Thread
```

送信と受信を1つのワーカースレッドで処理し、pyserialオブジェクトを複数スレッドから
同時操作しない。

### 10.2 接続状態

```text
DISCONNECTED
    │ connect
    ▼
CONNECTING
    ├── success ──> CONNECTED
    └── failure ──> DISCONNECTED

CONNECTED
    │ disconnect / serial error
    ▼
DISCONNECTING
    └─────────────> DISCONNECTED
```

### 10.3 送信キュー

初期版は未完了トランザクションが存在する間、追加送信を禁止する。

- 送信ボタンを無効化
- 送信キューには最大1件
- Command Completeまたはタイムアウトで再度送信可能
- Controllerが返す`Num_HCI_Command_Packets`はログ表示する
- 将来の複数キュー対応時はCommand Credit制御へ利用する

### 10.4 書き込み

- `serial.write(frame)`の戻り値がフレーム長と一致することを確認
- `serial.flush()`で送信完了を待つ
- 成功後に`TRANSMITTED`イベントを発行
- 部分書き込みまたは例外は`ERROR`イベントを発行

## 11. トランザクション管理

### 11.1 `PendingTransaction`

実装時に以下の内部型を追加する。

```text
transaction_id
opcode
command_name
frame
sent_at
deadline
response_kind
state
command_status
completion_event_code
```

### 11.2 状態

```text
QUEUED
  -> SENT
  -> COMPLETED
  -> FAILED
  -> TIMED_OUT
  -> CANCELLED
```

### 11.3 応答関連付け

`HCI_Command_Complete`:

- Event内の`Command_Opcode`を取得
- Pending TransactionのOpcodeと一致した場合に完了

`HCI_Command_Status`:

- Event内の`Command_Opcode`を取得
- `ResponseKind.COMMAND_STATUS`なら完了
- `COMMAND_STATUS_THEN_EVENT`なら中間状態として保持
- Statusが失敗ならその時点で失敗完了

LE Meta Event:

- `completion_event_code`が一致するトランザクションへ関連付ける
- 初期対象コマンドでは完了判定には使用しない
- Connectionless IQ Reportは非同期イベントとして表示する

Opcode不一致のEventは未関連RXイベントとしてログ表示する。

### 11.4 タイムアウト

タイムアウトは3.0秒固定で開始する。将来、設定UIまたはコマンド別定義へ
移行できる構造にする。

- TX完了時刻から計測
- 100 ms周期でdeadlineを確認
- 超過時に`RESPONSE_TIMEOUT`を発行
- タイムアウト後に到着した応答は未関連RXとして表示

## 12. ログ表示設計

ファイル保存は行わず、アプリ実行中のメモリー内ログだけを表示する。

### 12.1 ログ項目

- タイムスタンプ
- Direction: TX / RX / SYSTEM / ERROR
- Transaction ID
- Command/Event名
- Opcode
- Status
- 応答時間
- RAW Hex
- JSON解析結果
- 人間向けSUMMARY

### 12.2 表示例

```text
[2026-07-16T20:30:01.123+09:00] [TX] [Transaction 12]
RAW: 01 34 20 04 13 25 00 01
{"display_name":"HCI_LE_Transmitter_Test[v2]", ...}
SUMMARY
  Command                : HCI_LE_Transmitter_Test [v2]
  Opcode                 : 0x2034
  TX Channel             : 19 (2440 MHz)
  Data Length            : 37 bytes
  Payload                : PRBS9 (0x00)
  PHY                    : LE 1M PHY (0x01)

[2026-07-16T20:30:01.140+09:00] [RX] [Transaction 12] [17 ms]
RAW: 04 0E 04 01 34 20 00
{"event_name":"HCI_Command_Complete", ...}
SUMMARY
  Event                  : HCI_Command_Complete
  For Command            : HCI_LE_Transmitter_Test [v2] (0x2034)
  Status                 : Success (0x00)
  Response Time          : 17.0 ms
```

SUMMARYはコマンドまたはイベントの種類に応じて、周波数、PHY、CTE、
アンテナID、TX Power、受信パケット数、Supported Commands対応状況、
IQサンプルの先頭部分などを読みやすい形式で表示する。RAWおよびJSON解析結果は
従来どおり保持する。

### 12.3 フィルター

- すべて
- TX
- RX
- エラー

ログクリアは表示中の全ログを削除するが、接続やトランザクション状態には影響しない。

### 12.4 ウィンドウサイズの保存

終了時のウィンドウ幅と高さをユーザー設定へ保存し、次回起動時に復元する。
保存サイズが現在の画面または最小ウィンドウサイズに収まらない場合は、
表示可能な範囲へ補正する。ウィンドウ位置は保存しない。

## 13. アプリケーション統合

`HciCommandConsoleApplication`は以下を担当する。

1. 各コンポーネントの生成
2. シリアルポート一覧取得
3. コマンド定義のGUI登録
4. コマンド選択イベント処理
5. Opcode単位の固有値キャッシュとCommand単位の共通値管理
6. 検証とプレビュー
7. 接続と切断
8. 送信要求
9. Transport Event Queueの定期取得
10. GUIログ更新
11. 終了時の安全な切断

GUI、Validator、Encoder、Transportは互いに直接呼び合わず、
Applicationを経由して連携する。

## 14. 既存コードとの共用・変更点

### 14.1 共用するもの

- `SUPPORTED_BAUD_RATES`
- `SerialPortConfig`
- `list_serial_ports()`
- `H4StreamDecoder`
- `HciParser`
- Command/Event解析結果
- Opcode表示名と値マッピング

### 14.2 変更が必要なもの

既存`HciEventParser`は未対応Opcodeをエラーにする。将来、初期対象外の任意HCI Commandを
送信可能にする場合は、以下の分離が必要になる。

- H4/Event構造として正常か
- Opcodeが詳細デコード対象か

未登録OpcodeのCommand Complete/Statusでも、Opcode、Status、return parametersを
基本解析できるモードを追加する。既存Analyzerの「未知Opcodeはエラー」という要件は
strict modeとして維持する。

初期対象8コマンドは既存レジストリに登録済みのため、この変更なしでも実装可能。

## 15. エラー処理

| 状況 | GUI動作 |
|---|---|
| Port未選択 | 接続せずフィールドエラー |
| Port open失敗 | エラーログ、未接続へ戻る |
| 入力値不正 | 該当項目表示、送信無効 |
| エンコード失敗 | エラーログ、送信しない |
| serial write失敗 | トランザクション失敗、接続解除 |
| serial read失敗 | エラーログ、接続解除 |
| H4ノイズ | ノイズログ、再同期 |
| Event解析エラー | RXエラーログとして表示 |
| Opcode不一致 | 未関連RXとして表示 |
| 応答タイムアウト | Timeoutログ、送信を再有効化 |
| 切断中の送信 | 要求を拒否 |

## 16. テスト設計

### 16.1 Command Definition

- 全8コマンドのOpcode、順序、初期値
- ParameterKindと選択肢
- 可変長配列の派生フィールド

### 16.2 Validation

- 正常値
- 境界値
- `0x`入力
- 数値変換失敗
- CTE Lengthの不連続範囲
- Antenna ID配列長
- TX Power特殊値

### 16.3 Encoder

仕様書の既知ベクトルと一致すること。

```text
01 34 20 04 13 25 00 01
01 33 20 03 13 01 00
01 1F 20 00
```

- Receiver v3の可変長
- Transmitter v3/v4の可変長
- signed TX Power
- Parameter Total Length
- 生成結果を既存Parserで再解析

### 16.4 Transport

pyserialをモック化して以下を確認する。

- connect / disconnect
- 完全書き込み
- 部分書き込み
- 分割受信
- Command Complete関連付け
- Opcode不一致
- timeout
- 切断時cancel
- シリアル例外

### 16.5 Application

GUIとTransportをモック化して以下を確認する。

- 選択変更でフォーム再生成
- 同一Opcode再選択時の入力値復元
- 異なるversion間で入力値を共有しないこと
- 初期値リセット時のキャッシュ更新
- 入力変更で検証とプレビュー
- 未接続時に送信不可
- 送信中に再送不可
- Event Queueからログ更新
- 終了時切断

## 17. 実装順序

1. 対象10コマンドの`ConsoleCommandDefinition`を作成
2. `CommandValidator`を実装
3. `HciCommandEncoder`を実装
4. Definition / Validation / Encoderの単体テスト
5. `HciSerialTransport`とトランザクション管理を実装
6. Transportのモックテスト
7. `CommandConsoleWindow`の静的レイアウトを実装
8. パラメーターフォーム自動生成を実装
9. `HciCommandConsoleApplication`を統合
10. 実機で送信とCommand Complete受信を確認

## 18. 確定事項

2026年7月16日時点で、初期実装について以下を確定する。

1. 対象はReceiver v1～v3、Transmitter v1～v4、Test End、
   Read Local Supported Commands v1/v2の10コマンド
2. 応答タイムアウトは3.0秒
3. 応答待ち中の追加送信は禁止
4. Hex直接送信は初期版に含めない
5. パラメーター値はアプリ実行中だけ保持し、同一Commandのversion間では
   同名パラメーターを共有する
