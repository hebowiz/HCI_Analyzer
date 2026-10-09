# HCI Analyzer / HCI Command Console / Vendor Discovery

UART HCI（H4）で送受信されるBluetooth LE RF PHY TestのCommand/Eventを
解析するPython/Tkinterアプリケーションです。

このリポジトリには、用途の異なる次の3つのアプリが含まれます。

| アプリ | 用途 |
|---|---|
| HCI Analyzer | 最大2つのシリアルポートを受信専用で監視し、HCI通信を解析・保存する |
| HCI Command Console | GUIからHCI Commandを送信してControllerを制御する |
| HCI Vendor Command Discovery | 最大2ポートから標準・ベンダー固有Commandを取得し、パラメーター定義を編集・JSON出力する |

## セットアップ

Windows PowerShellでリポジトリ直下から実行します。

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## HCI Analyzer

### 機能

- 最大2ポートの同時受信
- 2ポート共通のボーレート（最大3 Mbps）
- 8 data bits / no parity / 1 stop bit / flow controlなし
- 同一ポートを2つの選択欄で指定した場合は、そのポートだけを監視
- H4 Command/Eventのフレーム復元と接続開始時ノイズの破棄
- OGF `0x3F`のVendor Specific CommandをOGF、OCF、Parameter RAWとして保存
- Vendor Commandに対するCommand Complete／Command StatusをOpcodeで識別
- Vendor Specific Event `0xFF`のParameter RAWを保存
- Head `0x05`のRACEフレームをType、Command ID、Payload RAWとして保存
- ACL/SCO/ISOパケットの基本フレーム情報解析
- Hex Stringの手動解析
- 2ポートと手動解析の結果を1つのGUIログへ統合
- `logs/hci_YYYYMMDD_HHMMSS.jsonl`へのJSON Lines保存
- 解析終了時にJSONLからHCIシーケンス図を生成
- シーケンス図を別ウィンドウでプレビュー
- Markdownとプレビュー全体のPNGスクリーンショットを一括保存

Analyzerは受信専用です。シリアルポートへのデータ送信は行いません。

### 起動

```powershell
run_analyzer.bat
```

または、仮想環境を有効にして直接起動します。

```powershell
python analyzer.py
```

2つのシリアルポートと共通ボーレートを選択し、「解析開始」を押します。
「解析終了」を押すと、そのセッションのJSONLを閉じてシーケンス図の
プレビューウィンドウを開きます。

シーケンス図の保存ボタンを押すと、元のJSONLと同じフォルダへ次の2ファイルを
同時に保存します。ファイル名と保存先を指定するダイアログは表示しません。

```text
hci_YYYYMMDD_HHMMSS_sequence.md
hci_YYYYMMDD_HHMMSS_sequence.png
```

終了時には、ポート1、ポート2、共通ボーレート、ウィンドウサイズを記憶し、
次回起動時に復元します。保存したポートが存在しない場合は、利用可能なポートを
初期選択します。

## HCI Command Console

GUIでコマンドとパラメーターを指定し、HCI Commandを送信してControllerを
制御するアプリです。送信内容とControllerからの応答は、制御結果を確認するため
GUIログへ解析表示します。

パラメーター設定は定義順に左列を上から配置し、全パラメーター数の半分を超えた
位置から右列を上から配置します。奇数個の場合は左列へ1項目多く配置し、画面の
横方向を活用して縦スクロール量を抑えます。

### 機能

- 1つのシリアルポートによるHCI Command送信とHCI Event受信
- コマンド選択と全パラメーターのGUI入力
- 入力内容を即時反映するH4 Command Packetプレビュー
- HCI ResetとHCI LE Test Endの1クリック送信
- 送信Commandと受信Eventを共通ログへ表示
- コマンド・イベント名とパラメーターの読みやすいSUMMARY表示
- Supported Commands v1/v2によるController対応状況の判定
- 1、2、3秒から選択できる応答タイムアウト（初期値1秒）
- Vendor Discoveryが出力した外部コマンド定義JSONの読込・フォーム生成・送信

Command Consoleのログはアプリ実行中の画面表示のみで、ファイルへ保存しません。
応答待ち中は追加のコマンド送信とタイムアウト変更を無効化します。

外部コマンド定義を使用する場合は、接続設定欄の「外部定義読込」から定義JSONを
選択します。`review_required: true`の定義は警告を表示し、利用者が確認した場合だけ
読み込みます。ベンダー固有コマンドは`Vendor Specific`、標準コマンドは
`External HCI`カテゴリへ追加されます。組み込みコマンドと同じOpcodeでも読み込めますが、
組み込み定義やReset／Test Endのクイックボタンは変更しません。
同一OpcodeでもCommand NameまたはVersionが異なる定義は、別バリアントとして
同時に登録・選択できます。送受信ログはTransaction IDを使って実際に送信した
バリアント名へ紐付けます。
定義はアプリ終了後まで記憶しないため、次回起動時は再度読み込んでください。

外部定義には、Command CompleteのReturn Parametersを記述できます。

```json
"response": {
  "kind": "command_complete",
  "parameter_length": 3,
  "parameters": [
    {
      "name": "status_code",
      "label": "Status",
      "offset": 0,
      "type": "enum_u8",
      "number_format": "hex",
      "choices": {
        "0x00": "Success",
        "0x01": "Failed"
      }
    },
    {
      "name": "result",
      "label": "Result",
      "offset": 1,
      "type": "uint16_le",
      "number_format": "hex"
    }
  ]
}
```

`parameter_length`はStatusを含むReturn Parameters全体の長さです。`offset: 0`は
H4 Event先頭ではなくReturn Parametersの先頭を示します。Command Complete内の
Event Code、Num_HCI_Command_Packets、Command OpcodeはConsoleが自動処理します。
受信長が定義と一致しない場合はRAWを保持し、ログへ長さ不一致を表示します。

### 起動

```powershell
run_command_console.bat
```

または、仮想環境を有効にして直接起動します。

```powershell
python command_console.py
```

終了時には、ポート、ボーレート、応答タイムアウト、ウィンドウサイズを記憶し、
次回起動時に復元します。保存したタイムアウトが未設定または不正な場合は、
初期値の1秒を使用します。

## HCI Vendor Command Discovery

最大2つのシリアルポートを監視し、標準・ベンダー固有HCI Commandをリアルタイムで
検出して、既知の設定値がParameter内に格納されている位置と型を推定する
補助ツールです。従来のAnalyzer JSONLも追加キャプチャーとして読み込めます。

### 起動

```powershell
run_vendor_discovery.bat
```

または、仮想環境を有効にして直接起動します。

```powershell
python vendor_discovery.py
```

### 基本操作

1. Analyzerと同じ2ポート・共通ボーレート設定で取得を開始する
2. 標準・ベンダー固有HCI Command、HCI Event、RACEを時系列一覧で確認する
3. 不要なキャプチャーを選択して除外する（Undo可能）
4. 解析するOpcodeを選択する
   - 「選択Opcodeのみ表示」で、そのCommandとOpcodeを含む応答だけに絞り込める
5. PHY、Channelなどのパラメーターをユーザー定義する
   - JSON数値表記はパラメーターごとに10進／16進を選択できる
6. キャプチャーを選び、選択パラメーターの既知値を割り当てる
   - 設定後もキャプチャーの複数選択状態は維持される
7. パラメーター単位で位置・型候補を解析し、候補を確定する
   - 自動候補が正しくない場合は「配置を手動設定」でOffsetと型を指定する
8. 解析プロジェクトを保存し、別のパラメーター解析を継続する
9. 完成後にCommand Console用定義を出力する

標準HCIコマンドは、Opcodeを初めて選択した時点で編集用の初期定義を作成します。
既存のReceiver Test、Transmitter Test、Test End、Reset、Supported Commandsは、
組み込み定義の名前・型・Enum選択肢を使い、初期値には最初のキャプチャー値を設定します。
未登録Opcodeや既知のレイアウトに合わないコマンドは、1バイト単位の`Parameter_0`、
`Parameter_1`などを作成します。これらの名前はパラメーターの意味を示しません。

自動作成された項目は、パラメーターの「編集」で名前・初期値・説明・数値表記を変更できます。
Enumの選択肢は`0x01=LE 1M, 0x02=LE 2M`のように値も指定できます。
初期値を空欄にすると、JSON出力時に先頭キャプチャーの値を使います。
位置と型は「配置を手動設定」で変更できます。変更内容はプロジェクトに保存され、
追加キャプチャーやOpcodeの再選択では上書きされません。

標準コマンドの自動作成済み項目は、既知値の割当や推定をせずにConsole用定義へ出力できます。
v3/v4の配列はキャプチャー時の長さで個別項目へ展開します。出力定義は固定長なので、
同じOpcodeで長さの違うキャプチャーがある場合は、不要な長さの行を除外してから出力してください。

キャプチャーは重複をまとめず、検出時刻順に1件ずつ表示するのが標準です。
`Group duplicate captures`を有効にした場合だけ、同一Protocol、識別子、
Parameter／Payloadのキャプチャーを表示上でまとめます。

H4 Packet Indicator `0x04`のHCI Eventは一覧へ表示します。Command Complete／
Command Statusは応答内のOpcodeと関連付け、Vendor Specific Eventは直前のVendor
Commandと参考情報として関連付けます。Event自体はパラメーター推定対象外です。

RACEはType、Command ID、Payloadを一覧へ表示しますが、現在はパラメーター推定
およびCommand Console定義出力の対象外です。

自動推定する型は、8／16／32／48 bitの符号あり・なし整数、
little-endian／big-endian、および1～4 byte Enumです。Enum値は連続値である
必要はなく、選択肢ごとに任意の値を対応付けられます。出力結果は候補であり、
定義案は`review_required: true`として保存されます。ユーザーが候補を明示的に
確定したパラメーターからはConsole用完成定義を出力できます。いずれも実機送信へ
使用する前に、必ず内容を確認してください。

Parameter Lengthが`0`のCommandは、ユーザー定義パラメーターを追加しなくても
Console用完成定義として出力できます。

外部コマンド定義のパラメーター説明欄では、現在の入力値を`value`として
計算式に使用できます。
たとえば`Frequency = 2402 + value * 2`と定義すると、Command Consoleでは
入力値`19`に対して`Frequency = 2402 + value * 2 → 2440`と即時表示します。
使用できる演算は加減乗除、整数除算、剰余、単項符号、括弧に限定されます。
式として解釈できない説明文は、通常の説明文としてそのまま表示します。

16進表記を選択したパラメーターは、完成定義の`default`とEnumの`choices`キーを
`"0x0123"`形式の文字列で出力します。Command ConsoleはJSON数値、10進文字列、
16進文字列のいずれも内部整数へ変換して読み込みます。送信後のConsoleログでは、
16進指定された外部定義のパラメーターを型サイズに合わせた16進数で表示します。
数値入力欄の初期値、リセット値、コマンド切替後の復元値にも同じ16進表記を
適用します。

未解明のParameter Byteは、最初のキャプチャを
`parameter_template_hex`として保持します。Command Consoleはテンプレートを
複製し、定義されたフィールドだけを入力値で上書きして送信Packetを生成します。

定義案の既定保存先は`vendor_definitions/`です。このフォルダー内のJSONは、
ベンダー情報を誤ってGitへ登録しないよう`.gitignore`の対象です。

## 対応するHCI Command / Event

### 詳細解析するCommand

- `HCI_LE_Receiver_Test` v1～v3
- `HCI_LE_Transmitter_Test` v1～v4
- `HCI_LE_Test_End`
- `HCI_Reset`
- `HCI_Read_Local_Supported_Commands` v1/v2
- Vendor Specific Command（OGF `0x3F`、汎用RAW解析）

### 詳細解析するEvent

- `HCI_Command_Complete`
  - LE RF PHY Testの`LE_Status`
  - HCI LE Test Endの`LE_Packet_Report`
  - HCI ResetのStatus
  - Supported Commands v1/v2のビットマップ
- `HCI_Command_Status`
- `HCI_LE_Connectionless_IQ_Report`
- `HCI_Vendor_Specific_Event`（Event Code `0xFF`、汎用RAW解析）

未対応のHCI EventはEvent Code、長さ、ParameterのRAW Hexを保持します。
Channel Sounding Commandの詳細パラメーター解析は未対応です。

## 設計資料

- [HCI Analyzer詳細設計](docs/hci_analyzer_detailed_design.md)
- [HCI Command Console詳細設計](docs/hci_command_console_detailed_design.md)
- [HCIシーケンス図設計](docs/hci_sequence_diagram_design.md)
- [Vendor Command Discovery設計](docs/vendor_command_discovery_design.md)
- [HCI LE RF PHY Test Command定義](docs/ble_le_rf_phy_test_hci_commands.md)

## テスト

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```
