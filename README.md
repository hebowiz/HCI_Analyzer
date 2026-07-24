# HCI Analyzer / HCI Command Console / Vendor Discovery

UART HCI（H4）で送受信されるBluetooth LE RF PHY TestのCommand/Eventを
解析するPython/Tkinterアプリケーションです。

このリポジトリには、用途の異なる次の3つのアプリが含まれます。

| アプリ | 用途 |
|---|---|
| HCI Analyzer | 最大2つのシリアルポートを受信専用で監視し、HCI通信を解析・保存する |
| HCI Command Console | GUIからHCI Commandを送信してControllerを制御する |
| HCI Vendor Command Discovery | 最大2ポートからベンダー固有Commandをリアルタイム取得し、パラメーター配置候補を調べる |

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

### 機能

- 1つのシリアルポートによるHCI Command送信とHCI Event受信
- コマンド選択と全パラメーターのGUI入力
- 入力内容を即時反映するH4 Command Packetプレビュー
- HCI ResetとHCI LE Test Endの1クリック送信
- 送信Commandと受信Eventを共通ログへ表示
- コマンド・イベント名とパラメーターの読みやすいSUMMARY表示
- Supported Commands v1/v2によるController対応状況の判定
- 1、2、3秒から選択できる応答タイムアウト（初期値1秒）
- Vendor Discoveryが出力した外部Vendor定義JSONの読込・フォーム生成・送信

Command Consoleのログはアプリ実行中の画面表示のみで、ファイルへ保存しません。
応答待ち中は追加のコマンド送信とタイムアウト変更を無効化します。

Vendor Commandを使用する場合は、接続設定欄の「Vendor定義読込」から定義案JSONを
選択します。`review_required: true`の定義は警告を表示し、利用者が確認した場合だけ
読み込みます。読み込んだCommandは`Vendor Specific`カテゴリへ追加されます。
定義はアプリ終了後まで記憶しないため、次回起動時は再度読み込んでください。

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

最大2つのシリアルポートを監視し、ベンダー固有HCI Commandをリアルタイムで
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
2. Vendor CommandとRACEを時系列一覧で確認する
3. 不要なキャプチャーを選択して除外する（Undo可能）
4. 解析するVendor Opcodeを選択する
5. PHY、Channelなどのパラメーターをユーザー定義する
   - JSON数値表記はパラメーターごとに10進／16進を選択できる
6. キャプチャーを選び、選択パラメーターの既知値を割り当てる
7. パラメーター単位で位置・型候補を解析し、候補を確定する
   - 自動候補が正しくない場合は「配置を手動設定」でOffsetと型を指定する
8. 解析プロジェクトを保存し、別のパラメーター解析を継続する
9. 完成後にCommand Console用定義を出力する

キャプチャーは重複をまとめず、検出時刻順に1件ずつ表示するのが標準です。
`Group duplicate captures`を有効にした場合だけ、同一Protocol、識別子、
Parameter／Payloadのキャプチャーを表示上でまとめます。

RACEはType、Command ID、Payloadを一覧へ表示しますが、現在はパラメーター
推定およびCommand Console定義出力の対象外です。

自動推定する型は、8／16／32／48 bitの符号あり・なし整数、
little-endian／big-endian、および1～4 byte Enumです。Enum値は連続値である
必要はなく、選択肢ごとに任意の値を対応付けられます。出力結果は候補であり、
定義案は`review_required: true`として保存されます。ユーザーが候補を明示的に
確定したパラメーターからはConsole用完成定義を出力できます。いずれも実機送信へ
使用する前に、必ず内容を確認してください。

16進表記を選択したパラメーターは、完成定義の`default`とEnumの`choices`キーを
`"0x0123"`形式の文字列で出力します。Command ConsoleはJSON数値、10進文字列、
16進文字列のいずれも内部整数へ変換して読み込みます。送信後のConsoleログでは、
16進指定されたVendorパラメーターを型サイズに合わせた16進数で表示します。
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
