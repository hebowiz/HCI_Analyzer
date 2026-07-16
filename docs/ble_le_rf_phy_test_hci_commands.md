# BLE / LE RF PHY Test HCI Command Reference

目的: シリアル通信（主に UART HCI）をのぞき見したときに、LE RF PHY試験で送受される HCI command / event を機械的に判別するための参照資料。

対象仕様:
- Bluetooth Core Specification v6.3
  - Vol 6, Part F, Section 1: RFPHY Test Modes setup alternatives
  - Vol 6, Part F, Section 2.1: LE Test Sequences / HCI and 2-wire UART mapping
  - Vol 6, Part F, Section 2.3: Channel Sounding test commands
  - Vol 4, Part A, Section 2: UART Transport Layer packet indicators
  - Vol 4, Part E, Section 5.4.1: HCI Command packet
  - Vol 4, Part E, Section 5.4.4: HCI Event packet
  - Vol 4, Part E, Section 7.7.14: HCI_Command_Complete event
  - Vol 4, Part E, Section 7.7.15: HCI_Command_Status event
  - Vol 4, Part E, Section 7.7.65.21: HCI_LE_Connectionless_IQ_Report event
  - Vol 4, Part E, Section 7.7.65.44: HCI_LE_CS_Subevent_Result event
  - Vol 4, Part E, Section 7.7.65.45: HCI_LE_CS_Subevent_Result_Continue event
  - Vol 4, Part E, Section 7.7.65.46: HCI_LE_CS_Test_End_Complete event
  - Vol 4, Part E, Section 7.8.28: HCI_LE_Receiver_Test command
  - Vol 4, Part E, Section 7.8.29: HCI_LE_Transmitter_Test command
  - Vol 4, Part E, Section 7.8.30: HCI_LE_Test_End command
  - Vol 4, Part E, Section 7.8.142: HCI_LE_CS_Test command
  - Vol 4, Part E, Section 7.8.143: HCI_LE_CS_Test_End command

## 1. 用語とスコープ

### 仕様書に明記されている事項

Bluetooth Core Specification v6.3 Vol 6, Part F, Section 2.1 では、通常の LE RF PHY Direct Test Mode の RF Test command と HCI command の対応は以下です。

| RF Test command / event | HCI command / event |
|---|---|
| `LE_Transmitter_Test` command | `HCI_LE_Transmitter_Test` command |
| `LE_Receiver_Test` command | `HCI_LE_Receiver_Test` command |
| `LE_Test_End` command | `HCI_LE_Test_End` command |
| `LE_Status` event | `HCI_Command_Complete` event |
| `LE_Packet_Report` event | `HCI_Command_Complete` event |

Bluetooth Core Specification v6.3 Vol 6, Part F, Section 2.3 では、Channel Sounding RFPHY test 用に以下が定義されています。

| HCI command / event | 用途 |
|---|---|
| `HCI_LE_CS_Test` command | Channel Sounding test を開始する |
| `HCI_LE_CS_Test_End` command | 実行中の CS test を停止する |
| `HCI_LE_CS_Subevent_Result` event | CS subevent 測定結果を報告する |
| `HCI_LE_CS_Subevent_Result_Continue` event | CS subevent 測定結果の続き |
| `HCI_LE_CS_Test_End_Complete` event | CS test 停止完了通知 |

### 仕様から論理的に導ける事項

UART HCI を使う場合、シリアル上では HCI Command packet indicator `0x01` の後に、HCI Command packet が続きます。したがって、PCや解析ツールで HCI UART を監視するときは、まず `0x01` を command の開始とみなし、次の2 octetsを little-endian の Opcode として解釈します。

### implementation specific な事項

以下は Core Specification の RF Test command 定義そのものではありません。解析器では「任意に出現しうるもの」として扱うのが安全です。

- DUTをテストモードへ入れる vendor-specific command
- UARTボーレート設定、RTS/CTS、リセット制御
- OSやベンダードライバが送る初期化コマンド
- `HCI_Reset`、`HCI_Read_Local_Supported_Commands` などの補助的な問い合わせ
- vendor-specific event `0xFF`

---

## 2. HCI UART フレーミング

### 2.1 UART HCI packet indicator

Bluetooth Core Specification v6.3 Vol 4, Part A, Section 2 に基づく UART HCI packet indicator:

| HCI packet type | Indicator | 方向 |
|---|---:|---|
| HCI Command packet | `0x01` | Host/PC → Controller/DUT |
| HCI ACL Data packet | `0x02` | 双方向 |
| HCI Synchronous Data packet | `0x03` | 双方向 |
| HCI Event packet | `0x04` | Controller/DUT → Host/PC |
| HCI ISO Data packet | `0x05` | 双方向 |

### 2.2 HCI Command packet 構造

UART HCI で command を送る場合の実バイト列:

```text
01  Opcode_LSB  Opcode_MSB  Parameter_Total_Length  Parameters...
```

HCI Command packet 本体:

| Field | Size | 説明 |
|---|---:|---|
| `Opcode` | 2 octets | OGF 6 bits + OCF 10 bits。HCIでは little-endian で送られる |
| `Parameter_Total_Length` | 1 octet | Parameters の合計octet数 |
| `Parameters` | variable | commandごとのパラメータ |

Opcode 計算:

```text
Opcode = (OGF << 10) | OCF
```

LE Controller command の OGF は `0x08` なので:

```text
Opcode = 0x2000 | OCF
```

例: `HCI_LE_Transmitter_Test [v2]`

```text
OCF    = 0x0034
Opcode = 0x2034
UART HCI command header = 01 34 20 ...
```

---

## 3. 解析器向け command registry

この節は、Python等でパーサを作るときにそのまま辞書化しやすい形式です。

```yaml
hci_transport:
  uart_command_indicator: 0x01
  uart_event_indicator: 0x04
  command_packet:
    opcode_endianness: little
    opcode_format: "Opcode = (OGF << 10) | OCF"
    le_controller_ogf: 0x08

commands:
  - name: HCI_LE_Receiver_Test
    versions:
      - version: v1
        ocf: 0x001D
        opcode: 0x201D
        uart_prefix: "01 1D 20"
        parameter_total_length: 1
        parameters: [RX_Channel]
        response: HCI_Command_Complete_Status
      - version: v2
        ocf: 0x0033
        opcode: 0x2033
        uart_prefix: "01 33 20"
        parameter_total_length: 3
        parameters: [RX_Channel, PHY, Modulation_Index]
        response: HCI_Command_Complete_Status
      - version: v3
        ocf: 0x004F
        opcode: 0x204F
        uart_prefix: "01 4F 20"
        parameter_total_length: "7 + Switching_Pattern_Length"
        parameters:
          - RX_Channel
          - PHY
          - Modulation_Index
          - Expected_CTE_Length
          - Expected_CTE_Type
          - Slot_Durations
          - Switching_Pattern_Length
          - Antenna_IDs[i]
        response: HCI_Command_Complete_Status
        possible_additional_events:
          - HCI_LE_Connectionless_IQ_Report

  - name: HCI_LE_Transmitter_Test
    versions:
      - version: v1
        ocf: 0x001E
        opcode: 0x201E
        uart_prefix: "01 1E 20"
        parameter_total_length: 3
        parameters: [TX_Channel, Test_Data_Length, Packet_Payload]
        response: HCI_Command_Complete_Status
      - version: v2
        ocf: 0x0034
        opcode: 0x2034
        uart_prefix: "01 34 20"
        parameter_total_length: 4
        parameters: [TX_Channel, Test_Data_Length, Packet_Payload, PHY]
        response: HCI_Command_Complete_Status
      - version: v3
        ocf: 0x0050
        opcode: 0x2050
        uart_prefix: "01 50 20"
        parameter_total_length: "7 + Switching_Pattern_Length"
        parameters:
          - TX_Channel
          - Test_Data_Length
          - Packet_Payload
          - PHY
          - CTE_Length
          - CTE_Type
          - Switching_Pattern_Length
          - Antenna_IDs[i]
        response: HCI_Command_Complete_Status
      - version: v4
        ocf: 0x007B
        opcode: 0x207B
        uart_prefix: "01 7B 20"
        parameter_total_length: "8 + Switching_Pattern_Length"
        parameters:
          - TX_Channel
          - Test_Data_Length
          - Packet_Payload
          - PHY
          - CTE_Length
          - CTE_Type
          - Switching_Pattern_Length
          - Antenna_IDs[i]
          - TX_Power_Level
        response: HCI_Command_Complete_Status

  - name: HCI_LE_Test_End
    versions:
      - version: none
        ocf: 0x001F
        opcode: 0x201F
        uart_prefix: "01 1F 20"
        parameter_total_length: 0
        parameters: []
        response: HCI_Command_Complete_Status_Num_Packets

  - name: HCI_LE_CS_Test
    category: Channel_Sounding_RFPHY_Test
    versions:
      - version: none
        ocf: 0x0095
        opcode: 0x2095
        uart_prefix: "01 95 20"
        parameter_total_length: "30 + Override_Parameters_Length"
        response: HCI_Command_Complete_Status
        parameters:
          - Main_Mode_Type
          - Sub_Mode_Type
          - Main_Mode_Repetition
          - Mode_0_Steps
          - Role
          - RTT_Type
          - CS_SYNC_PHY
          - CS_SYNC_Antenna_Selection
          - Subevent_Len
          - Subevent_Interval
          - Max_Num_Subevents
          - Transmit_Power_Level
          - T_IP1_Time
          - T_IP2_Time
          - T_FCS_Time
          - T_PM_Time
          - T_SW_Time
          - Tone_Antenna_Config_Selection
          - CS_Enhancements
          - SNR_Control_Initiator
          - SNR_Control_Reflector
          - DRBG_Nonce
          - Channel_Map_Repetition
          - Override_Config
          - Override_Parameters_Length
          - Override_Parameters_Data
        possible_additional_events:
          - HCI_LE_CS_Subevent_Result
          - HCI_LE_CS_Subevent_Result_Continue

  - name: HCI_LE_CS_Test_End
    category: Channel_Sounding_RFPHY_Test
    versions:
      - version: none
        ocf: 0x0096
        opcode: 0x2096
        uart_prefix: "01 96 20"
        parameter_total_length: 0
        parameters: []
        immediate_response: HCI_Command_Status
        completion_event: HCI_LE_CS_Test_End_Complete
```

---

## 4. 通常 LE Direct Test Mode コマンド

### 4.1 HCI_LE_Receiver_Test [v1]

参照: Bluetooth Core Specification v6.3 Vol 4, Part E, Section 7.8.28

目的: DUT/IUTを test reference packet の受信状態にする。Lower Tester がRF側から test reference packet を生成する。

UART HCI byte template:

```text
01 1D 20 01  RX_Channel
```

| Field | Size | 説明 |
|---|---:|---|
| `RX_Channel` | 1 octet | `N = (F - 2402) / 2`。範囲 `0x00` to `0x27`。周波数範囲 2402 MHz to 2480 MHz |

応答:

```text
04 0E 04  Num_HCI_Command_Packets  1D 20  Status
```

---

### 4.2 HCI_LE_Receiver_Test [v2]

参照: Bluetooth Core Specification v6.3 Vol 4, Part E, Section 7.8.28

目的: v1に `PHY` と `Modulation_Index` 指定を追加した受信テスト開始。

UART HCI byte template:

```text
01 33 20 03  RX_Channel  PHY  Modulation_Index
```

| Field | Size | 値 | 説明 |
|---|---:|---:|---|
| `RX_Channel` | 1 | `0x00`-`0x27` | `N = (F - 2402) / 2` |
| `PHY` | 1 | `0x01` | LE 1M PHY |
| `PHY` | 1 | `0x02` | LE 2M PHY |
| `PHY` | 1 | `0x03` | LE Coded PHY |
| `Modulation_Index` | 1 | `0x00` | standard modulation index と仮定 |
| `Modulation_Index` | 1 | `0x01` | stable modulation index と仮定 |

応答:

```text
04 0E 04  Num_HCI_Command_Packets  33 20  Status
```

---

### 4.3 HCI_LE_Receiver_Test [v3]

参照: Bluetooth Core Specification v6.3 Vol 4, Part E, Section 7.8.28

目的: v2に CTE / AoA / AoD / antenna switching 関連パラメータを追加した受信テスト開始。

UART HCI byte template:

```text
01 4F 20  LL  RX_Channel  PHY  Modulation_Index
             Expected_CTE_Length  Expected_CTE_Type  Slot_Durations
             Switching_Pattern_Length
             Antenna_IDs[0] ... Antenna_IDs[n-1]
```

`LL = 7 + Switching_Pattern_Length`

| Field | Size | 値 | 説明 |
|---|---:|---:|---|
| `RX_Channel` | 1 | `0x00`-`0x27` | `N = (F - 2402) / 2` |
| `PHY` | 1 | `0x01` | LE 1M PHY |
| `PHY` | 1 | `0x02` | LE 2M PHY |
| `PHY` | 1 | `0x03` | LE Coded PHY |
| `Modulation_Index` | 1 | `0x00` | standard modulation index と仮定 |
| `Modulation_Index` | 1 | `0x01` | stable modulation index と仮定 |
| `Expected_CTE_Length` | 1 | `0x00` | CTEなし |
| `Expected_CTE_Length` | 1 | `0x02`-`0x14` | 8 us単位のCTE長 |
| `Expected_CTE_Type` | 1 | `0x00` | AoA CTE |
| `Expected_CTE_Type` | 1 | `0x01` | AoD CTE with 1 us slots |
| `Expected_CTE_Type` | 1 | `0x02` | AoD CTE with 2 us slots |
| `Slot_Durations` | 1 | `0x01` | switching/sampling slot = 1 us |
| `Slot_Durations` | 1 | `0x02` | switching/sampling slot = 2 us |
| `Switching_Pattern_Length` | 1 | `0x02`-`0x4B` | Antenna ID数 |
| `Antenna_IDs[i]` | variable | `0xXX` | antenna switching pattern |

応答:

```text
04 0E 04  Num_HCI_Command_Packets  4F 20  Status
```

追加で発生しうる event:

```text
04 3E LL  15  ...   # HCI_LE_Connectionless_IQ_Report event, Subevent_Code = 0x15
```

---

### 4.4 HCI_LE_Transmitter_Test [v1]

参照: Bluetooth Core Specification v6.3 Vol 4, Part E, Section 7.8.29

目的: DUT/IUTに test reference packet を fixed interval で送信させる。v1はPHY指定を持たない。仕様上、欠落した `PHY` は `0x01`、つまり LE 1M PHY として扱われる。

UART HCI byte template:

```text
01 1E 20 03  TX_Channel  Test_Data_Length  Packet_Payload
```

| Field | Size | 値 | 説明 |
|---|---:|---:|---|
| `TX_Channel` | 1 | `0x00`-`0x27` | `N = (F - 2402) / 2` |
| `Test_Data_Length` | 1 | `0x00`-`0xFF` | payload length in bytes |
| `Packet_Payload` | 1 | `0x00` | PRBS9 |
| `Packet_Payload` | 1 | `0x01` | repeated `11110000` |
| `Packet_Payload` | 1 | `0x02` | repeated `10101010` |
| `Packet_Payload` | 1 | `0x03` | PRBS15 |
| `Packet_Payload` | 1 | `0x04` | repeated `11111111` |
| `Packet_Payload` | 1 | `0x05` | repeated `00000000` |
| `Packet_Payload` | 1 | `0x06` | repeated `00001111` |
| `Packet_Payload` | 1 | `0x07` | repeated `01010101` |

応答:

```text
04 0E 04  Num_HCI_Command_Packets  1E 20  Status
```

---

### 4.5 HCI_LE_Transmitter_Test [v2]

参照: Bluetooth Core Specification v6.3 Vol 4, Part E, Section 7.8.29

目的: v1に `PHY` 指定を追加した送信テスト開始。通常のスペアナ評価で LE 1M / LE 2M / LE Coded を切り替える場合に最も扱いやすい。

UART HCI byte template:

```text
01 34 20 04  TX_Channel  Test_Data_Length  Packet_Payload  PHY
```

| Field | Size | 値 | 説明 |
|---|---:|---:|---|
| `TX_Channel` | 1 | `0x00`-`0x27` | `N = (F - 2402) / 2` |
| `Test_Data_Length` | 1 | `0x00`-`0xFF` | payload length in bytes |
| `Packet_Payload` | 1 | `0x00`-`0x07` | payload pattern。詳細は v1 を参照 |
| `PHY` | 1 | `0x01` | LE 1M PHY |
| `PHY` | 1 | `0x02` | LE 2M PHY |
| `PHY` | 1 | `0x03` | LE Coded PHY with S=8 |
| `PHY` | 1 | `0x04` | LE Coded PHY with S=2 |

応答:

```text
04 0E 04  Num_HCI_Command_Packets  34 20  Status
```

---

### 4.6 HCI_LE_Transmitter_Test [v3]

参照: Bluetooth Core Specification v6.3 Vol 4, Part E, Section 7.8.29

目的: v2に CTE / AoD antenna switching 関連パラメータを追加した送信テスト開始。

UART HCI byte template:

```text
01 50 20  LL  TX_Channel  Test_Data_Length  Packet_Payload  PHY
             CTE_Length  CTE_Type  Switching_Pattern_Length
             Antenna_IDs[0] ... Antenna_IDs[n-1]
```

`LL = 7 + Switching_Pattern_Length`

| Field | Size | 値 | 説明 |
|---|---:|---:|---|
| `TX_Channel` | 1 | `0x00`-`0x27` | `N = (F - 2402) / 2` |
| `Test_Data_Length` | 1 | `0x00`-`0xFF` | payload length in bytes |
| `Packet_Payload` | 1 | `0x00`-`0x07` | payload pattern。詳細は v1 を参照 |
| `PHY` | 1 | `0x01` | LE 1M PHY |
| `PHY` | 1 | `0x02` | LE 2M PHY |
| `PHY` | 1 | `0x03` | LE Coded PHY with S=8 |
| `PHY` | 1 | `0x04` | LE Coded PHY with S=2 |
| `CTE_Length` | 1 | `0x00` | CTEなし |
| `CTE_Length` | 1 | `0x02`-`0x14` | 8 us単位のCTE長 |
| `CTE_Type` | 1 | `0x00` | AoA CTE |
| `CTE_Type` | 1 | `0x01` | AoD CTE with 1 us slots |
| `CTE_Type` | 1 | `0x02` | AoD CTE with 2 us slots |
| `Switching_Pattern_Length` | 1 | `0x02`-`0x4B` | Antenna ID数 |
| `Antenna_IDs[i]` | variable | `0xXX` | antenna switching pattern |

応答:

```text
04 0E 04  Num_HCI_Command_Packets  50 20  Status
```

---

### 4.7 HCI_LE_Transmitter_Test [v4]

参照: Bluetooth Core Specification v6.3 Vol 4, Part E, Section 7.8.29

目的: v3に `TX_Power_Level` を追加した送信テスト開始。HCI標準コマンドで送信電力指定まで行いたい場合に使う。

UART HCI byte template:

```text
01 7B 20  LL  TX_Channel  Test_Data_Length  Packet_Payload  PHY
             CTE_Length  CTE_Type  Switching_Pattern_Length
             Antenna_IDs[0] ... Antenna_IDs[n-1]
             TX_Power_Level
```

`LL = 8 + Switching_Pattern_Length`

| Field | Size | 値 | 説明 |
|---|---:|---:|---|
| `TX_Channel` | 1 | `0x00`-`0x27` | `N = (F - 2402) / 2` |
| `Test_Data_Length` | 1 | `0x00`-`0xFF` | payload length in bytes |
| `Packet_Payload` | 1 | `0x00`-`0x07` | payload pattern。詳細は v1 を参照 |
| `PHY` | 1 | `0x01`-`0x04` | LE 1M / 2M / Coded S=8 / Coded S=2 |
| `CTE_Length` | 1 | `0x00`, `0x02`-`0x14` | CTEなし、または8 us単位のCTE長 |
| `CTE_Type` | 1 | `0x00`-`0x02` | AoA/AoD CTE種別 |
| `Switching_Pattern_Length` | 1 | `0x02`-`0x4B` | Antenna ID数 |
| `Antenna_IDs[i]` | variable | `0xXX` | antenna switching pattern |
| `TX_Power_Level` | 1 | `0xXX` | -127 to +20 dBm の指定値または近傍値 |
| `TX_Power_Level` | 1 | `0x7E` | minimum transmit power |
| `TX_Power_Level` | 1 | `0x7F` | maximum transmit power |

応答:

```text
04 0E 04  Num_HCI_Command_Packets  7B 20  Status
```

---

### 4.8 HCI_LE_Test_End

参照: Bluetooth Core Specification v6.3 Vol 4, Part E, Section 7.8.30

目的: 実行中の transmitter test または receiver test を停止する。送信テストでは `Num_Packets = 0x0000`。受信テストでは受信パケット数を `Num_Packets` として返す。

UART HCI byte template:

```text
01 1F 20 00
```

応答:

```text
04 0E 06  Num_HCI_Command_Packets  1F 20  Status  Num_Packets_LSB  Num_Packets_MSB
```

| Return field | Size | 説明 |
|---|---:|---|
| `Status` | 1 | `0x00` = succeeded。`0x01`-`0xFF` = error code |
| `Num_Packets` | 2 | 受信テストでは受信パケット数。送信テストでは `0x0000` |

---

## 5. Channel Sounding RFPHY test コマンド

### 5.1 HCI_LE_CS_Test

参照:
- Bluetooth Core Specification v6.3 Vol 6, Part F, Section 2.3
- Bluetooth Core Specification v6.3 Vol 4, Part E, Section 7.8.142

目的: Channel Sounding testを開始する。IUTは initiator または reflector のどちらかの役割で動作する。

UART HCI byte template:

```text
01 95 20  LL
  Main_Mode_Type
  Sub_Mode_Type
  Main_Mode_Repetition
  Mode_0_Steps
  Role
  RTT_Type
  CS_SYNC_PHY
  CS_SYNC_Antenna_Selection
  Subevent_Len[3]
  Subevent_Interval[2]
  Max_Num_Subevents
  Transmit_Power_Level
  T_IP1_Time
  T_IP2_Time
  T_FCS_Time
  T_PM_Time
  T_SW_Time
  Tone_Antenna_Config_Selection
  CS_Enhancements
  SNR_Control_Initiator
  SNR_Control_Reflector
  DRBG_Nonce[2]
  Channel_Map_Repetition
  Override_Config[2]
  Override_Parameters_Length
  Override_Parameters_Data[Override_Parameters_Length]
```

`LL = 30 + Override_Parameters_Length`

固定部パラメータ:

| Field | Size | 主な値 / 範囲 | 説明 |
|---|---:|---|---|
| `Main_Mode_Type` | 1 | `0x01` Mode-1, `0x02` Mode-2, `0x03` Mode-3 | main mode |
| `Sub_Mode_Type` | 1 | `0x01` Mode-1, `0x02` Mode-2, `0x03` Mode-3, `0xFF` Unused | sub mode |
| `Main_Mode_Repetition` | 1 | `0x00`-`0x03` | 前subevent末尾のmain mode stepを次subevent先頭で繰り返す数 |
| `Mode_0_Steps` | 1 | `0x01`-`0x03` | 各test CS subevent先頭のmode-0 step数 |
| `Role` | 1 | `0x00` Initiator, `0x01` Reflector | local ControllerのCS role |
| `RTT_Type` | 1 | `0x00`-`0x06` | RTT種別。AA only、sounding sequence、random sequence等 |
| `CS_SYNC_PHY` | 1 | `0x01` LE 1M, `0x02` LE 2M, `0x03` LE 2M 2BT | CS_SYNC交換に使うPHY |
| `CS_SYNC_Antenna_Selection` | 1 | `0x01`-`0x04` | CS_SYNC packet用アンテナ識別子 |
| `Subevent_Len` | 3 | 1250 us to 3.999999 s | CS subevent長。単位 us |
| `Subevent_Interval` | 2 | `0x0000` single, `0x0002`-`0xFFFF` | 連続subevent開始間隔。単位 0.625 ms |
| `Max_Num_Subevents` | 1 | `0x00`, `0x01`-`0x20` | `0x00`は制限なし |
| `Transmit_Power_Level` | 1 | -127 to +20 dBm, `0x7E`, `0x7F` | 指定/最小/最大のTX power |
| `T_IP1_Time` | 1 | allowed set | mode-0/mode-1 CS_SYNC間のinterlude time |
| `T_IP2_Time` | 1 | allowed set | CS tone間のinterlude time |
| `T_FCS_Time` | 1 | allowed set | frequency change time |
| `T_PM_Time` | 1 | allowed set | phase measurement period |
| `T_SW_Time` | 1 | allowed set | antenna switch period |
| `Tone_Antenna_Config_Selection` | 1 | `0x00`-`0x07` | tone phaseのantenna configuration index |
| `CS_Enhancements` | 1 | bit0 = IPT enabled in reflector | CS拡張指定 |
| `SNR_Control_Initiator` | 1 | `0x00`-`0x04`, `0xFF` | initiator側SNR制御。`0xFF`は適用しない |
| `SNR_Control_Reflector` | 1 | `0x00`-`0x04`, `0xFF` | reflector側SNR制御。`0xFF`は適用しない |
| `DRBG_Nonce` | 2 | `0xXXXX` | DRBG nonceの一部 |
| `Channel_Map_Repetition` | 1 | `0x01`-`0xFF` | channel map / channel array の繰り返し回数 |
| `Override_Config` | 2 | bit field | 後続 `Override_Parameters_Data` に含む項目を指定 |
| `Override_Parameters_Length` | 1 | `0xXX` | 後続variable objectの長さ |
| `Override_Parameters_Data` | variable | 下表参照 | `Override_Config` に依存するvariable object |

`Override_Config` と `Override_Parameters_Data`:

| Override_Config bit | `Override_Parameters_Data` に含まれる項目 | 説明 |
|---:|---|---|
| 0 = 1 | `Channel_Length`, `Channel[i]` | channel sequenceを明示リストで指定 |
| 0 = 0 | `Channel_Map`, `Channel_Selection_Type`, `Ch3c_Shape`, `Ch3c_Jump` | channel mapとchannel selectionで指定 |
| 2 = 1 | `Main_Mode_Steps` | submode挿入までのmain mode step数 |
| 3 = 1 | `T_PM_Tone_Ext` | Mode-2/Mode-3 step内のtone extension |
| 4 = 1 | `Antenna_Path_Permutation_Index` | antenna path permutation |
| 5 = 1 | `CS_SYNC_AA_Initiator`, `CS_SYNC_AA_Reflector` | CS_SYNC packet用access address |
| 6 = 1 | `SS_Marker1_Position`, `SS_Marker2_Position` | sounding sequence marker位置 |
| 7 = 1 | `SS_Marker_Value` | sounding sequence marker値 |
| 8 = 1 | `CS_SYNC_Payload_Pattern`, `CS_SYNC_User_Payload` | CS_SYNC payload pattern / user payload |
| 10 = 1 | no direct data field by itself | Stable Phase test |

`Override_Parameters_Data` 内の主な項目:

| Field | Size | 値 / 範囲 | 説明 |
|---|---:|---|---|
| `Channel_Length` | 1 | `0x01`-`0x48` | channel pattern内のchannel数 |
| `Channel[i]` | variable | `Channel_Length × 1` | 使用channelリスト |
| `Channel_Map` | 10 | bit map | CS channel map |
| `Channel_Selection_Type` | 1 | `0x00` Algo #3b, `0x01` Algo #3c | channel selection algorithm |
| `Ch3c_Shape` | 1 | `0x00` Hat, `0x01` X | Algorithm #3c shape |
| `Ch3c_Jump` | 1 | `0x02`-`0x08` | CSChannelJump |
| `Main_Mode_Steps` | 1 | `0x01`-`0xFF` | submode step前のmain mode step数 |
| `T_PM_Tone_Ext` | 1 | `0x00`-`0x04` | tone extensionパターン |
| `Antenna_Path_Permutation_Index` | 1 | `0x00`-`0x17`, `0xFF` | antenna path permutation |
| `CS_SYNC_AA_Initiator` | 4 | `0xXXXXXXXX` | initiator側access address |
| `CS_SYNC_AA_Reflector` | 4 | `0xXXXXXXXX` | reflector側access address |
| `SS_Marker1_Position` | 1 | `0`-`63` | first marker position |
| `SS_Marker2_Position` | 1 | `67`-`92`, `0xFF` | second marker position / not present |
| `SS_Marker_Value` | 1 | `0x00`, `0x01`, `0x02` | marker pattern |
| `CS_SYNC_Payload_Pattern` | 1 | `0x00`-`0x07`, `0x80` | PRBS/pattern/user payload |
| `CS_SYNC_User_Payload` | 16 | `0xXX..XX` | user payload |

応答:

```text
04 0E 04  Num_HCI_Command_Packets  95 20  Status
```

追加で発生しうる CS result event:

```text
04 3E LL  31 ...   # HCI_LE_CS_Subevent_Result, Subevent_Code = 0x31
04 3E LL  32 ...   # HCI_LE_CS_Subevent_Result_Continue, Subevent_Code = 0x32
```

---

### 5.2 HCI_LE_CS_Test_End

参照:
- Bluetooth Core Specification v6.3 Vol 6, Part F, Section 2.3
- Bluetooth Core Specification v6.3 Vol 4, Part E, Section 7.8.143

目的: 実行中の CS test を停止する。

UART HCI byte template:

```text
01 96 20 00
```

即時応答:

```text
04 0F 04  Status  Num_HCI_Command_Packets  96 20
```

完了event:

```text
04 3E 02  33  Status
```

| Field | Size | 説明 |
|---|---:|---|
| `Subevent_Code` | 1 | `0x33` = `HCI_LE_CS_Test_End_Complete` |
| `Status` | 1 | `0x00` = success。`0x01`-`0xFF` = error |

---

## 6. 共通パラメータ辞書

### 6.1 LE RF Channel

`RX_Channel` / `TX_Channel` の解釈:

```text
N = (F - 2402) / 2
F = 2402 + 2N MHz
Range: N = 0x00 to 0x27
```

よく使う例:

| Channel value | Frequency |
|---:|---:|
| `0x00` | 2402 MHz |
| `0x13` | 2440 MHz |
| `0x27` | 2480 MHz |

### 6.2 PHY

Receiver Test:

| Value | Meaning |
|---:|---|
| `0x01` | LE 1M PHY |
| `0x02` | LE 2M PHY |
| `0x03` | LE Coded PHY |

Transmitter Test:

| Value | Meaning |
|---:|---|
| `0x01` | LE 1M PHY |
| `0x02` | LE 2M PHY |
| `0x03` | LE Coded PHY with S=8 |
| `0x04` | LE Coded PHY with S=2 |

### 6.3 Packet_Payload

| Value | Pattern |
|---:|---|
| `0x00` | PRBS9 |
| `0x01` | repeated `11110000` |
| `0x02` | repeated `10101010` |
| `0x03` | PRBS15 |
| `0x04` | repeated `11111111` |
| `0x05` | repeated `00000000` |
| `0x06` | repeated `00001111` |
| `0x07` | repeated `01010101` |

### 6.4 Modulation_Index

| Value | Meaning |
|---:|---|
| `0x00` | standard modulation index |
| `0x01` | stable modulation index |

### 6.5 Status

| Value | Meaning |
|---:|---|
| `0x00` | command succeeded |
| `0x01`-`0xFF` | command failed。Controller Error Codesを参照 |

---

## 7. 具体例

### 7.1 TX: 2440 MHz / 37 bytes / PRBS9 / LE 1M

```text
01 34 20 04  13 25 00 01
```

解釈:

| Byte(s) | Meaning |
|---|---|
| `01` | HCI Command packet indicator |
| `34 20` | Opcode `0x2034` = `HCI_LE_Transmitter_Test [v2]` |
| `04` | parameter length = 4 |
| `13` | `TX_Channel = 19` → 2440 MHz |
| `25` | `Test_Data_Length = 37` |
| `00` | PRBS9 |
| `01` | LE 1M PHY |

### 7.2 TX: 2440 MHz / 37 bytes / PRBS9 / LE 2M

```text
01 34 20 04  13 25 00 02
```

### 7.3 TX: 2440 MHz / 37 bytes / PRBS9 / LE Coded S=8

```text
01 34 20 04  13 25 00 03
```

### 7.4 TX: 2440 MHz / 37 bytes / PRBS9 / LE Coded S=2

```text
01 34 20 04  13 25 00 04
```

### 7.5 RX: 2440 MHz / LE 1M / standard modulation index

```text
01 33 20 03  13 01 00
```

### 7.6 End current test

```text
01 1F 20 00
```

受信テスト後の例:

```text
04 0E 06  01 1F 20  00  34 12
```

解釈:

| Byte(s) | Meaning |
|---|---|
| `04` | HCI Event packet indicator |
| `0E` | HCI_Command_Complete |
| `06` | parameter length = 6 |
| `01` | command packet credit |
| `1F 20` | command opcode = `0x201F` = `HCI_LE_Test_End` |
| `00` | Status success |
| `34 12` | `Num_Packets = 0x1234` |

---

## 8. パーサ実装メモ

### 8.1 command 判定手順

```python
def parse_hci_uart_command(frame: bytes) -> dict:
    # frame example: b"\x01\x34\x20\x04\x13\x25\x00\x01"
    if frame[0] != 0x01:
        raise ValueError("not HCI Command packet on UART HCI")

    opcode = frame[1] | (frame[2] << 8)
    plen = frame[3]
    params = frame[4:4 + plen]

    ogf = (opcode >> 10) & 0x3F
    ocf = opcode & 0x03FF

    return {
        "opcode": opcode,
        "ogf": ogf,
        "ocf": ocf,
        "parameter_total_length": plen,
        "parameters": params,
    }
```

### 8.2 Direct Test Mode command 判定

```python
DTM_COMMANDS = {
    0x201D: "HCI_LE_Receiver_Test[v1]",
    0x2033: "HCI_LE_Receiver_Test[v2]",
    0x204F: "HCI_LE_Receiver_Test[v3]",
    0x201E: "HCI_LE_Transmitter_Test[v1]",
    0x2034: "HCI_LE_Transmitter_Test[v2]",
    0x2050: "HCI_LE_Transmitter_Test[v3]",
    0x207B: "HCI_LE_Transmitter_Test[v4]",
    0x201F: "HCI_LE_Test_End",
    0x2095: "HCI_LE_CS_Test",
    0x2096: "HCI_LE_CS_Test_End",
}
```

### 8.3 variable length command の注意

`HCI_LE_Receiver_Test [v3]`:

```python
expected_len = 7 + switching_pattern_length
```

`HCI_LE_Transmitter_Test [v3]`:

```python
expected_len = 7 + switching_pattern_length
```

`HCI_LE_Transmitter_Test [v4]`:

```python
expected_len = 8 + switching_pattern_length
```

`HCI_LE_CS_Test`:

```python
expected_len = 30 + override_parameters_length
```

### 8.4 event 判定手順

```python
def parse_hci_uart_event(frame: bytes) -> dict:
    # frame example: b"\x04\x0e\x04\x01\x34\x20\x00"
    if frame[0] != 0x04:
        raise ValueError("not HCI Event packet on UART HCI")

    event_code = frame[1]
    plen = frame[2]
    params = frame[3:3 + plen]

    if event_code == 0x0E:  # HCI_Command_Complete
        num_packets = params[0]
        cmd_opcode = params[1] | (params[2] << 8)
        return_params = params[3:]
        return {
            "event": "HCI_Command_Complete",
            "num_hci_command_packets": num_packets,
            "command_opcode": cmd_opcode,
            "return_parameters": return_params,
        }

    if event_code == 0x0F:  # HCI_Command_Status
        status = params[0]
        num_packets = params[1]
        cmd_opcode = params[2] | (params[3] << 8)
        return {
            "event": "HCI_Command_Status",
            "status": status,
            "num_hci_command_packets": num_packets,
            "command_opcode": cmd_opcode,
        }

    if event_code == 0x3E:  # LE Meta Event
        subevent_code = params[0]
        return {
            "event": "HCI_LE_Meta_Event",
            "subevent_code": subevent_code,
            "subevent_parameters": params[1:],
        }

    return {
        "event_code": event_code,
        "parameters": params,
    }
```

### 8.5 LE Meta Event のうち PHY試験で重要なもの

| Event | Event code | Subevent code | 用途 |
|---|---:|---:|---|
| `HCI_LE_Connectionless_IQ_Report` | `0x3E` | `0x15` | Receiver Test v3でCTEを使う場合にIQ sample報告として出る可能性あり |
| `HCI_LE_CS_Subevent_Result` | `0x3E` | `0x31` | CS subevent result |
| `HCI_LE_CS_Subevent_Result_Continue` | `0x3E` | `0x32` | CS subevent result continuation |
| `HCI_LE_CS_Test_End_Complete` | `0x3E` | `0x33` | CS test end complete |

---

## 9. Supported Commands での確認ポイント

参照: Bluetooth Core Specification v6.3 Vol 4, Part E, Supported Commands table

`HCI_Read_Local_Supported_Commands` の戻り値で、以下のbitが立っているか確認できる。これは command解析の前処理として便利。

| Supported Commands octet | bit | Command |
|---:|---:|---|
| 23 | 3 | `HCI_LE_CS_Test` |
| 23 | 4 | `HCI_LE_CS_Test_End` |
| 28 | 4 | `HCI_LE_Receiver_Test [v1]` |
| 28 | 5 | `HCI_LE_Transmitter_Test [v1]` |
| 28 | 6 | `HCI_LE_Test_End` |
| 35 | 7 | `HCI_LE_Receiver_Test [v2]` |
| 36 | 0 | `HCI_LE_Transmitter_Test [v2]` |
| 39 | 3 | `HCI_LE_Receiver_Test [v3]` |
| 39 | 4 | `HCI_LE_Transmitter_Test [v3]` |
| 45 | 0 | `HCI_LE_Transmitter_Test [v4]` |

---

## 10. 注意: v1/v2/v3/v4 の意味

`HCI_LE_Receiver_Test [v1]` / `[v2]` / `[v3]` や `HCI_LE_Transmitter_Test [v1]` / `[v2]` / `[v3]` / `[v4]` は、Bluetooth Core Specification の版ではなく、同一目的のHCI commandに対する「パラメータ拡張版」です。

同じ名前でも OCF が違うため、解析器では別commandとして扱う。

例:

```text
HCI_LE_Transmitter_Test [v1] -> OCF 0x001E -> Opcode 0x201E -> 01 1E 20 ...
HCI_LE_Transmitter_Test [v2] -> OCF 0x0034 -> Opcode 0x2034 -> 01 34 20 ...
HCI_LE_Transmitter_Test [v3] -> OCF 0x0050 -> Opcode 0x2050 -> 01 50 20 ...
HCI_LE_Transmitter_Test [v4] -> OCF 0x007B -> Opcode 0x207B -> 01 7B 20 ...
```

---

## 11. 解析対象外または実装依存として扱うべきもの

以下は実際のシリアルログに出る可能性があるが、Core v6.3 Vol 6, Part F の RF Test command mapping の中核ではない。

| 種類 | 例 | 扱い |
|---|---|---|
| Controller初期化 | `HCI_Reset`, `HCI_Read_Local_Version_Information` | テスター/ドライバ依存 |
| Capability確認 | `HCI_Read_Local_Supported_Commands`, `HCI_LE_Read_Local_Supported_Features_Page_0` | 補助コマンド |
| 通常接続PHY制御 | `HCI_LE_Set_PHY`, `HCI_LE_Read_PHY` | 接続中PHY制御。Direct Test Mode commandではない |
| Vendor-specific | OGF `0x3F`, Event `0xFF` | vendor実装依存 |
| 2-wire UART DTM | `LE_Test_Setup`, `LE_Receiver_Test`, `LE_Transmitter_Test`, `LE_Test_End` | HCIではなく2-wire UART Test Interface |

---

## 12. 実装時の最小判別表

まずはこの表だけ実装すると、通常の LE PHY送受信試験ログの主要commandは判別できる。

| UART prefix | Opcode | Command | Length rule |
|---|---:|---|---|
| `01 1D 20` | `0x201D` | `HCI_LE_Receiver_Test [v1]` | `1` |
| `01 33 20` | `0x2033` | `HCI_LE_Receiver_Test [v2]` | `3` |
| `01 4F 20` | `0x204F` | `HCI_LE_Receiver_Test [v3]` | `7 + Switching_Pattern_Length` |
| `01 1E 20` | `0x201E` | `HCI_LE_Transmitter_Test [v1]` | `3` |
| `01 34 20` | `0x2034` | `HCI_LE_Transmitter_Test [v2]` | `4` |
| `01 50 20` | `0x2050` | `HCI_LE_Transmitter_Test [v3]` | `7 + Switching_Pattern_Length` |
| `01 7B 20` | `0x207B` | `HCI_LE_Transmitter_Test [v4]` | `8 + Switching_Pattern_Length` |
| `01 1F 20 00` | `0x201F` | `HCI_LE_Test_End` | `0` |
| `01 95 20` | `0x2095` | `HCI_LE_CS_Test` | `30 + Override_Parameters_Length` |
| `01 96 20 00` | `0x2096` | `HCI_LE_CS_Test_End` | `0` |
