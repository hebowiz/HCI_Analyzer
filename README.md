# HCI LE RF PHY Analyzer

2つのシリアルポートからUART HCI（H4）を受信し、Bluetooth LE RF PHY Testの
Command/Eventを解析するPython/Tkinterアプリです。

## 対応範囲

- `HCI_LE_Receiver_Test` v1～v3
- `HCI_LE_Transmitter_Test` v1～v4
- `HCI_LE_Test_End`
- `HCI_Command_Complete`（`LE_Status` / `LE_Packet_Report`）
- `HCI_Command_Status`
- `HCI_LE_Connectionless_IQ_Report`
- H4 Command/Eventのフレーム分割と接続開始時ノイズの破棄
- ACL/SCO/ISOパケットの基本フレーム情報
- 2ポート同時受信、共通ボーレート、8-N-1、フロー制御なし
- GUIでのHex String手動解析
- `logs/hci_YYYYMMDD_HHMMSS.jsonl` へのJSON Lines保存

Channel Soundingコマンドの詳細解析は未対応です。

## セットアップ

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## 起動

```powershell
python main.py
```

2つのシリアルポートと共通ボーレートを選択し、「解析開始」を押します。
両方に同じポートを選択した場合、そのポートだけを1つの受信スレッドで監視します。
アプリは受信専用であり、シリアルポートへのデータ送信は行いません。

Command Consoleでは、GUIからLE RF PHY Testコマンドとパラメーターを選択し、
UART HCI Commandを送信して応答Eventを確認できます。

```powershell
python command_console.py
```

詳細設計は
[`docs/hci_command_console_detailed_design.md`](docs/hci_command_console_detailed_design.md)
を参照してください。

## テスト

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```
