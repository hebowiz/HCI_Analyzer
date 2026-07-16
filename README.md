# HCI LE RF PHY Analyzer

2つのシリアルポートからUART HCI（H4）を受信し、Bluetooth LE RF PHY Testの
Command/Eventを解析するPython/Tkinterアプリです。

## 対応範囲

- `HCI_LE_Receiver_Test` v1～v3
- `HCI_LE_Transmitter_Test` v1～v4
- `HCI_LE_Test_End`
- `HCI_Read_Local_Supported_Commands` v1/v2
- `HCI_Command_Complete`（`LE_Status` / `LE_Packet_Report`）
- `HCI_Command_Status`
- `HCI_LE_Connectionless_IQ_Report`
- H4 Command/Eventのフレーム分割と接続開始時ノイズの破棄
- ACL/SCO/ISOパケットの基本フレーム情報
- 2ポート同時受信、共通ボーレート、8-N-1、フロー制御なし
- GUIでのHex String手動解析
- `logs/hci_YYYYMMDD_HHMMSS.jsonl` へのJSON Lines保存
- 解析終了時にJSONLからHCIシーケンス図を生成
- Markdown `.md`とプレビュー全体のPNGスクリーンショット出力

Channel Soundingコマンドの詳細解析は未対応です。

## セットアップ

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## 起動

仮想環境を使用してBATファイルから起動できます。

```powershell
run_analyzer.bat
run_command_console.bat
```

Pythonから直接起動する場合:

```powershell
python analyzer.py
```

2つのシリアルポートと共通ボーレートを選択し、「解析開始」を押します。
両方に同じポートを選択した場合、そのポートだけを1つの受信スレッドで監視します。
アプリは受信専用であり、シリアルポートへのデータ送信は行いません。

Command Consoleでは、GUIからLE RF PHY Testコマンドとパラメーターを選択し、
UART HCI Commandを送信して応答Eventを確認できます。
Informational ParametersカテゴリからSupported Commands v1/v2も送信できます。
両アプリとも終了時のウィンドウサイズを記憶し、次回起動時に復元します。
Analyzerはポート1・ポート2・共通ボーレートも終了時に記憶します。
保存したポートが次回起動時に存在しない場合は、利用可能なポートを選択します。
Analyzerで「解析終了」を押すと、直近のJSONLログからHostとController間の
シーケンス図を生成し、新しいMarkdownプレビューウィンドウに表示します。
プレビューの保存ボタンを押すと、元のJSONLと同じフォルダへ
`<ログファイル名>_sequence.md`と`<ログファイル名>_sequence.png`を
まとめて保存します。

```powershell
python command_console.py
```

詳細設計は
[`docs/hci_command_console_detailed_design.md`](docs/hci_command_console_detailed_design.md)
を参照してください。

シーケンス図の変換仕様は
[`docs/hci_sequence_diagram_design.md`](docs/hci_sequence_diagram_design.md)
を参照してください。

## テスト

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```
