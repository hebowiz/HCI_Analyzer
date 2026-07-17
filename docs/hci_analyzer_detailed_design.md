# HCI Analyzer 詳細設計

## 1. 目的

HCI Analyzerは、最大2つのシリアルポートからUART HCI（H4）データを受信し、
HCI CommandおよびHCI Eventを解析する受信専用アプリケーションである。

解析結果は次の場所へ出力する。

- Tkinter GUIの共通ログ領域
- 解析セッション単位のJSON Linesファイル
- 解析終了後に生成するHCI通信シーケンス図

GUIからHex Stringを手動入力し、シリアルポートを使用せずに1フレームを解析する
機能も提供する。

## 2. 対象範囲

### 2.1 詳細解析するHCI Command

| Opcode | Command |
|---:|---|
| `0x201D` | `HCI_LE_Receiver_Test[v1]` |
| `0x2033` | `HCI_LE_Receiver_Test[v2]` |
| `0x204F` | `HCI_LE_Receiver_Test[v3]` |
| `0x201E` | `HCI_LE_Transmitter_Test[v1]` |
| `0x2034` | `HCI_LE_Transmitter_Test[v2]` |
| `0x2050` | `HCI_LE_Transmitter_Test[v3]` |
| `0x207B` | `HCI_LE_Transmitter_Test[v4]` |
| `0x201F` | `HCI_LE_Test_End` |
| `0x0C03` | `HCI_Reset` |
| `0x1002` | `HCI_Read_Local_Supported_Commands[v1]` |
| `0x1010` | `HCI_Read_Local_Supported_Commands[v2]` |

### 2.2 詳細解析するHCI Event

- `HCI_Command_Complete`
  - 通常のLE Test応答を`LE_Status`として識別
  - `HCI_LE_Test_End`の応答を`LE_Packet_Report`として識別
  - Supported Commands v1/v2のビットマップを解析
- `HCI_Command_Status`
- `HCI_LE_Meta_Event`
  - `HCI_LE_Connectionless_IQ_Report`
  - その他の既知subevent名

未対応EventはH4 Eventとして受理し、Event Code、長さ、ParameterのRAW Hexを
保持する。Command CompleteまたはCommand Statusが未対応Opcodeを参照する場合は
`UNKNOWN_OPCODE`エラーとする。

### 2.3 基本解析するH4 Data Packet

次のH4 Packet Indicatorについて、フレーム境界、Handle/Flags、Payload Length、
Payload Hexまでを解析する。

| Indicator | Packet |
|---:|---|
| `0x02` | HCI ACL Data |
| `0x03` | HCI Synchronous Data |
| `0x05` | HCI ISO Data |

Data PacketのPayload内部は詳細解析しない。

### 2.4 初期対象外

- Channel Sounding Commandの詳細パラメーター解析
- ACL/SCO/ISO Payloadの上位プロトコル解析
- シリアルポートへのCommand送信
- ASCIIデバッグメッセージの解析

## 3. 非機能要件

- Python 3.11以上
- GUIはTkinter
- シリアル通信はpyserial
- PNG生成はPillow
- シリアル設定は8 data bits / no parity / 1 stop bit
- XON/XOFF、RTS/CTS、DSR/DTRは使用しない
- 共通ボーレートは最大3 Mbps
- シリアル受信はGUIスレッドと独立したワーカースレッドで実行する
- GUI部品の更新はTkinterメインスレッドだけで実行する
- 2ポートの受信内容は1つのGUIログと1つのJSONLへ統合する
- 各レコードへタイムスタンプ、ポート識別子、Directionを付与する

## 4. 全体構成

```text
MainWindow
    │ ユーザー操作 / ログ表示 / シーケンス図表示
    ▼
HciAnalyzerApplication
    ├── AnalyzerSettingsStore
    ├── DualSerialMonitor
    │     ├── SerialPortWorker (Port 1)
    │     │     └── H4StreamDecoder
    │     └── SerialPortWorker (Port 2)
    │           └── H4StreamDecoder
    ├── Queue[LogRecord]
    ├── HciParser
    │     ├── HciCommandParser
    │     └── HciEventParser
    ├── JsonlLogger
    └── HciSequenceDiagram
          └── SequenceDiagramWindow
```

### 4.1 モジュール責務

| モジュール | 責務 |
|---|---|
| `application.py` | GUI、Monitor、Parser、Logger、設定、シーケンス図の統合 |
| `gui/main_window.py` | Analyzerメイン画面とユーザー入力 |
| `serial/monitor.py` | 1または2ポートの受信ワーカー管理 |
| `parser/h4_stream.py` | 任意の分割単位で届くUARTデータからH4フレームを抽出 |
| `parser/facade.py` | Packet IndicatorによるParser振り分け |
| `parser/command.py` | HCI Commandの長さ検証とパラメーター解析 |
| `parser/event.py` | HCI Eventの長さ検証とパラメーター解析 |
| `parser/registry.py` | Opcode、Event、PHYなどの静的定義 |
| `parser/supported_commands.py` | Supported Commandsビットマップ解析 |
| `logging/jsonl_logger.py` | セッション単位のJSONL保存 |
| `analyzer_settings.py` | ポート、ボーレート、ウィンドウサイズの永続化 |
| `sequence/diagram.py` | JSONLからMermaid、Markdown、PNGを生成 |
| `gui/sequence_window.py` | シーケンス図の別ウィンドウ表示と保存操作 |

## 5. GUI詳細設計

### 5.1 画面構成

```text
┌─────────────────────────────────────────────────────────────────────┐
│ シリアルモニター                                                   │
│ Port 1 [COM3 ▼] Port 2 [COM4 ▼] Baud [115200 ▼]                   │
│ [ポート更新] [解析開始] [解析終了] 状態                            │
├─────────────────────────────────────────────────────────────────────┤
│ Hex String 手動解析                                                │
│ [01 1F 20 00                                      ] [解析]         │
├─────────────────────────────────────────────────────────────────────┤
│ 受信データ / 解析結果                                               │
│ [timestamp] [Port1:COM3] [host_to_controller] [packet] RAW: ...    │
│ { JSON形式の解析結果 }                                             │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.2 シリアル設定

| 項目 | 仕様 |
|---|---|
| Port 1 / Port 2 | `list_serial_ports()`の結果から選択 |
| 同一ポート選択 | 1つのワーカーだけを起動して当該ポートを監視 |
| 異なるポート選択 | 2つのワーカーを同時起動 |
| Baud | 2ポート共通、`SUPPORTED_BAUD_RATES`から選択 |
| ポート更新 | 監視停止中のみ使用可能 |
| 解析開始 | 監視停止中のみ使用可能 |
| 解析終了 | 監視中のみ使用可能 |

監視中はPort、Baud、ポート更新、解析開始を無効化する。

### 5.3 手動解析

- Hex String入力欄と解析ボタンを配置する
- Enterキーでも解析できる
- 空白、カンマ、セミコロン、コロン、アンダースコア、ハイフンを区切りとして許可
- `0x`または`0X`接頭辞を許可
- 手動解析結果はGUIログへ表示する
- JSONLセッション中に実行した場合は同じJSONLへ保存する
- Directionは`manual`、Sourceは`Manual`とする

### 5.4 ログ表示

各レコードは最低2行で表示する。

```text
[timestamp] [source] [direction] [kind] RAW: XX XX ...
{decodedまたはerrorのJSON}
```

Systemレコードは2行目へメッセージを表示する。
ログ表示とJSONLはASCIIだけで記録する。OS例外は例外種別、`errno`、
`winerror`へ正規化し、残った非ASCII文字は`[localized message omitted]`へ
置換する。

### 5.5 ウィンドウサイズ

- 初期サイズは`1100 x 720`
- 最小サイズは`800 x 520`
- 終了時の幅と高さを保存する
- 次回起動時に画面サイズ内へ補正して復元する
- ウィンドウ位置は保存しない

## 6. アプリケーション制御

### 6.1 起動処理

1. Parser、Record Queue、Monitor、Logger、Settings Storeを生成
2. 設定ファイルを読み込む
3. MainWindowを生成してCallbackを登録
4. ウィンドウサイズとボーレートを復元
5. シリアルポートを列挙
6. 保存ポートが存在すれば選択、存在しなければ利用可能な初期ポートを選択
7. 50 ms周期でRecord Queueの取得を開始
8. Tkinterイベントループを開始

### 6.2 解析開始

1. Port 1、Port 2、BaudをGUIから取得
2. Port未選択を検証
3. `logs/`へJSONLセッションを作成
4. `DualSerialMonitor.start()`を呼び出す
5. GUIを監視中状態へ変更
6. Monitoring started Systemレコードを出力

Monitor開始に失敗した場合は、起動済みワーカーを停止し、Loggerを閉じ、
`MONITOR_START_ERROR`を表示する。

### 6.3 解析終了

1. 全Serial Workerを停止
2. Record Queueに残っているレコードを処理
3. Monitoring stopped SystemレコードをJSONLへ保存
4. JSONLを閉じる
5. GUIを停止状態へ戻す
6. 終了したセッションのJSONLを読み込む
7. 新規ウィンドウへシーケンス図を表示

アプリケーションのウィンドウを直接閉じた場合は、MonitorとLoggerを安全に
終了するが、シーケンス図ウィンドウは開かない。

### 6.4 Record Queue

Serial WorkerからTkinter部品を直接操作しない。Workerは`LogRecord`を
thread-safeなQueueへ投入し、Applicationが50 ms周期でQueueを空になるまで取得する。

```text
Serial Worker Thread
    │ LogRecord
    ▼
Queue
    │ after(50)
    ▼
Tkinter Main Thread
    ├── GUIへ表示
    └── JSONLへ保存
```

## 7. シリアル受信設計

### 7.1 SerialPortWorker

各ワーカーは次の設定で`serial.Serial`を開く。

```text
bytesize = 8
parity   = none
stopbits = 1
timeout  = 0.1 seconds
xonxoff  = false
rtscts   = false
dsrdtr   = false
```

受信ループでは`in_waiting`分を読み、データがない場合も最大1 byteのreadを行う。

### 7.2 停止処理

1. Stop Eventを設定
2. 使用可能なら`cancel_read()`を呼び出す
3. Worker Threadを最大2秒待機
4. シリアルポートを閉じる
5. H4StreamDecoderに未完フレームが残っていれば
   `INCOMPLETE_H4_FRAME`として記録

### 7.3 方向判定

Directionは物理ポートではなくH4 Packet Indicatorから判定する。

| Indicator | Direction |
|---:|---|
| `0x01` Command | `host_to_controller` |
| `0x04` Event | `controller_to_host` |
| その他 | `unknown` |

Port 1／Port 2はHost側・Controller側へ固定せず、それぞれのSourceラベルで識別する。

### 7.4 シリアルエラー

`serial.SerialException`または`OSError`を捕捉し、次のエラーを生成する。

```text
code    = SERIAL_READ_ERROR
details = { port: <port name> }
```

## 8. H4ストリーム復元

### 8.1 対応Indicatorとフレーム長

| Indicator | Header | Frame Length |
|---:|---:|---|
| Command `0x01` | 4 | `4 + Parameter_Total_Length` |
| ACL `0x02` | 5 | `5 + Data_Total_Length` |
| SCO `0x03` | 4 | `4 + Data_Total_Length` |
| Event `0x04` | 3 | `3 + Parameter_Total_Length` |
| ISO `0x05` | 5 | `5 + (ISO_Data_Load_Length & 0x3FFF)` |

1回のreadがフレーム途中で分割される場合と、複数フレームが連結される場合の
両方に対応する。

### 8.2 起動時ノイズ

- 最初の有効Indicatorより前のbyte列をNoiseとして破棄する
- Noiseは`RecordKind.NOISE`でログへ残す
- 同期前に誤ったIndicatorを検出した場合は、後続のもっともらしいCommandまたは
  Event開始位置へ再同期する
- 一度正常フレームへ同期した後は、基本的にノイズが混在しない前提とする

再同期候補は次の条件で判定する。

- Command Opcodeが既知の`COMMAND_DEFINITIONS`に存在する
- Event CodeがCommand Complete、Command Status、LE Meta Eventのいずれか

## 9. Parser共通設計

### 9.1 入力

`HciParser`は次の入力形式を提供する。

- `parse_bytes(data: bytes)`
- `parse_hex_string(text: str)`
- `parse(data: bytes | str)`：plain dictを返す補助API

### 9.2 Packet Indicator振り分け

```text
0x01 -> HciCommandParser
0x04 -> HciEventParser
0x02 / 0x03 / 0x05 -> Data Packet基本解析
その他 -> UNKNOWN_PACKET_INDICATOR
```

### 9.3 ParseResult

```text
success
packet_type
raw_data
decoded
error
```

エラーは`ParseError`で表現する。

```text
code
message
details
```

## 10. HCI Command解析

### 10.1 共通ヘッダー

```text
01 Opcode_LSB Opcode_MSB Parameter_Total_Length Parameters...
```

- Packet Indicatorが`0x01`であることを検証
- Opcodeはlittle-endianで取得
- OGFは`(opcode >> 10) & 0x3F`
- OCFは`opcode & 0x03FF`
- 実フレーム長とParameter Total Lengthを検証
- Opcodeを`COMMAND_DEFINITIONS`から検索

### 10.2 固定長Command

Definitionの`fixed_parameter_length`とParameter Total Lengthが一致することを
検証する。

### 10.3 可変長Command

Receiver v3、Transmitter v3/v4は、Switching Pattern Lengthから期待長を算出する。

| Command | Length Field Index | Expected Length |
|---|---:|---:|
| Receiver v3 | 6 | `7 + Switching_Pattern_Length` |
| Transmitter v3 | 6 | `7 + Switching_Pattern_Length` |
| Transmitter v4 | 6 | `8 + Switching_Pattern_Length` |

### 10.4 デコード項目

- RX/TX Channelと周波数`2402 + 2N MHz`
- PHY値と表示名
- Modulation Index
- Test Data Length
- Packet Payload
- CTE Length / Type
- Slot Duration
- Switching Pattern Length
- Antenna IDs
- TX Power Level

TX Powerの`0x7E`はminimum、`0x7F`はmaximum、それ以外はsigned 1 octetとして
解釈する。

## 11. HCI Event解析

### 11.1 共通ヘッダー

```text
04 Event_Code Parameter_Total_Length Parameters...
```

実Parameter長とParameter Total Lengthが一致しない場合は
`PACKET_LENGTH_MISMATCH`とする。

### 11.2 HCI Command Complete

最低3 byteの共通パラメーターを検証し、Command Opcodeをlittle-endianで取得する。

| Opcode | Return Parameter Length | 追加解析 |
|---:|---:|---|
| `0x0C03` | 1 | Status |
| 通常LE Test | 1 | Status、`LE_Status` |
| `0x201F` | 3 | Status、Num Packets、`LE_Packet_Report` |
| `0x1002` | 65 | Status、64-octet Supported Commands |
| `0x1010` | 252 | Status、251-octet Supported Commands |

### 11.3 HCI Command Status

- Parameter Lengthは4 byte固定
- Status
- Num HCI Command Packets
- Command Opcode
- 対応Command名

### 11.4 HCI LE Meta Event

先頭byteをSubevent Codeとして取得する。

`HCI_LE_Connectionless_IQ_Report`では次を解析する。

- Sync Handle
- Channel Index
- RSSI
- RSSI Antenna ID
- CTE Type
- Slot Durations
- Packet Status
- Event Counter
- Sample Count
- signed I/Q Samples

Sample Countと残りのParameter Lengthが一致しない場合は
`IQ_SAMPLE_LENGTH_MISMATCH`とする。

### 11.5 Supported Commands

応答全体について次を保持する。

- byte配列
- Hex String
- 対応Command一覧
- 予約bit一覧
- アプリ対象Commandの対応可否

対応bit定義は`parser/supported_commands.csv`と`SUPPORTED_COMMAND_BITS`を使用する。

## 12. エラー設計

代表的なParserエラーは次のとおり。

| Code | 内容 |
|---|---|
| `INVALID_INPUT_TYPE` | 入力型がbytesまたはstrではない |
| `EMPTY_INPUT` | 入力が空 |
| `INVALID_HEX_STRING` | Hex String形式が不正 |
| `UNKNOWN_PACKET_INDICATOR` | 未知のH4 Indicator |
| `TRUNCATED_HEADER` | H4ヘッダー不足 |
| `PACKET_LENGTH_MISMATCH` | H4ヘッダーの長さと実フレーム長が不一致 |
| `UNKNOWN_OPCODE` | 詳細解析対象外のOpcode |
| `PARAMETER_LENGTH_MISMATCH` | Command Definitionの長さと不一致 |
| `RETURN_PARAMETER_LENGTH_MISMATCH` | Command Complete応答長が不一致 |
| `COMMAND_STATUS_LENGTH_MISMATCH` | Command Status長が不一致 |
| `MISSING_SUBEVENT_CODE` | LE Meta EventにSubevent Codeがない |
| `TRUNCATED_IQ_REPORT` | IQ Report固定領域が不足 |
| `IQ_SAMPLE_LENGTH_MISMATCH` | IQ Sample Countと実データ長が不一致 |
| `SERIAL_READ_ERROR` | シリアル受信エラー |
| `INCOMPLETE_H4_FRAME` | 終了時に未完フレームが残った |
| `LOG_WRITE_ERROR` | JSONLへの書き込み失敗 |
| `SEQUENCE_DIAGRAM_ERROR` | JSONLからのシーケンス図生成失敗 |

## 13. JSONLログ設計

### 13.1 セッション

- 解析開始ごとに1ファイル作成
- 保存先は`logs/`
- 基本名は`hci_YYYYMMDD_HHMMSS.jsonl`
- 同名が存在する場合は`_01`、`_02`を付加
- 1行を1受信フレーム、1エラー、1Noise、1Systemレコードとする
- 各write後にflushする
- 2ポートと手動解析を同じファイルへ保存する

### 13.2 レコード例

```json
{
  "timestamp": "2026-07-17T00:03:51.123+09:00",
  "source": "Port1:COM3",
  "direction": "host_to_controller",
  "kind": "packet",
  "raw_data": "01 1F 20 00",
  "result": {
    "success": true,
    "packet_type": "HCI_Command",
    "raw_data": "01 1F 20 00",
    "decoded": {
      "opcode": "0x201F",
      "display_name": "HCI_LE_Test_End"
    },
    "error": null
  },
  "message": null
}
```

### 13.3 Source

| Source | 内容 |
|---|---|
| `Port1:<port>` | Port 1ワーカー |
| `Port2:<port>` | Port 2ワーカー |
| `Manual` | GUI手動解析 |
| `Application` | 開始、終了、Application Error |

## 14. シーケンス図

解析終了時に、終了したセッションのJSONLを入力としてMermaid
`sequenceDiagram`を生成する。

- HCI CommandはHostからControllerへの矢印
- HCI EventはControllerからHostへの矢印
- Command Complete / StatusはOpcodeで直前のCommandへ関連付け
- LE Meta EventはSubevent名を表示
- 不明OpcodeとVendor固有EventはRAW Hexを保持
- 新規プレビューウィンドウへ表示
- 保存ボタンでJSONLと同じフォルダへMarkdownとPNGを同時保存

```text
hci_20260717_000351.jsonl
hci_20260717_000351_sequence.md
hci_20260717_000351_sequence.png
```

詳細は[`hci_sequence_diagram_design.md`](hci_sequence_diagram_design.md)を参照する。

## 15. 設定保存

### 15.1 保存場所

```text
~/.hci_analyzer/analyzer.json
```

### 15.2 保存項目

```json
{
  "port_one": "COM3",
  "port_two": "COM4",
  "baud_rate": 115200,
  "window_width": 1100,
  "window_height": 720
}
```

### 15.3 復元規則

- 設定ファイルが存在しない、壊れている、JSON Objectでない場合は初期値
- 未対応Baudは`115200`
- 不正または最小サイズ未満のウィンドウサイズは初期サイズ
- 保存Portが列挙結果に存在しない場合は利用可能なPortを初期選択
- Portが1つだけの場合は両Comboboxへ同じPortを設定

## 16. 終了処理

1. 現在のPort 1、Port 2、Baud、ウィンドウサイズを取得
2. Analyzer設定をJSONへ保存
3. 監視中ならMonitorを停止
4. 残存レコードを処理
5. Loggerを閉じる
6. メインウィンドウを破棄

設定保存に失敗した場合は`SETTINGS_SAVE_ERROR`をGUIログへ表示し、終了処理は継続する。

## 17. テスト設計

### 17.1 Parser

- Command/Event正常解析
- little-endian Opcode
- 固定長と可変長Command
- Parameter Total Length不一致
- 不明Opcode
- Command Complete / Status
- LE Packet Report
- Supported Commands
- Connectionless IQ Report
- ACL/SCO/ISO基本フレーム

### 17.2 H4 Stream

- 分割フレーム
- 連結フレーム
- 起動時ノイズ
- 誤Indicatorからの再同期
- 最大長Event
- 終了時未完フレーム

### 17.3 Serial Monitor

- 異なる2ポートで2 Workerを起動
- 同一ポートで1 Workerだけを起動
- 一方の起動失敗時に起動済みWorkerを停止
- シリアル受信エラー

### 17.4 Logger / Settings

- 1レコード1 JSON Line
- bytes、datetime、EnumのJSON変換
- ファイル名重複回避
- 設定の保存と復元
- 不正設定値の初期値化
- ウィンドウサイズ永続化

### 17.5 Application / Sequence

- QueueからGUIとJSONLへ同一レコードを出力
- 解析終了時に最後のJSONLからプレビューを開く
- アプリ終了時にはプレビューを開かない
- Mermaid方向とOpcode関連付け
- Markdown / PNGの自動命名と保存
- 不明Opcode、Vendor Event、壊れたJSON行の処理

## 18. 起動方法

リポジトリ直下から次のいずれかで起動する。

```powershell
run_analyzer.bat
```

または、仮想環境を有効にして起動する。

```powershell
.venv\Scripts\Activate.ps1
python analyzer.py
```
