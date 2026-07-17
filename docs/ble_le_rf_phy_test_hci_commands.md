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
  - Vol 4, Part E, Section 6.27: Supported Commands bit field
  - Vol 4, Part E, Section 7.3.2: HCI_Reset command
  - Vol 4, Part E, Section 7.4.2: HCI_Read_Local_Supported_Commands command
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
- UARTボーレート設定、RTS/CTS、ハードウェアリセット制御
- OSやベンダードライバが決定する初期化シーケンス
- `HCI_Reset`、`HCI_Read_Local_Version_Information` などの標準補助コマンドを使用するタイミング
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
    informational_parameters_ogf: 0x04
    controller_and_baseband_ogf: 0x03

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

  - name: HCI_Reset
    category: Controller_and_Baseband
    purpose: controller_initialization_or_recovery
    versions:
      - version: none
        ogf: 0x03
        ocf: 0x0003
        opcode: 0x0C03
        uart_prefix: "01 03 0C"
        parameter_total_length: 0
        parameters: []
        response: HCI_Command_Complete_Status
        supported_commands:
          octet: 5
          bit: 7

  - name: HCI_Read_Local_Supported_Commands
    category: Informational_Parameters
    purpose: capability_query
    versions:
      - version: v1
        ogf: 0x04
        ocf: 0x0002
        opcode: 0x1002
        uart_prefix: "01 02 10"
        parameter_total_length: 0
        parameters: []
        response: HCI_Command_Complete_Status_Supported_Commands_64_Octets
      - version: v2
        ogf: 0x04
        ocf: 0x0010
        opcode: 0x1010
        uart_prefix: "01 10 10"
        parameter_total_length: 0
        parameters: []
        response: HCI_Command_Complete_Status_Supported_Commands_251_Octets
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

### 8.6 補助コマンド: HCI_Reset

参照: Bluetooth Core Specification v6.3 Vol 4, Part E, Section 7.3.2

目的: Controllerをリセットし、Link Manager / Baseband / Link Layerの状態を初期化する。LE RF PHY試験そのものの開始・終了コマンドではないが、テスト前のController初期化、異常状態からの復帰、HCI analyzerの初期シーケンス解析で出現しやすい。

`HCI_Reset` は Controller and Baseband command group のコマンドである。したがって OGF は `0x03`。

Opcode 計算:

~~~text
Opcode = (OGF << 10) | OCF
       = (0x03 << 10) | 0x0003
       = 0x0C03
~~~

UART HCI byte template:

~~~text
01 03 0C 00
~~~

内訳:

~~~text
01        HCI Command packet indicator
03 0C     Opcode = 0x0C03 = HCI_Reset
00        Parameter_Total_Length = 0
~~~

応答:

~~~text
04 0E 04  Num_HCI_Command_Packets  03 0C  Status
~~~

成功例:

~~~text
04 0E 04  01 03 0C 00
~~~

| Field | Size | Value | 説明 |
|---|---:|---|---|
| `Status` | 1 | `0x00` | `HCI_Reset` command succeeded, was received and will be executed |
| `Status` | 1 | `0x01`-`0xFF` | command failed。Controller Error Codesを参照 |

仕様書に明記されている事項:
- `HCI_Reset` は、BR/EDR ControllerではControllerとLink Managerを、LE ControllerではLink Layerをリセットする。
- BR/EDRとLEの両方をサポートするControllerでは、Link Manager、Baseband、Link Layerをリセットする。
- HCI transport layerには影響しない。
- リセット完了後、現在のoperational stateは失われ、Controllerはstandby modeに入り、仕様でdefault valueが定義されているパラメータはdefault valueへ戻る。
- Hostは `HCI_Reset` に対応する `HCI_Command_Complete` eventを受信するまで、追加のHCI commandを送ってはならない。
- `HCI_Reset` が必ずhardware resetを行うとは限らない。

implementation specific な事項:
- `HCI_Reset` がhardware resetを行うかどうかは implementation defined。

Supported Commandsでの確認:
- `HCI_Read_Local_Supported_Commands` で対応状況を確認する場合、`HCI_Reset` は `Supported_Commands` octet 5 bit 7で判定する。

---

## 9. Capability query: HCI_Read_Local_Supported_Commands

目的: Controller がどの標準HCIコマンドをサポートしているかを、テスト開始前に問い合わせる。

参照:
- Bluetooth Core Specification v6.3 Vol 4, Part E, Section 7.4.2: HCI_Read_Local_Supported_Commands command
- Bluetooth Core Specification v6.3 Vol 4, Part E, Section 6.27: Supported Commands bit field
- Bluetooth Core Specification v6.3 Vol 4, Part E, Section 7.7.14: HCI_Command_Complete event

### 9.1 コマンド定義

`HCI_Read_Local_Supported_Commands` は Informational Parameters command group のコマンドであり、LE Controller command ではない。したがって OGF は `0x08` ではなく `0x04`。

Opcode 計算:

```text
Opcode = (OGF << 10) | OCF
```

| Command | OGF | OCF | Opcode | UART HCI bytes | Parameters | 戻り値 |
|---|---:|---:|---:|---|---|---|
| `HCI_Read_Local_Supported_Commands [v1]` | `0x04` | `0x0002` | `0x1002` | `01 02 10 00` | なし | `Status` + `Supported_Commands[64]` |
| `HCI_Read_Local_Supported_Commands [v2]` | `0x04` | `0x0010` | `0x1010` | `01 10 10 00` | なし | `Status` + `Supported_Commands[251]` |

### 9.2 UART HCIコマンド例

v1:

```text
01 02 10 00
```

内訳:

```text
01        HCI Command packet indicator
02 10     Opcode = 0x1002 = HCI_Read_Local_Supported_Commands [v1]
00        Parameter_Total_Length = 0
```

v2:

```text
01 10 10 00
```

内訳:

```text
01        HCI Command packet indicator
10 10     Opcode = 0x1010 = HCI_Read_Local_Supported_Commands [v2]
00        Parameter_Total_Length = 0
```

### 9.3 Command Complete応答の解析

`HCI_Read_Local_Supported_Commands` は `HCI_Command_Complete` event で応答される。

HCI UART上のイベント基本形:

```text
04 0E Event_Parameter_Total_Length Num_HCI_Command_Packets Command_Opcode_LSB Command_Opcode_MSB Status Supported_Commands...
```

v1成功時の期待長:

```text
Event_Parameter_Total_Length = 0x44
= Num_HCI_Command_Packets(1)
+ Command_Opcode(2)
+ Status(1)
+ Supported_Commands(64)
```

v2成功時の期待長:

```text
Event_Parameter_Total_Length = 0xFF
= Num_HCI_Command_Packets(1)
+ Command_Opcode(2)
+ Status(1)
+ Supported_Commands(251)
```

解析器では `Command_Opcode` が `0x1002` なら v1応答、`0x1010` なら v2応答として扱う。

### 9.4 Supported_Commands bitの読み方

`Supported_Commands` は octet配列であり、各コマンドに割り当てられた octet / bit を見る。bit値が `1` の場合、そのHCIコマンドと、そのコマンドに必要なfeatureをControllerがサポートしていることを示す。bit値が `0` の場合、未サポートまたは未定義として扱う。

Python実装例:

```python
def is_supported(supported_commands: bytes, octet: int, bit: int) -> bool:
    if octet >= len(supported_commands):
        return False
    return bool(supported_commands[octet] & (1 << bit))
```

### 9.5 Supported_Commands応答表の分類方針

この表は `HCI_Read_Local_Supported_Commands` の `Supported_Commands` 応答を解析して、GUI上で「PHY試験に直接使うコマンド」と「それ以外の標準HCIコマンド」を区別するための対応表である。

`Scope` の意味:

| Scope | 意味 |
|---|---|
| `PHY_TEST_CORE` | LE Direct Test Mode の通常PHY試験で直接使うコマンド |
| `PHY_TEST_CS` | Channel Sounding RFPHY test で直接使うコマンド |
| `CAPABILITY_QUERY` | PHY試験コマンドではないが、本表を取得するために使う問い合わせコマンド |
| `OTHER_STANDARD` | 標準HCIコマンドだが、本資料のLE RF PHY試験の直接制御対象ではないもの |
| `RESERVED` | Reserved for future use |
| `PREVIOUSLY_USED` | Previously used |

parser / GUI では、`PHY_TEST_CORE` と `PHY_TEST_CS` を「PHY試験用」として扱い、それ以外を「その他」として扱う。`CAPABILITY_QUERY` はGUI初期化用の補助コマンドとして常に別扱いにするとよい。

### 9.6 Supported_Commands応答表

`HCI_Read_Local_Supported_Commands [v1]` は octet 0〜63 を返す。`HCI_Read_Local_Supported_Commands [v2]` は octet 0〜250 を返す。Core v6.3 の Section 6.27 で定義済みのコマンドは octet 0〜49 bit 5 までであり、octet 49 bit 6〜7 および octet 50〜250 は parser 実装上 `RESERVED` として扱う。

| Supported Commands octet | bit | Scope | Command / meaning |
|---:|---:|---|---|
| 0 | 0 | `OTHER_STANDARD` | `HCI_Inquiry` |
| 0 | 1 | `OTHER_STANDARD` | `HCI_Inquiry_Cancel` |
| 0 | 2 | `OTHER_STANDARD` | `HCI_Periodic_Inquiry_Mode` |
| 0 | 3 | `OTHER_STANDARD` | `HCI_Exit_Periodic_Inquiry_Mode` |
| 0 | 4 | `OTHER_STANDARD` | `HCI_Create_Connection` |
| 0 | 5 | `OTHER_STANDARD` | `HCI_Disconnect` |
| 0 | 6 | `PREVIOUSLY_USED` | Previously used |
| 0 | 7 | `OTHER_STANDARD` | `HCI_Create_Connection_Cancel` |
| 1 | 0 | `OTHER_STANDARD` | `HCI_Accept_Connection_Request` |
| 1 | 1 | `OTHER_STANDARD` | `HCI_Reject_Connection_Request` |
| 1 | 2 | `OTHER_STANDARD` | `HCI_Link_Key_Request_Reply` |
| 1 | 3 | `OTHER_STANDARD` | `HCI_Link_Key_Request_Negative_Reply` |
| 1 | 4 | `OTHER_STANDARD` | `HCI_PIN_Code_Request_Reply` |
| 1 | 5 | `OTHER_STANDARD` | `HCI_PIN_Code_Request_Negative_Reply` |
| 1 | 6 | `OTHER_STANDARD` | `HCI_Change_Connection_Packet_Type` |
| 1 | 7 | `OTHER_STANDARD` | `HCI_Authentication_Requested` |
| 2 | 0 | `OTHER_STANDARD` | `HCI_Set_Connection_Encryption` |
| 2 | 1 | `OTHER_STANDARD` | `HCI_Change_Connection_Link_Key` |
| 2 | 2 | `OTHER_STANDARD` | `HCI_Link_Key_Selection` |
| 2 | 3 | `OTHER_STANDARD` | `HCI_Remote_Name_Request` |
| 2 | 4 | `OTHER_STANDARD` | `HCI_Remote_Name_Request_Cancel` |
| 2 | 5 | `OTHER_STANDARD` | `HCI_Read_Remote_Supported_Features` |
| 2 | 6 | `OTHER_STANDARD` | `HCI_Read_Remote_Extended_Features` |
| 2 | 7 | `OTHER_STANDARD` | `HCI_Read_Remote_Version_Information` |
| 3 | 0 | `OTHER_STANDARD` | `HCI_Read_Clock_Offset` |
| 3 | 1 | `OTHER_STANDARD` | `HCI_Read_LMP_Handle` |
| 3 | 2 | `RESERVED` | Reserved for future use |
| 3 | 3 | `RESERVED` | Reserved for future use |
| 3 | 4 | `RESERVED` | Reserved for future use |
| 3 | 5 | `RESERVED` | Reserved for future use |
| 3 | 6 | `RESERVED` | Reserved for future use |
| 3 | 7 | `RESERVED` | Reserved for future use |
| 4 | 0 | `RESERVED` | Reserved for future use |
| 4 | 1 | `OTHER_STANDARD` | `HCI_Hold_Mode` |
| 4 | 2 | `OTHER_STANDARD` | `HCI_Sniff_Mode` |
| 4 | 3 | `OTHER_STANDARD` | `HCI_Exit_Sniff_Mode` |
| 4 | 4 | `PREVIOUSLY_USED` | Previously used |
| 4 | 5 | `PREVIOUSLY_USED` | Previously used |
| 4 | 6 | `OTHER_STANDARD` | `HCI_QoS_Setup` |
| 4 | 7 | `OTHER_STANDARD` | `HCI_Role_Discovery` |
| 5 | 0 | `OTHER_STANDARD` | `HCI_Switch_Role` |
| 5 | 1 | `OTHER_STANDARD` | `HCI_Read_Link_Policy_Settings` |
| 5 | 2 | `OTHER_STANDARD` | `HCI_Write_Link_Policy_Settings` |
| 5 | 3 | `OTHER_STANDARD` | `HCI_Read_Default_Link_Policy_Settings` |
| 5 | 4 | `OTHER_STANDARD` | `HCI_Write_Default_Link_Policy_Settings` |
| 5 | 5 | `OTHER_STANDARD` | `HCI_Flow_Specification` |
| 5 | 6 | `OTHER_STANDARD` | `HCI_Set_Event_Mask` |
| 5 | 7 | `OTHER_STANDARD` | `HCI_Reset` |
| 6 | 0 | `OTHER_STANDARD` | `HCI_Set_Event_Filter` |
| 6 | 1 | `OTHER_STANDARD` | `HCI_Flush` |
| 6 | 2 | `OTHER_STANDARD` | `HCI_Read_PIN_Type` |
| 6 | 3 | `OTHER_STANDARD` | `HCI_Write_PIN_Type` |
| 6 | 4 | `PREVIOUSLY_USED` | Previously used |
| 6 | 5 | `OTHER_STANDARD` | `HCI_Read_Stored_Link_Key` |
| 6 | 6 | `OTHER_STANDARD` | `HCI_Write_Stored_Link_Key` |
| 6 | 7 | `OTHER_STANDARD` | `HCI_Delete_Stored_Link_Key` |
| 7 | 0 | `OTHER_STANDARD` | `HCI_Write_Local_Name` |
| 7 | 1 | `OTHER_STANDARD` | `HCI_Read_Local_Name` |
| 7 | 2 | `OTHER_STANDARD` | `HCI_Read_Connection_Accept_Timeout` |
| 7 | 3 | `OTHER_STANDARD` | `HCI_Write_Connection_Accept_Timeout` |
| 7 | 4 | `OTHER_STANDARD` | `HCI_Read_Page_Timeout` |
| 7 | 5 | `OTHER_STANDARD` | `HCI_Write_Page_Timeout` |
| 7 | 6 | `OTHER_STANDARD` | `HCI_Read_Scan_Enable` |
| 7 | 7 | `OTHER_STANDARD` | `HCI_Write_Scan_Enable` |
| 8 | 0 | `OTHER_STANDARD` | `HCI_Read_Page_Scan_Activity` |
| 8 | 1 | `OTHER_STANDARD` | `HCI_Write_Page_Scan_Activity` |
| 8 | 2 | `OTHER_STANDARD` | `HCI_Read_Inquiry_Scan_Activity` |
| 8 | 3 | `OTHER_STANDARD` | `HCI_Write_Inquiry_Scan_Activity` |
| 8 | 4 | `OTHER_STANDARD` | `HCI_Read_Authentication_Enable` |
| 8 | 5 | `OTHER_STANDARD` | `HCI_Write_Authentication_Enable` |
| 8 | 6 | `PREVIOUSLY_USED` | Previously used |
| 8 | 7 | `PREVIOUSLY_USED` | Previously used |
| 9 | 0 | `OTHER_STANDARD` | `HCI_Read_Class_Of_Device` |
| 9 | 1 | `OTHER_STANDARD` | `HCI_Write_Class_Of_Device` |
| 9 | 2 | `OTHER_STANDARD` | `HCI_Read_Voice_Setting` |
| 9 | 3 | `OTHER_STANDARD` | `HCI_Write_Voice_Setting` |
| 9 | 4 | `OTHER_STANDARD` | `HCI_Read_Automatic_Flush_Timeout` |
| 9 | 5 | `OTHER_STANDARD` | `HCI_Write_Automatic_Flush_Timeout` |
| 9 | 6 | `OTHER_STANDARD` | `HCI_Read_Num_Broadcast_Retransmissions` |
| 9 | 7 | `OTHER_STANDARD` | `HCI_Write_Num_Broadcast_Retransmissions` |
| 10 | 0 | `OTHER_STANDARD` | `HCI_Read_Hold_Mode_Activity` |
| 10 | 1 | `OTHER_STANDARD` | `HCI_Write_Hold_Mode_Activity` |
| 10 | 2 | `OTHER_STANDARD` | `HCI_Read_Transmit_Power_Level` |
| 10 | 3 | `OTHER_STANDARD` | `HCI_Read_Synchronous_Flow_Control_Enable` |
| 10 | 4 | `OTHER_STANDARD` | `HCI_Write_Synchronous_Flow_Control_Enable` |
| 10 | 5 | `OTHER_STANDARD` | `HCI_Set_Controller_To_Host_Flow_Control` |
| 10 | 6 | `OTHER_STANDARD` | `HCI_Host_Buffer_Size` |
| 10 | 7 | `OTHER_STANDARD` | `HCI_Host_Number_Of_Completed_Packets` |
| 11 | 0 | `OTHER_STANDARD` | `HCI_Read_Link_Supervision_Timeout` |
| 11 | 1 | `OTHER_STANDARD` | `HCI_Write_Link_Supervision_Timeout` |
| 11 | 2 | `OTHER_STANDARD` | `HCI_Read_Number_Of_Supported_IAC` |
| 11 | 3 | `OTHER_STANDARD` | `HCI_Read_Current_IAC_LAP` |
| 11 | 4 | `OTHER_STANDARD` | `HCI_Write_Current_IAC_LAP` |
| 11 | 5 | `PREVIOUSLY_USED` | Previously used |
| 11 | 6 | `PREVIOUSLY_USED` | Previously used |
| 11 | 7 | `PREVIOUSLY_USED` | Previously used |
| 12 | 0 | `PREVIOUSLY_USED` | Previously used |
| 12 | 1 | `OTHER_STANDARD` | `HCI_Set_AFH_Host_Channel_Classification` |
| 12 | 2 | `OTHER_STANDARD` | `HCI_LE_CS_Read_Remote_FAE_Table` |
| 12 | 3 | `OTHER_STANDARD` | `HCI_LE_CS_Write_Cached_Remote_FAE_Table` |
| 12 | 4 | `OTHER_STANDARD` | `HCI_Read_Inquiry_Scan_Type` |
| 12 | 5 | `OTHER_STANDARD` | `HCI_Write_Inquiry_Scan_Type` |
| 12 | 6 | `OTHER_STANDARD` | `HCI_Read_Inquiry_Mode` |
| 12 | 7 | `OTHER_STANDARD` | `HCI_Write_Inquiry_Mode` |
| 13 | 0 | `OTHER_STANDARD` | `HCI_Read_Page_Scan_Type` |
| 13 | 1 | `OTHER_STANDARD` | `HCI_Write_Page_Scan_Type` |
| 13 | 2 | `OTHER_STANDARD` | `HCI_Read_AFH_Channel_Assessment_Mode` |
| 13 | 3 | `OTHER_STANDARD` | `HCI_Write_AFH_Channel_Assessment_Mode` |
| 13 | 4 | `RESERVED` | Reserved for future use |
| 13 | 5 | `RESERVED` | Reserved for future use |
| 13 | 6 | `RESERVED` | Reserved for future use |
| 13 | 7 | `RESERVED` | Reserved for future use |
| 14 | 0 | `RESERVED` | Reserved for future use |
| 14 | 1 | `RESERVED` | Reserved for future use |
| 14 | 2 | `RESERVED` | Reserved for future use |
| 14 | 3 | `OTHER_STANDARD` | `HCI_Read_Local_Version_Information` |
| 14 | 4 | `RESERVED` | Reserved for future use |
| 14 | 5 | `OTHER_STANDARD` | `HCI_Read_Local_Supported_Features` |
| 14 | 6 | `OTHER_STANDARD` | `HCI_Read_Local_Extended_Features` |
| 14 | 7 | `OTHER_STANDARD` | `HCI_Read_Buffer_Size` |
| 15 | 0 | `PREVIOUSLY_USED` | Previously used |
| 15 | 1 | `OTHER_STANDARD` | `HCI_Read_BD_ADDR` |
| 15 | 2 | `OTHER_STANDARD` | `HCI_Read_Failed_Contact_Counter` |
| 15 | 3 | `OTHER_STANDARD` | `HCI_Reset_Failed_Contact_Counter` |
| 15 | 4 | `OTHER_STANDARD` | `HCI_Read_Link_Quality` |
| 15 | 5 | `OTHER_STANDARD` | `HCI_Read_RSSI` |
| 15 | 6 | `OTHER_STANDARD` | `HCI_Read_AFH_Channel_Map` |
| 15 | 7 | `OTHER_STANDARD` | `HCI_Read_Clock` |
| 16 | 0 | `OTHER_STANDARD` | `HCI_Read_Loopback_Mode` |
| 16 | 1 | `OTHER_STANDARD` | `HCI_Write_Loopback_Mode` |
| 16 | 2 | `OTHER_STANDARD` | `HCI_Enable_Implementation_Under_Test_Mode` |
| 16 | 3 | `OTHER_STANDARD` | `HCI_Setup_Synchronous_Connection` |
| 16 | 4 | `OTHER_STANDARD` | `HCI_Accept_Synchronous_Connection_Request` |
| 16 | 5 | `OTHER_STANDARD` | `HCI_Reject_Synchronous_Connection_Request` |
| 16 | 6 | `OTHER_STANDARD` | `HCI_LE_CS_Create_Config` |
| 16 | 7 | `OTHER_STANDARD` | `HCI_LE_CS_Remove_Config` |
| 17 | 0 | `OTHER_STANDARD` | `HCI_Read_Extended_Inquiry_Response` |
| 17 | 1 | `OTHER_STANDARD` | `HCI_Write_Extended_Inquiry_Response` |
| 17 | 2 | `OTHER_STANDARD` | `HCI_Refresh_Encryption_Key` |
| 17 | 3 | `RESERVED` | Reserved for future use |
| 17 | 4 | `OTHER_STANDARD` | `HCI_Sniff_Subrating` |
| 17 | 5 | `OTHER_STANDARD` | `HCI_Read_Simple_Pairing_Mode` |
| 17 | 6 | `OTHER_STANDARD` | `HCI_Write_Simple_Pairing_Mode` |
| 17 | 7 | `OTHER_STANDARD` | `HCI_Read_Local_OOB_Data` |
| 18 | 0 | `OTHER_STANDARD` | `HCI_Read_Inquiry_Response_Transmit_Power_Level` |
| 18 | 1 | `OTHER_STANDARD` | `HCI_Write_Inquiry_Transmit_Power_Level` |
| 18 | 2 | `OTHER_STANDARD` | `HCI_Read_Default_Erroneous_Data_Reporting` |
| 18 | 3 | `OTHER_STANDARD` | `HCI_Write_Default_Erroneous_Data_Reporting` |
| 18 | 4 | `RESERVED` | Reserved for future use |
| 18 | 5 | `RESERVED` | Reserved for future use |
| 18 | 6 | `RESERVED` | Reserved for future use |
| 18 | 7 | `OTHER_STANDARD` | `HCI_IO_Capability_Request_Reply` |
| 19 | 0 | `OTHER_STANDARD` | `HCI_User_Confirmation_Request_Reply` |
| 19 | 1 | `OTHER_STANDARD` | `HCI_User_Confirmation_Request_Negative_Reply` |
| 19 | 2 | `OTHER_STANDARD` | `HCI_User_Passkey_Request_Reply` |
| 19 | 3 | `OTHER_STANDARD` | `HCI_User_Passkey_Request_Negative_Reply` |
| 19 | 4 | `OTHER_STANDARD` | `HCI_Remote_OOB_Data_Request_Reply` |
| 19 | 5 | `OTHER_STANDARD` | `HCI_Write_Simple_Pairing_Debug_Mode` |
| 19 | 6 | `OTHER_STANDARD` | `HCI_Enhanced_Flush` |
| 19 | 7 | `OTHER_STANDARD` | `HCI_Remote_OOB_Data_Request_Negative_Reply` |
| 20 | 0 | `RESERVED` | Reserved for future use |
| 20 | 1 | `RESERVED` | Reserved for future use |
| 20 | 2 | `OTHER_STANDARD` | `HCI_Send_Keypress_Notification` |
| 20 | 3 | `OTHER_STANDARD` | `HCI_IO_Capability_Request_Negative_Reply` |
| 20 | 4 | `OTHER_STANDARD` | `HCI_Read_Encryption_Key_Size` |
| 20 | 5 | `OTHER_STANDARD` | `HCI_LE_CS_Read_Local_Supported_Capabilities [v1]` |
| 20 | 6 | `OTHER_STANDARD` | `HCI_LE_CS_Read_Remote_Supported_Capabilities` |
| 20 | 7 | `OTHER_STANDARD` | `HCI_LE_CS_Write_Cached_Remote_Supported_Capabilities [v1]` |
| 21 | 0 | `PREVIOUSLY_USED` | Previously used |
| 21 | 1 | `PREVIOUSLY_USED` | Previously used |
| 21 | 2 | `PREVIOUSLY_USED` | Previously used |
| 21 | 3 | `PREVIOUSLY_USED` | Previously used |
| 21 | 4 | `PREVIOUSLY_USED` | Previously used |
| 21 | 5 | `PREVIOUSLY_USED` | Previously used |
| 21 | 6 | `PREVIOUSLY_USED` | Previously used |
| 21 | 7 | `PREVIOUSLY_USED` | Previously used |
| 22 | 0 | `PREVIOUSLY_USED` | Previously used |
| 22 | 1 | `PREVIOUSLY_USED` | Previously used |
| 22 | 2 | `OTHER_STANDARD` | `HCI_Set_Event_Mask_Page_2` |
| 22 | 3 | `PREVIOUSLY_USED` | Previously used |
| 22 | 4 | `PREVIOUSLY_USED` | Previously used |
| 22 | 5 | `PREVIOUSLY_USED` | Previously used |
| 22 | 6 | `PREVIOUSLY_USED` | Previously used |
| 22 | 7 | `PREVIOUSLY_USED` | Previously used |
| 23 | 0 | `OTHER_STANDARD` | `HCI_Read_Flow_Control_Mode` |
| 23 | 1 | `OTHER_STANDARD` | `HCI_Write_Flow_Control_Mode` |
| 23 | 2 | `OTHER_STANDARD` | `HCI_Read_Data_Block_Size` |
| 23 | 3 | `PHY_TEST_CS` | `HCI_LE_CS_Test` |
| 23 | 4 | `PHY_TEST_CS` | `HCI_LE_CS_Test_End` |
| 23 | 5 | `PREVIOUSLY_USED` | Previously used |
| 23 | 6 | `PREVIOUSLY_USED` | Previously used |
| 23 | 7 | `PREVIOUSLY_USED` | Previously used |
| 24 | 0 | `OTHER_STANDARD` | `HCI_Read_Enhanced_Transmit_Power_Level` |
| 24 | 1 | `OTHER_STANDARD` | `HCI_LE_CS_Security_Enable` |
| 24 | 2 | `PREVIOUSLY_USED` | Previously used |
| 24 | 3 | `PREVIOUSLY_USED` | Previously used |
| 24 | 4 | `PREVIOUSLY_USED` | Previously used |
| 24 | 5 | `OTHER_STANDARD` | `HCI_Read_LE_Host_Support` |
| 24 | 6 | `OTHER_STANDARD` | `HCI_Write_LE_Host_Support` |
| 24 | 7 | `OTHER_STANDARD` | `HCI_LE_CS_Set_Default_Settings` |
| 25 | 0 | `OTHER_STANDARD` | `HCI_LE_Set_Event_Mask [v1]` |
| 25 | 1 | `OTHER_STANDARD` | `HCI_LE_Read_Buffer_Size [v1]` |
| 25 | 2 | `OTHER_STANDARD` | `HCI_LE_Read_Local_Supported_Features_Page_0` |
| 25 | 3 | `RESERVED` | Reserved for future use |
| 25 | 4 | `OTHER_STANDARD` | `HCI_LE_Set_Random_Address` |
| 25 | 5 | `OTHER_STANDARD` | `HCI_LE_Set_Advertising_Parameters` |
| 25 | 6 | `OTHER_STANDARD` | `HCI_LE_Read_Advertising_Physical_Channel_Tx_Power` |
| 25 | 7 | `OTHER_STANDARD` | `HCI_LE_Set_Advertising_Data` |
| 26 | 0 | `OTHER_STANDARD` | `HCI_LE_Set_Scan_Response_Data` |
| 26 | 1 | `OTHER_STANDARD` | `HCI_LE_Set_Advertising_Enable` |
| 26 | 2 | `OTHER_STANDARD` | `HCI_LE_Set_Scan_Parameters` |
| 26 | 3 | `OTHER_STANDARD` | `HCI_LE_Set_Scan_Enable` |
| 26 | 4 | `OTHER_STANDARD` | `HCI_LE_Create_Connection` |
| 26 | 5 | `OTHER_STANDARD` | `HCI_LE_Create_Connection_Cancel` |
| 26 | 6 | `OTHER_STANDARD` | `HCI_LE_Read_Filter_Accept_List_Size` |
| 26 | 7 | `OTHER_STANDARD` | `HCI_LE_Clear_Filter_Accept_List` |
| 27 | 0 | `OTHER_STANDARD` | `HCI_LE_Add_Device_To_Filter_Accept_List` |
| 27 | 1 | `OTHER_STANDARD` | `HCI_LE_Remove_Device_From_Filter_Accept_List` |
| 27 | 2 | `OTHER_STANDARD` | `HCI_LE_Connection_Update` |
| 27 | 3 | `OTHER_STANDARD` | `HCI_LE_Set_Host_Channel_Classification` |
| 27 | 4 | `OTHER_STANDARD` | `HCI_LE_Read_Channel_Map` |
| 27 | 5 | `OTHER_STANDARD` | `HCI_LE_Read_Remote_Features_Page_0` |
| 27 | 6 | `OTHER_STANDARD` | `HCI_LE_Encrypt` |
| 27 | 7 | `OTHER_STANDARD` | `HCI_LE_Rand` |
| 28 | 0 | `OTHER_STANDARD` | `HCI_LE_Enable_Encryption` |
| 28 | 1 | `OTHER_STANDARD` | `HCI_LE_Long_Term_Key_Request_Reply` |
| 28 | 2 | `OTHER_STANDARD` | `HCI_LE_Long_Term_Key_Request_Negative_Reply` |
| 28 | 3 | `OTHER_STANDARD` | `HCI_LE_Read_Supported_States` |
| 28 | 4 | `PHY_TEST_CORE` | `HCI_LE_Receiver_Test [v1]` |
| 28 | 5 | `PHY_TEST_CORE` | `HCI_LE_Transmitter_Test [v1]` |
| 28 | 6 | `PHY_TEST_CORE` | `HCI_LE_Test_End` |
| 28 | 7 | `OTHER_STANDARD` | `HCI_LE_Enable_Monitoring_Advertisers` |
| 29 | 0 | `OTHER_STANDARD` | `HCI_LE_CS_Set_Channel_Classification` |
| 29 | 1 | `OTHER_STANDARD` | `HCI_LE_CS_Set_Procedure_Parameters` |
| 29 | 2 | `OTHER_STANDARD` | `HCI_LE_CS_Procedure_Enable` |
| 29 | 3 | `OTHER_STANDARD` | `HCI_Enhanced_Setup_Synchronous_Connection` |
| 29 | 4 | `OTHER_STANDARD` | `HCI_Enhanced_Accept_Synchronous_Connection_Request` |
| 29 | 5 | `OTHER_STANDARD` | `HCI_Read_Local_Supported_Codecs [v1]` |
| 29 | 6 | `OTHER_STANDARD` | `HCI_Set_MWS_Channel_Parameters` |
| 29 | 7 | `OTHER_STANDARD` | `HCI_Set_External_Frame_Configuration` |
| 30 | 0 | `OTHER_STANDARD` | `HCI_Set_MWS_Signaling` |
| 30 | 1 | `OTHER_STANDARD` | `HCI_Set_MWS_Transport_Layer` |
| 30 | 2 | `OTHER_STANDARD` | `HCI_Set_MWS_Scan_Frequency_Table` |
| 30 | 3 | `OTHER_STANDARD` | `HCI_Get_MWS_Transport_Layer_Configuration` |
| 30 | 4 | `OTHER_STANDARD` | `HCI_Set_MWS_PATTERN_Configuration` |
| 30 | 5 | `OTHER_STANDARD` | `HCI_Set_Triggered_Clock_Capture` |
| 30 | 6 | `OTHER_STANDARD` | `HCI_Truncated_Page` |
| 30 | 7 | `OTHER_STANDARD` | `HCI_Truncated_Page_Cancel` |
| 31 | 0 | `OTHER_STANDARD` | `HCI_Set_Connectionless_Peripheral_Broadcast` |
| 31 | 1 | `OTHER_STANDARD` | `HCI_Set_Connectionless_Peripheral_Broadcast_Receive` |
| 31 | 2 | `OTHER_STANDARD` | `HCI_Start_Synchronization_Train` |
| 31 | 3 | `OTHER_STANDARD` | `HCI_Receive_Synchronization_Train` |
| 31 | 4 | `OTHER_STANDARD` | `HCI_Set_Reserved_LT_ADDR` |
| 31 | 5 | `OTHER_STANDARD` | `HCI_Delete_Reserved_LT_ADDR` |
| 31 | 6 | `OTHER_STANDARD` | `HCI_Set_Connectionless_Peripheral_Broadcast_Data` |
| 31 | 7 | `OTHER_STANDARD` | `HCI_Read_Synchronization_Train_Parameters` |
| 32 | 0 | `OTHER_STANDARD` | `HCI_Write_Synchronization_Train_Parameters` |
| 32 | 1 | `OTHER_STANDARD` | `HCI_Remote_OOB_Extended_Data_Request_Reply` |
| 32 | 2 | `OTHER_STANDARD` | `HCI_Read_Secure_Connections_Host_Support` |
| 32 | 3 | `OTHER_STANDARD` | `HCI_Write_Secure_Connections_Host_Support` |
| 32 | 4 | `OTHER_STANDARD` | `HCI_Read_Authenticated_Payload_Timeout` |
| 32 | 5 | `OTHER_STANDARD` | `HCI_Write_Authenticated_Payload_Timeout` |
| 32 | 6 | `OTHER_STANDARD` | `HCI_Read_Local_OOB_Extended_Data` |
| 32 | 7 | `OTHER_STANDARD` | `HCI_Write_Secure_Connections_Test_Mode` |
| 33 | 0 | `OTHER_STANDARD` | `HCI_Read_Extended_Page_Timeout` |
| 33 | 1 | `OTHER_STANDARD` | `HCI_Write_Extended_Page_Timeout` |
| 33 | 2 | `OTHER_STANDARD` | `HCI_Read_Extended_Inquiry_Length` |
| 33 | 3 | `OTHER_STANDARD` | `HCI_Write_Extended_Inquiry_Length` |
| 33 | 4 | `OTHER_STANDARD` | `HCI_LE_Remote_Connection_Parameter_Request_Reply` |
| 33 | 5 | `OTHER_STANDARD` | `HCI_LE_Remote_Connection_Parameter_Request_Negative_Reply` |
| 33 | 6 | `OTHER_STANDARD` | `HCI_LE_Set_Data_Length` |
| 33 | 7 | `OTHER_STANDARD` | `HCI_LE_Read_Suggested_Default_Data_Length` |
| 34 | 0 | `OTHER_STANDARD` | `HCI_LE_Write_Suggested_Default_Data_Length` |
| 34 | 1 | `OTHER_STANDARD` | `HCI_LE_Read_Local_P-256_Public_Key` |
| 34 | 2 | `OTHER_STANDARD` | `HCI_LE_Generate_DHKey [v1]` |
| 34 | 3 | `OTHER_STANDARD` | `HCI_LE_Add_Device_To_Resolving_List` |
| 34 | 4 | `OTHER_STANDARD` | `HCI_LE_Remove_Device_From_Resolving_List` |
| 34 | 5 | `OTHER_STANDARD` | `HCI_LE_Clear_Resolving_List` |
| 34 | 6 | `OTHER_STANDARD` | `HCI_LE_Read_Resolving_List_Size` |
| 34 | 7 | `OTHER_STANDARD` | `HCI_LE_Read_Peer_Resolvable_Address` |
| 35 | 0 | `OTHER_STANDARD` | `HCI_LE_Read_Local_Resolvable_Address` |
| 35 | 1 | `OTHER_STANDARD` | `HCI_LE_Set_Address_Resolution_Enable` |
| 35 | 2 | `OTHER_STANDARD` | `HCI_LE_Set_Resolvable_Private_Address_Timeout [v1]` |
| 35 | 3 | `OTHER_STANDARD` | `HCI_LE_Read_Maximum_Data_Length` |
| 35 | 4 | `OTHER_STANDARD` | `HCI_LE_Read_PHY` |
| 35 | 5 | `OTHER_STANDARD` | `HCI_LE_Set_Default_PHY` |
| 35 | 6 | `OTHER_STANDARD` | `HCI_LE_Set_PHY` |
| 35 | 7 | `PHY_TEST_CORE` | `HCI_LE_Receiver_Test [v2]` |
| 36 | 0 | `PHY_TEST_CORE` | `HCI_LE_Transmitter_Test [v2]` |
| 36 | 1 | `OTHER_STANDARD` | `HCI_LE_Set_Advertising_Set_Random_Address` |
| 36 | 2 | `OTHER_STANDARD` | `HCI_LE_Set_Extended_Advertising_Parameters [v1]` |
| 36 | 3 | `OTHER_STANDARD` | `HCI_LE_Set_Extended_Advertising_Data` |
| 36 | 4 | `OTHER_STANDARD` | `HCI_LE_Set_Extended_Scan_Response_Data` |
| 36 | 5 | `OTHER_STANDARD` | `HCI_LE_Set_Extended_Advertising_Enable` |
| 36 | 6 | `OTHER_STANDARD` | `HCI_LE_Read_Maximum_Advertising_Data_Length` |
| 36 | 7 | `OTHER_STANDARD` | `HCI_LE_Read_Number_of_Supported_Advertising_Sets` |
| 37 | 0 | `OTHER_STANDARD` | `HCI_LE_Remove_Advertising_Set` |
| 37 | 1 | `OTHER_STANDARD` | `HCI_LE_Clear_Advertising_Sets` |
| 37 | 2 | `OTHER_STANDARD` | `HCI_LE_Set_Periodic_Advertising_Parameters [v1]` |
| 37 | 3 | `OTHER_STANDARD` | `HCI_LE_Set_Periodic_Advertising_Data` |
| 37 | 4 | `OTHER_STANDARD` | `HCI_LE_Set_Periodic_Advertising_Enable` |
| 37 | 5 | `OTHER_STANDARD` | `HCI_LE_Set_Extended_Scan_Parameters` |
| 37 | 6 | `OTHER_STANDARD` | `HCI_LE_Set_Extended_Scan_Enable` |
| 37 | 7 | `OTHER_STANDARD` | `HCI_LE_Extended_Create_Connection [v1]` |
| 38 | 0 | `OTHER_STANDARD` | `HCI_LE_Periodic_Advertising_Create_Sync` |
| 38 | 1 | `OTHER_STANDARD` | `HCI_LE_Periodic_Advertising_Create_Sync_Cancel` |
| 38 | 2 | `OTHER_STANDARD` | `HCI_LE_Periodic_Advertising_Terminate_Sync` |
| 38 | 3 | `OTHER_STANDARD` | `HCI_LE_Add_Device_To_Periodic_Advertiser_List` |
| 38 | 4 | `OTHER_STANDARD` | `HCI_LE_Remove_Device_From_Periodic_Advertiser_List` |
| 38 | 5 | `OTHER_STANDARD` | `HCI_LE_Clear_Periodic_Advertiser_List` |
| 38 | 6 | `OTHER_STANDARD` | `HCI_LE_Read_Periodic_Advertiser_List_Size` |
| 38 | 7 | `OTHER_STANDARD` | `HCI_LE_Read_Transmit_Power` |
| 39 | 0 | `OTHER_STANDARD` | `HCI_LE_Read_RF_Path_Compensation` |
| 39 | 1 | `OTHER_STANDARD` | `HCI_LE_Write_RF_Path_Compensation` |
| 39 | 2 | `OTHER_STANDARD` | `HCI_LE_Set_Privacy_Mode` |
| 39 | 3 | `PHY_TEST_CORE` | `HCI_LE_Receiver_Test [v3]` |
| 39 | 4 | `PHY_TEST_CORE` | `HCI_LE_Transmitter_Test [v3]` |
| 39 | 5 | `OTHER_STANDARD` | `HCI_LE_Set_Connectionless_CTE_Transmit_Parameters` |
| 39 | 6 | `OTHER_STANDARD` | `HCI_LE_Set_Connectionless_CTE_Transmit_Enable` |
| 39 | 7 | `OTHER_STANDARD` | `HCI_LE_Set_Connectionless_IQ_Sampling_Enable` |
| 40 | 0 | `OTHER_STANDARD` | `HCI_LE_Set_Connection_CTE_Receive_Parameters` |
| 40 | 1 | `OTHER_STANDARD` | `HCI_LE_Set_Connection_CTE_Transmit_Parameters` |
| 40 | 2 | `OTHER_STANDARD` | `HCI_LE_Connection_CTE_Request_Enable` |
| 40 | 3 | `OTHER_STANDARD` | `HCI_LE_Connection_CTE_Response_Enable` |
| 40 | 4 | `OTHER_STANDARD` | `HCI_LE_Read_Antenna_Information` |
| 40 | 5 | `OTHER_STANDARD` | `HCI_LE_Set_Periodic_Advertising_Receive_Enable` |
| 40 | 6 | `OTHER_STANDARD` | `HCI_LE_Periodic_Advertising_Sync_Transfer` |
| 40 | 7 | `OTHER_STANDARD` | `HCI_LE_Periodic_Advertising_Set_Info_Transfer` |
| 41 | 0 | `OTHER_STANDARD` | `HCI_LE_Set_Periodic_Advertising_Sync_Transfer_Parameters` |
| 41 | 1 | `OTHER_STANDARD` | `HCI_LE_Set_Default_Periodic_Advertising_Sync_Transfer_Parameters` |
| 41 | 2 | `OTHER_STANDARD` | `HCI_LE_Generate_DHKey [v2]` |
| 41 | 3 | `OTHER_STANDARD` | `HCI_Read_Local_Simple_Pairing_Options` |
| 41 | 4 | `OTHER_STANDARD` | `HCI_LE_Modify_Sleep_Clock_Accuracy` |
| 41 | 5 | `OTHER_STANDARD` | `HCI_LE_Read_Buffer_Size [v2]` |
| 41 | 6 | `OTHER_STANDARD` | `HCI_LE_Read_ISO_TX_Sync` |
| 41 | 7 | `OTHER_STANDARD` | `HCI_LE_Set_CIG_Parameters` |
| 42 | 0 | `OTHER_STANDARD` | `HCI_LE_Set_CIG_Parameters_Test` |
| 42 | 1 | `OTHER_STANDARD` | `HCI_LE_Create_CIS` |
| 42 | 2 | `OTHER_STANDARD` | `HCI_LE_Remove_CIG` |
| 42 | 3 | `OTHER_STANDARD` | `HCI_LE_Accept_CIS_Request` |
| 42 | 4 | `OTHER_STANDARD` | `HCI_LE_Reject_CIS_Request` |
| 42 | 5 | `OTHER_STANDARD` | `HCI_LE_Create_BIG` |
| 42 | 6 | `OTHER_STANDARD` | `HCI_LE_Create_BIG_Test` |
| 42 | 7 | `OTHER_STANDARD` | `HCI_LE_Terminate_BIG` |
| 43 | 0 | `OTHER_STANDARD` | `HCI_LE_BIG_Create_Sync` |
| 43 | 1 | `OTHER_STANDARD` | `HCI_LE_BIG_Terminate_Sync` |
| 43 | 2 | `OTHER_STANDARD` | `HCI_LE_Request_Peer_SCA` |
| 43 | 3 | `OTHER_STANDARD` | `HCI_LE_Setup_ISO_Data_Path` |
| 43 | 4 | `OTHER_STANDARD` | `HCI_LE_Remove_ISO_Data_Path` |
| 43 | 5 | `OTHER_STANDARD` | `HCI_LE_ISO_Transmit_Test` |
| 43 | 6 | `OTHER_STANDARD` | `HCI_LE_ISO_Receive_Test` |
| 43 | 7 | `OTHER_STANDARD` | `HCI_LE_ISO_Read_Test_Counters` |
| 44 | 0 | `OTHER_STANDARD` | `HCI_LE_ISO_Test_End` |
| 44 | 1 | `OTHER_STANDARD` | `HCI_LE_Set_Host_Feature [v1]` |
| 44 | 2 | `OTHER_STANDARD` | `HCI_LE_Read_ISO_Link_Quality` |
| 44 | 3 | `OTHER_STANDARD` | `HCI_LE_Enhanced_Read_Transmit_Power_Level` |
| 44 | 4 | `OTHER_STANDARD` | `HCI_LE_Read_Remote_Transmit_Power_Level` |
| 44 | 5 | `OTHER_STANDARD` | `HCI_LE_Set_Path_Loss_Reporting_Parameters` |
| 44 | 6 | `OTHER_STANDARD` | `HCI_LE_Set_Path_Loss_Reporting_Enable` |
| 44 | 7 | `OTHER_STANDARD` | `HCI_LE_Set_Transmit_Power_Reporting_Enable` |
| 45 | 0 | `PHY_TEST_CORE` | `HCI_LE_Transmitter_Test [v4]` |
| 45 | 1 | `OTHER_STANDARD` | `HCI_Set_Ecosystem_Base_Interval` |
| 45 | 2 | `OTHER_STANDARD` | `HCI_Read_Local_Supported_Codecs [v2]` |
| 45 | 3 | `OTHER_STANDARD` | `HCI_Read_Local_Supported_Codec_Capabilities` |
| 45 | 4 | `OTHER_STANDARD` | `HCI_Read_Local_Supported_Controller_Delay` |
| 45 | 5 | `OTHER_STANDARD` | `HCI_Configure_Data_Path` |
| 45 | 6 | `OTHER_STANDARD` | `HCI_LE_Set_Data_Related_Address_Changes` |
| 45 | 7 | `OTHER_STANDARD` | `HCI_Set_Min_Encryption_Key_Size` |
| 46 | 0 | `OTHER_STANDARD` | `HCI_LE_Set_Default_Subrate` |
| 46 | 1 | `OTHER_STANDARD` | `HCI_LE_Subrate_Request` |
| 46 | 2 | `OTHER_STANDARD` | `HCI_LE_Set_Extended_Advertising_Parameters [v2]` |
| 46 | 3 | `OTHER_STANDARD` | `HCI_LE_Set_Decision_Data` |
| 46 | 4 | `OTHER_STANDARD` | `HCI_LE_Set_Decision_Instructions` |
| 46 | 5 | `OTHER_STANDARD` | `HCI_LE_Set_Periodic_Advertising_Subevent_Data` |
| 46 | 6 | `OTHER_STANDARD` | `HCI_LE_Set_Periodic_Advertising_Response_Data` |
| 46 | 7 | `OTHER_STANDARD` | `HCI_LE_Set_Periodic_Sync_Subevent` |
| 47 | 0 | `OTHER_STANDARD` | `HCI_LE_Extended_Create_Connection [v2]` |
| 47 | 1 | `OTHER_STANDARD` | `HCI_LE_Set_Periodic_Advertising_Parameters [v2]` |
| 47 | 2 | `OTHER_STANDARD` | `HCI_LE_Read_All_Local_Supported_Features` |
| 47 | 3 | `OTHER_STANDARD` | `HCI_LE_Read_All_Remote_Features` |
| 47 | 4 | `OTHER_STANDARD` | `HCI_LE_Set_Host_Feature [v2]` |
| 47 | 5 | `OTHER_STANDARD` | `HCI_LE_Add_Device_To_Monitored_Advertisers_List` |
| 47 | 6 | `OTHER_STANDARD` | `HCI_LE_Remove_Device_From_Monitored_Advertisers_List` |
| 47 | 7 | `OTHER_STANDARD` | `HCI_LE_Clear_Monitored_Advertisers_List` |
| 48 | 0 | `OTHER_STANDARD` | `HCI_LE_Read_Monitored_Advertisers_List_Size` |
| 48 | 1 | `OTHER_STANDARD` | `HCI_LE_Frame_Space_Update` |
| 48 | 2 | `OTHER_STANDARD` | `HCI_LE_Set_Resolvable_Private_Address_Timeout [v2]` |
| 48 | 3 | `OTHER_STANDARD` | `HCI_LE_Enable_OTA_UTP_Mode` |
| 48 | 4 | `OTHER_STANDARD` | `HCI_LE_UTP_Send` |
| 48 | 5 | `OTHER_STANDARD` | `HCI_LE_Connection_Rate_Request` |
| 48 | 6 | `OTHER_STANDARD` | `HCI_LE_Set_Default_Rate_Parameters` |
| 48 | 7 | `OTHER_STANDARD` | `HCI_LE_Read_Minimum_Supported_Connection_Interval` |
| 49 | 0 | `CAPABILITY_QUERY` | `HCI_Read_Local_Supported_Commands [v2]` |
| 49 | 1 | `OTHER_STANDARD` | `HCI_LE_Set_Event_Mask [v2]` |
| 49 | 2 | `OTHER_STANDARD` | `HCI_LE_CS_Read_Local_Supported_Capabilities [v2]` |
| 49 | 3 | `OTHER_STANDARD` | `HCI_LE_CS_Write_Cached_Remote_Supported_Capabilities [v2]` |
| 49 | 4 | `OTHER_STANDARD` | `HCI_LE_CS_Set_Security_Requirements` |
| 49 | 5 | `OTHER_STANDARD` | `HCI_LE_CS_Set_Default_Security_Requirements` |
| 49 | 6 | `RESERVED` | Reserved for future use |
| 49 | 7 | `RESERVED` | Reserved for future use |

追加の予約範囲:

| Supported Commands octet | bit | Scope | Command / meaning |
|---:|---|---|---|
| 50-250 | 0-7 | `RESERVED` | Reserved for future use |

### 9.7 機械読み取り用CSV

```csv
octet,bit,scope,command
0,0,OTHER_STANDARD,HCI_Inquiry
0,1,OTHER_STANDARD,HCI_Inquiry_Cancel
0,2,OTHER_STANDARD,HCI_Periodic_Inquiry_Mode
0,3,OTHER_STANDARD,HCI_Exit_Periodic_Inquiry_Mode
0,4,OTHER_STANDARD,HCI_Create_Connection
0,5,OTHER_STANDARD,HCI_Disconnect
0,6,PREVIOUSLY_USED,Previously used
0,7,OTHER_STANDARD,HCI_Create_Connection_Cancel
1,0,OTHER_STANDARD,HCI_Accept_Connection_Request
1,1,OTHER_STANDARD,HCI_Reject_Connection_Request
1,2,OTHER_STANDARD,HCI_Link_Key_Request_Reply
1,3,OTHER_STANDARD,HCI_Link_Key_Request_Negative_Reply
1,4,OTHER_STANDARD,HCI_PIN_Code_Request_Reply
1,5,OTHER_STANDARD,HCI_PIN_Code_Request_Negative_Reply
1,6,OTHER_STANDARD,HCI_Change_Connection_Packet_Type
1,7,OTHER_STANDARD,HCI_Authentication_Requested
2,0,OTHER_STANDARD,HCI_Set_Connection_Encryption
2,1,OTHER_STANDARD,HCI_Change_Connection_Link_Key
2,2,OTHER_STANDARD,HCI_Link_Key_Selection
2,3,OTHER_STANDARD,HCI_Remote_Name_Request
2,4,OTHER_STANDARD,HCI_Remote_Name_Request_Cancel
2,5,OTHER_STANDARD,HCI_Read_Remote_Supported_Features
2,6,OTHER_STANDARD,HCI_Read_Remote_Extended_Features
2,7,OTHER_STANDARD,HCI_Read_Remote_Version_Information
3,0,OTHER_STANDARD,HCI_Read_Clock_Offset
3,1,OTHER_STANDARD,HCI_Read_LMP_Handle
3,2,RESERVED,Reserved for future use
3,3,RESERVED,Reserved for future use
3,4,RESERVED,Reserved for future use
3,5,RESERVED,Reserved for future use
3,6,RESERVED,Reserved for future use
3,7,RESERVED,Reserved for future use
4,0,RESERVED,Reserved for future use
4,1,OTHER_STANDARD,HCI_Hold_Mode
4,2,OTHER_STANDARD,HCI_Sniff_Mode
4,3,OTHER_STANDARD,HCI_Exit_Sniff_Mode
4,4,PREVIOUSLY_USED,Previously used
4,5,PREVIOUSLY_USED,Previously used
4,6,OTHER_STANDARD,HCI_QoS_Setup
4,7,OTHER_STANDARD,HCI_Role_Discovery
5,0,OTHER_STANDARD,HCI_Switch_Role
5,1,OTHER_STANDARD,HCI_Read_Link_Policy_Settings
5,2,OTHER_STANDARD,HCI_Write_Link_Policy_Settings
5,3,OTHER_STANDARD,HCI_Read_Default_Link_Policy_Settings
5,4,OTHER_STANDARD,HCI_Write_Default_Link_Policy_Settings
5,5,OTHER_STANDARD,HCI_Flow_Specification
5,6,OTHER_STANDARD,HCI_Set_Event_Mask
5,7,OTHER_STANDARD,HCI_Reset
6,0,OTHER_STANDARD,HCI_Set_Event_Filter
6,1,OTHER_STANDARD,HCI_Flush
6,2,OTHER_STANDARD,HCI_Read_PIN_Type
6,3,OTHER_STANDARD,HCI_Write_PIN_Type
6,4,PREVIOUSLY_USED,Previously used
6,5,OTHER_STANDARD,HCI_Read_Stored_Link_Key
6,6,OTHER_STANDARD,HCI_Write_Stored_Link_Key
6,7,OTHER_STANDARD,HCI_Delete_Stored_Link_Key
7,0,OTHER_STANDARD,HCI_Write_Local_Name
7,1,OTHER_STANDARD,HCI_Read_Local_Name
7,2,OTHER_STANDARD,HCI_Read_Connection_Accept_Timeout
7,3,OTHER_STANDARD,HCI_Write_Connection_Accept_Timeout
7,4,OTHER_STANDARD,HCI_Read_Page_Timeout
7,5,OTHER_STANDARD,HCI_Write_Page_Timeout
7,6,OTHER_STANDARD,HCI_Read_Scan_Enable
7,7,OTHER_STANDARD,HCI_Write_Scan_Enable
8,0,OTHER_STANDARD,HCI_Read_Page_Scan_Activity
8,1,OTHER_STANDARD,HCI_Write_Page_Scan_Activity
8,2,OTHER_STANDARD,HCI_Read_Inquiry_Scan_Activity
8,3,OTHER_STANDARD,HCI_Write_Inquiry_Scan_Activity
8,4,OTHER_STANDARD,HCI_Read_Authentication_Enable
8,5,OTHER_STANDARD,HCI_Write_Authentication_Enable
8,6,PREVIOUSLY_USED,Previously used
8,7,PREVIOUSLY_USED,Previously used
9,0,OTHER_STANDARD,HCI_Read_Class_Of_Device
9,1,OTHER_STANDARD,HCI_Write_Class_Of_Device
9,2,OTHER_STANDARD,HCI_Read_Voice_Setting
9,3,OTHER_STANDARD,HCI_Write_Voice_Setting
9,4,OTHER_STANDARD,HCI_Read_Automatic_Flush_Timeout
9,5,OTHER_STANDARD,HCI_Write_Automatic_Flush_Timeout
9,6,OTHER_STANDARD,HCI_Read_Num_Broadcast_Retransmissions
9,7,OTHER_STANDARD,HCI_Write_Num_Broadcast_Retransmissions
10,0,OTHER_STANDARD,HCI_Read_Hold_Mode_Activity
10,1,OTHER_STANDARD,HCI_Write_Hold_Mode_Activity
10,2,OTHER_STANDARD,HCI_Read_Transmit_Power_Level
10,3,OTHER_STANDARD,HCI_Read_Synchronous_Flow_Control_Enable
10,4,OTHER_STANDARD,HCI_Write_Synchronous_Flow_Control_Enable
10,5,OTHER_STANDARD,HCI_Set_Controller_To_Host_Flow_Control
10,6,OTHER_STANDARD,HCI_Host_Buffer_Size
10,7,OTHER_STANDARD,HCI_Host_Number_Of_Completed_Packets
11,0,OTHER_STANDARD,HCI_Read_Link_Supervision_Timeout
11,1,OTHER_STANDARD,HCI_Write_Link_Supervision_Timeout
11,2,OTHER_STANDARD,HCI_Read_Number_Of_Supported_IAC
11,3,OTHER_STANDARD,HCI_Read_Current_IAC_LAP
11,4,OTHER_STANDARD,HCI_Write_Current_IAC_LAP
11,5,PREVIOUSLY_USED,Previously used
11,6,PREVIOUSLY_USED,Previously used
11,7,PREVIOUSLY_USED,Previously used
12,0,PREVIOUSLY_USED,Previously used
12,1,OTHER_STANDARD,HCI_Set_AFH_Host_Channel_Classification
12,2,OTHER_STANDARD,HCI_LE_CS_Read_Remote_FAE_Table
12,3,OTHER_STANDARD,HCI_LE_CS_Write_Cached_Remote_FAE_Table
12,4,OTHER_STANDARD,HCI_Read_Inquiry_Scan_Type
12,5,OTHER_STANDARD,HCI_Write_Inquiry_Scan_Type
12,6,OTHER_STANDARD,HCI_Read_Inquiry_Mode
12,7,OTHER_STANDARD,HCI_Write_Inquiry_Mode
13,0,OTHER_STANDARD,HCI_Read_Page_Scan_Type
13,1,OTHER_STANDARD,HCI_Write_Page_Scan_Type
13,2,OTHER_STANDARD,HCI_Read_AFH_Channel_Assessment_Mode
13,3,OTHER_STANDARD,HCI_Write_AFH_Channel_Assessment_Mode
13,4,RESERVED,Reserved for future use
13,5,RESERVED,Reserved for future use
13,6,RESERVED,Reserved for future use
13,7,RESERVED,Reserved for future use
14,0,RESERVED,Reserved for future use
14,1,RESERVED,Reserved for future use
14,2,RESERVED,Reserved for future use
14,3,OTHER_STANDARD,HCI_Read_Local_Version_Information
14,4,RESERVED,Reserved for future use
14,5,OTHER_STANDARD,HCI_Read_Local_Supported_Features
14,6,OTHER_STANDARD,HCI_Read_Local_Extended_Features
14,7,OTHER_STANDARD,HCI_Read_Buffer_Size
15,0,PREVIOUSLY_USED,Previously used
15,1,OTHER_STANDARD,HCI_Read_BD_ADDR
15,2,OTHER_STANDARD,HCI_Read_Failed_Contact_Counter
15,3,OTHER_STANDARD,HCI_Reset_Failed_Contact_Counter
15,4,OTHER_STANDARD,HCI_Read_Link_Quality
15,5,OTHER_STANDARD,HCI_Read_RSSI
15,6,OTHER_STANDARD,HCI_Read_AFH_Channel_Map
15,7,OTHER_STANDARD,HCI_Read_Clock
16,0,OTHER_STANDARD,HCI_Read_Loopback_Mode
16,1,OTHER_STANDARD,HCI_Write_Loopback_Mode
16,2,OTHER_STANDARD,HCI_Enable_Implementation_Under_Test_Mode
16,3,OTHER_STANDARD,HCI_Setup_Synchronous_Connection
16,4,OTHER_STANDARD,HCI_Accept_Synchronous_Connection_Request
16,5,OTHER_STANDARD,HCI_Reject_Synchronous_Connection_Request
16,6,OTHER_STANDARD,HCI_LE_CS_Create_Config
16,7,OTHER_STANDARD,HCI_LE_CS_Remove_Config
17,0,OTHER_STANDARD,HCI_Read_Extended_Inquiry_Response
17,1,OTHER_STANDARD,HCI_Write_Extended_Inquiry_Response
17,2,OTHER_STANDARD,HCI_Refresh_Encryption_Key
17,3,RESERVED,Reserved for future use
17,4,OTHER_STANDARD,HCI_Sniff_Subrating
17,5,OTHER_STANDARD,HCI_Read_Simple_Pairing_Mode
17,6,OTHER_STANDARD,HCI_Write_Simple_Pairing_Mode
17,7,OTHER_STANDARD,HCI_Read_Local_OOB_Data
18,0,OTHER_STANDARD,HCI_Read_Inquiry_Response_Transmit_Power_Level
18,1,OTHER_STANDARD,HCI_Write_Inquiry_Transmit_Power_Level
18,2,OTHER_STANDARD,HCI_Read_Default_Erroneous_Data_Reporting
18,3,OTHER_STANDARD,HCI_Write_Default_Erroneous_Data_Reporting
18,4,RESERVED,Reserved for future use
18,5,RESERVED,Reserved for future use
18,6,RESERVED,Reserved for future use
18,7,OTHER_STANDARD,HCI_IO_Capability_Request_Reply
19,0,OTHER_STANDARD,HCI_User_Confirmation_Request_Reply
19,1,OTHER_STANDARD,HCI_User_Confirmation_Request_Negative_Reply
19,2,OTHER_STANDARD,HCI_User_Passkey_Request_Reply
19,3,OTHER_STANDARD,HCI_User_Passkey_Request_Negative_Reply
19,4,OTHER_STANDARD,HCI_Remote_OOB_Data_Request_Reply
19,5,OTHER_STANDARD,HCI_Write_Simple_Pairing_Debug_Mode
19,6,OTHER_STANDARD,HCI_Enhanced_Flush
19,7,OTHER_STANDARD,HCI_Remote_OOB_Data_Request_Negative_Reply
20,0,RESERVED,Reserved for future use
20,1,RESERVED,Reserved for future use
20,2,OTHER_STANDARD,HCI_Send_Keypress_Notification
20,3,OTHER_STANDARD,HCI_IO_Capability_Request_Negative_Reply
20,4,OTHER_STANDARD,HCI_Read_Encryption_Key_Size
20,5,OTHER_STANDARD,HCI_LE_CS_Read_Local_Supported_Capabilities [v1]
20,6,OTHER_STANDARD,HCI_LE_CS_Read_Remote_Supported_Capabilities
20,7,OTHER_STANDARD,HCI_LE_CS_Write_Cached_Remote_Supported_Capabilities [v1]
21,0,PREVIOUSLY_USED,Previously used
21,1,PREVIOUSLY_USED,Previously used
21,2,PREVIOUSLY_USED,Previously used
21,3,PREVIOUSLY_USED,Previously used
21,4,PREVIOUSLY_USED,Previously used
21,5,PREVIOUSLY_USED,Previously used
21,6,PREVIOUSLY_USED,Previously used
21,7,PREVIOUSLY_USED,Previously used
22,0,PREVIOUSLY_USED,Previously used
22,1,PREVIOUSLY_USED,Previously used
22,2,OTHER_STANDARD,HCI_Set_Event_Mask_Page_2
22,3,PREVIOUSLY_USED,Previously used
22,4,PREVIOUSLY_USED,Previously used
22,5,PREVIOUSLY_USED,Previously used
22,6,PREVIOUSLY_USED,Previously used
22,7,PREVIOUSLY_USED,Previously used
23,0,OTHER_STANDARD,HCI_Read_Flow_Control_Mode
23,1,OTHER_STANDARD,HCI_Write_Flow_Control_Mode
23,2,OTHER_STANDARD,HCI_Read_Data_Block_Size
23,3,PHY_TEST_CS,HCI_LE_CS_Test
23,4,PHY_TEST_CS,HCI_LE_CS_Test_End
23,5,PREVIOUSLY_USED,Previously used
23,6,PREVIOUSLY_USED,Previously used
23,7,PREVIOUSLY_USED,Previously used
24,0,OTHER_STANDARD,HCI_Read_Enhanced_Transmit_Power_Level
24,1,OTHER_STANDARD,HCI_LE_CS_Security_Enable
24,2,PREVIOUSLY_USED,Previously used
24,3,PREVIOUSLY_USED,Previously used
24,4,PREVIOUSLY_USED,Previously used
24,5,OTHER_STANDARD,HCI_Read_LE_Host_Support
24,6,OTHER_STANDARD,HCI_Write_LE_Host_Support
24,7,OTHER_STANDARD,HCI_LE_CS_Set_Default_Settings
25,0,OTHER_STANDARD,HCI_LE_Set_Event_Mask [v1]
25,1,OTHER_STANDARD,HCI_LE_Read_Buffer_Size [v1]
25,2,OTHER_STANDARD,HCI_LE_Read_Local_Supported_Features_Page_0
25,3,RESERVED,Reserved for future use
25,4,OTHER_STANDARD,HCI_LE_Set_Random_Address
25,5,OTHER_STANDARD,HCI_LE_Set_Advertising_Parameters
25,6,OTHER_STANDARD,HCI_LE_Read_Advertising_Physical_Channel_Tx_Power
25,7,OTHER_STANDARD,HCI_LE_Set_Advertising_Data
26,0,OTHER_STANDARD,HCI_LE_Set_Scan_Response_Data
26,1,OTHER_STANDARD,HCI_LE_Set_Advertising_Enable
26,2,OTHER_STANDARD,HCI_LE_Set_Scan_Parameters
26,3,OTHER_STANDARD,HCI_LE_Set_Scan_Enable
26,4,OTHER_STANDARD,HCI_LE_Create_Connection
26,5,OTHER_STANDARD,HCI_LE_Create_Connection_Cancel
26,6,OTHER_STANDARD,HCI_LE_Read_Filter_Accept_List_Size
26,7,OTHER_STANDARD,HCI_LE_Clear_Filter_Accept_List
27,0,OTHER_STANDARD,HCI_LE_Add_Device_To_Filter_Accept_List
27,1,OTHER_STANDARD,HCI_LE_Remove_Device_From_Filter_Accept_List
27,2,OTHER_STANDARD,HCI_LE_Connection_Update
27,3,OTHER_STANDARD,HCI_LE_Set_Host_Channel_Classification
27,4,OTHER_STANDARD,HCI_LE_Read_Channel_Map
27,5,OTHER_STANDARD,HCI_LE_Read_Remote_Features_Page_0
27,6,OTHER_STANDARD,HCI_LE_Encrypt
27,7,OTHER_STANDARD,HCI_LE_Rand
28,0,OTHER_STANDARD,HCI_LE_Enable_Encryption
28,1,OTHER_STANDARD,HCI_LE_Long_Term_Key_Request_Reply
28,2,OTHER_STANDARD,HCI_LE_Long_Term_Key_Request_Negative_Reply
28,3,OTHER_STANDARD,HCI_LE_Read_Supported_States
28,4,PHY_TEST_CORE,HCI_LE_Receiver_Test [v1]
28,5,PHY_TEST_CORE,HCI_LE_Transmitter_Test [v1]
28,6,PHY_TEST_CORE,HCI_LE_Test_End
28,7,OTHER_STANDARD,HCI_LE_Enable_Monitoring_Advertisers
29,0,OTHER_STANDARD,HCI_LE_CS_Set_Channel_Classification
29,1,OTHER_STANDARD,HCI_LE_CS_Set_Procedure_Parameters
29,2,OTHER_STANDARD,HCI_LE_CS_Procedure_Enable
29,3,OTHER_STANDARD,HCI_Enhanced_Setup_Synchronous_Connection
29,4,OTHER_STANDARD,HCI_Enhanced_Accept_Synchronous_Connection_Request
29,5,OTHER_STANDARD,HCI_Read_Local_Supported_Codecs [v1]
29,6,OTHER_STANDARD,HCI_Set_MWS_Channel_Parameters
29,7,OTHER_STANDARD,HCI_Set_External_Frame_Configuration
30,0,OTHER_STANDARD,HCI_Set_MWS_Signaling
30,1,OTHER_STANDARD,HCI_Set_MWS_Transport_Layer
30,2,OTHER_STANDARD,HCI_Set_MWS_Scan_Frequency_Table
30,3,OTHER_STANDARD,HCI_Get_MWS_Transport_Layer_Configuration
30,4,OTHER_STANDARD,HCI_Set_MWS_PATTERN_Configuration
30,5,OTHER_STANDARD,HCI_Set_Triggered_Clock_Capture
30,6,OTHER_STANDARD,HCI_Truncated_Page
30,7,OTHER_STANDARD,HCI_Truncated_Page_Cancel
31,0,OTHER_STANDARD,HCI_Set_Connectionless_Peripheral_Broadcast
31,1,OTHER_STANDARD,HCI_Set_Connectionless_Peripheral_Broadcast_Receive
31,2,OTHER_STANDARD,HCI_Start_Synchronization_Train
31,3,OTHER_STANDARD,HCI_Receive_Synchronization_Train
31,4,OTHER_STANDARD,HCI_Set_Reserved_LT_ADDR
31,5,OTHER_STANDARD,HCI_Delete_Reserved_LT_ADDR
31,6,OTHER_STANDARD,HCI_Set_Connectionless_Peripheral_Broadcast_Data
31,7,OTHER_STANDARD,HCI_Read_Synchronization_Train_Parameters
32,0,OTHER_STANDARD,HCI_Write_Synchronization_Train_Parameters
32,1,OTHER_STANDARD,HCI_Remote_OOB_Extended_Data_Request_Reply
32,2,OTHER_STANDARD,HCI_Read_Secure_Connections_Host_Support
32,3,OTHER_STANDARD,HCI_Write_Secure_Connections_Host_Support
32,4,OTHER_STANDARD,HCI_Read_Authenticated_Payload_Timeout
32,5,OTHER_STANDARD,HCI_Write_Authenticated_Payload_Timeout
32,6,OTHER_STANDARD,HCI_Read_Local_OOB_Extended_Data
32,7,OTHER_STANDARD,HCI_Write_Secure_Connections_Test_Mode
33,0,OTHER_STANDARD,HCI_Read_Extended_Page_Timeout
33,1,OTHER_STANDARD,HCI_Write_Extended_Page_Timeout
33,2,OTHER_STANDARD,HCI_Read_Extended_Inquiry_Length
33,3,OTHER_STANDARD,HCI_Write_Extended_Inquiry_Length
33,4,OTHER_STANDARD,HCI_LE_Remote_Connection_Parameter_Request_Reply
33,5,OTHER_STANDARD,HCI_LE_Remote_Connection_Parameter_Request_Negative_Reply
33,6,OTHER_STANDARD,HCI_LE_Set_Data_Length
33,7,OTHER_STANDARD,HCI_LE_Read_Suggested_Default_Data_Length
34,0,OTHER_STANDARD,HCI_LE_Write_Suggested_Default_Data_Length
34,1,OTHER_STANDARD,HCI_LE_Read_Local_P-256_Public_Key
34,2,OTHER_STANDARD,HCI_LE_Generate_DHKey [v1]
34,3,OTHER_STANDARD,HCI_LE_Add_Device_To_Resolving_List
34,4,OTHER_STANDARD,HCI_LE_Remove_Device_From_Resolving_List
34,5,OTHER_STANDARD,HCI_LE_Clear_Resolving_List
34,6,OTHER_STANDARD,HCI_LE_Read_Resolving_List_Size
34,7,OTHER_STANDARD,HCI_LE_Read_Peer_Resolvable_Address
35,0,OTHER_STANDARD,HCI_LE_Read_Local_Resolvable_Address
35,1,OTHER_STANDARD,HCI_LE_Set_Address_Resolution_Enable
35,2,OTHER_STANDARD,HCI_LE_Set_Resolvable_Private_Address_Timeout [v1]
35,3,OTHER_STANDARD,HCI_LE_Read_Maximum_Data_Length
35,4,OTHER_STANDARD,HCI_LE_Read_PHY
35,5,OTHER_STANDARD,HCI_LE_Set_Default_PHY
35,6,OTHER_STANDARD,HCI_LE_Set_PHY
35,7,PHY_TEST_CORE,HCI_LE_Receiver_Test [v2]
36,0,PHY_TEST_CORE,HCI_LE_Transmitter_Test [v2]
36,1,OTHER_STANDARD,HCI_LE_Set_Advertising_Set_Random_Address
36,2,OTHER_STANDARD,HCI_LE_Set_Extended_Advertising_Parameters [v1]
36,3,OTHER_STANDARD,HCI_LE_Set_Extended_Advertising_Data
36,4,OTHER_STANDARD,HCI_LE_Set_Extended_Scan_Response_Data
36,5,OTHER_STANDARD,HCI_LE_Set_Extended_Advertising_Enable
36,6,OTHER_STANDARD,HCI_LE_Read_Maximum_Advertising_Data_Length
36,7,OTHER_STANDARD,HCI_LE_Read_Number_of_Supported_Advertising_Sets
37,0,OTHER_STANDARD,HCI_LE_Remove_Advertising_Set
37,1,OTHER_STANDARD,HCI_LE_Clear_Advertising_Sets
37,2,OTHER_STANDARD,HCI_LE_Set_Periodic_Advertising_Parameters [v1]
37,3,OTHER_STANDARD,HCI_LE_Set_Periodic_Advertising_Data
37,4,OTHER_STANDARD,HCI_LE_Set_Periodic_Advertising_Enable
37,5,OTHER_STANDARD,HCI_LE_Set_Extended_Scan_Parameters
37,6,OTHER_STANDARD,HCI_LE_Set_Extended_Scan_Enable
37,7,OTHER_STANDARD,HCI_LE_Extended_Create_Connection [v1]
38,0,OTHER_STANDARD,HCI_LE_Periodic_Advertising_Create_Sync
38,1,OTHER_STANDARD,HCI_LE_Periodic_Advertising_Create_Sync_Cancel
38,2,OTHER_STANDARD,HCI_LE_Periodic_Advertising_Terminate_Sync
38,3,OTHER_STANDARD,HCI_LE_Add_Device_To_Periodic_Advertiser_List
38,4,OTHER_STANDARD,HCI_LE_Remove_Device_From_Periodic_Advertiser_List
38,5,OTHER_STANDARD,HCI_LE_Clear_Periodic_Advertiser_List
38,6,OTHER_STANDARD,HCI_LE_Read_Periodic_Advertiser_List_Size
38,7,OTHER_STANDARD,HCI_LE_Read_Transmit_Power
39,0,OTHER_STANDARD,HCI_LE_Read_RF_Path_Compensation
39,1,OTHER_STANDARD,HCI_LE_Write_RF_Path_Compensation
39,2,OTHER_STANDARD,HCI_LE_Set_Privacy_Mode
39,3,PHY_TEST_CORE,HCI_LE_Receiver_Test [v3]
39,4,PHY_TEST_CORE,HCI_LE_Transmitter_Test [v3]
39,5,OTHER_STANDARD,HCI_LE_Set_Connectionless_CTE_Transmit_Parameters
39,6,OTHER_STANDARD,HCI_LE_Set_Connectionless_CTE_Transmit_Enable
39,7,OTHER_STANDARD,HCI_LE_Set_Connectionless_IQ_Sampling_Enable
40,0,OTHER_STANDARD,HCI_LE_Set_Connection_CTE_Receive_Parameters
40,1,OTHER_STANDARD,HCI_LE_Set_Connection_CTE_Transmit_Parameters
40,2,OTHER_STANDARD,HCI_LE_Connection_CTE_Request_Enable
40,3,OTHER_STANDARD,HCI_LE_Connection_CTE_Response_Enable
40,4,OTHER_STANDARD,HCI_LE_Read_Antenna_Information
40,5,OTHER_STANDARD,HCI_LE_Set_Periodic_Advertising_Receive_Enable
40,6,OTHER_STANDARD,HCI_LE_Periodic_Advertising_Sync_Transfer
40,7,OTHER_STANDARD,HCI_LE_Periodic_Advertising_Set_Info_Transfer
41,0,OTHER_STANDARD,HCI_LE_Set_Periodic_Advertising_Sync_Transfer_Parameters
41,1,OTHER_STANDARD,HCI_LE_Set_Default_Periodic_Advertising_Sync_Transfer_Parameters
41,2,OTHER_STANDARD,HCI_LE_Generate_DHKey [v2]
41,3,OTHER_STANDARD,HCI_Read_Local_Simple_Pairing_Options
41,4,OTHER_STANDARD,HCI_LE_Modify_Sleep_Clock_Accuracy
41,5,OTHER_STANDARD,HCI_LE_Read_Buffer_Size [v2]
41,6,OTHER_STANDARD,HCI_LE_Read_ISO_TX_Sync
41,7,OTHER_STANDARD,HCI_LE_Set_CIG_Parameters
42,0,OTHER_STANDARD,HCI_LE_Set_CIG_Parameters_Test
42,1,OTHER_STANDARD,HCI_LE_Create_CIS
42,2,OTHER_STANDARD,HCI_LE_Remove_CIG
42,3,OTHER_STANDARD,HCI_LE_Accept_CIS_Request
42,4,OTHER_STANDARD,HCI_LE_Reject_CIS_Request
42,5,OTHER_STANDARD,HCI_LE_Create_BIG
42,6,OTHER_STANDARD,HCI_LE_Create_BIG_Test
42,7,OTHER_STANDARD,HCI_LE_Terminate_BIG
43,0,OTHER_STANDARD,HCI_LE_BIG_Create_Sync
43,1,OTHER_STANDARD,HCI_LE_BIG_Terminate_Sync
43,2,OTHER_STANDARD,HCI_LE_Request_Peer_SCA
43,3,OTHER_STANDARD,HCI_LE_Setup_ISO_Data_Path
43,4,OTHER_STANDARD,HCI_LE_Remove_ISO_Data_Path
43,5,OTHER_STANDARD,HCI_LE_ISO_Transmit_Test
43,6,OTHER_STANDARD,HCI_LE_ISO_Receive_Test
43,7,OTHER_STANDARD,HCI_LE_ISO_Read_Test_Counters
44,0,OTHER_STANDARD,HCI_LE_ISO_Test_End
44,1,OTHER_STANDARD,HCI_LE_Set_Host_Feature [v1]
44,2,OTHER_STANDARD,HCI_LE_Read_ISO_Link_Quality
44,3,OTHER_STANDARD,HCI_LE_Enhanced_Read_Transmit_Power_Level
44,4,OTHER_STANDARD,HCI_LE_Read_Remote_Transmit_Power_Level
44,5,OTHER_STANDARD,HCI_LE_Set_Path_Loss_Reporting_Parameters
44,6,OTHER_STANDARD,HCI_LE_Set_Path_Loss_Reporting_Enable
44,7,OTHER_STANDARD,HCI_LE_Set_Transmit_Power_Reporting_Enable
45,0,PHY_TEST_CORE,HCI_LE_Transmitter_Test [v4]
45,1,OTHER_STANDARD,HCI_Set_Ecosystem_Base_Interval
45,2,OTHER_STANDARD,HCI_Read_Local_Supported_Codecs [v2]
45,3,OTHER_STANDARD,HCI_Read_Local_Supported_Codec_Capabilities
45,4,OTHER_STANDARD,HCI_Read_Local_Supported_Controller_Delay
45,5,OTHER_STANDARD,HCI_Configure_Data_Path
45,6,OTHER_STANDARD,HCI_LE_Set_Data_Related_Address_Changes
45,7,OTHER_STANDARD,HCI_Set_Min_Encryption_Key_Size
46,0,OTHER_STANDARD,HCI_LE_Set_Default_Subrate
46,1,OTHER_STANDARD,HCI_LE_Subrate_Request
46,2,OTHER_STANDARD,HCI_LE_Set_Extended_Advertising_Parameters [v2]
46,3,OTHER_STANDARD,HCI_LE_Set_Decision_Data
46,4,OTHER_STANDARD,HCI_LE_Set_Decision_Instructions
46,5,OTHER_STANDARD,HCI_LE_Set_Periodic_Advertising_Subevent_Data
46,6,OTHER_STANDARD,HCI_LE_Set_Periodic_Advertising_Response_Data
46,7,OTHER_STANDARD,HCI_LE_Set_Periodic_Sync_Subevent
47,0,OTHER_STANDARD,HCI_LE_Extended_Create_Connection [v2]
47,1,OTHER_STANDARD,HCI_LE_Set_Periodic_Advertising_Parameters [v2]
47,2,OTHER_STANDARD,HCI_LE_Read_All_Local_Supported_Features
47,3,OTHER_STANDARD,HCI_LE_Read_All_Remote_Features
47,4,OTHER_STANDARD,HCI_LE_Set_Host_Feature [v2]
47,5,OTHER_STANDARD,HCI_LE_Add_Device_To_Monitored_Advertisers_List
47,6,OTHER_STANDARD,HCI_LE_Remove_Device_From_Monitored_Advertisers_List
47,7,OTHER_STANDARD,HCI_LE_Clear_Monitored_Advertisers_List
48,0,OTHER_STANDARD,HCI_LE_Read_Monitored_Advertisers_List_Size
48,1,OTHER_STANDARD,HCI_LE_Frame_Space_Update
48,2,OTHER_STANDARD,HCI_LE_Set_Resolvable_Private_Address_Timeout [v2]
48,3,OTHER_STANDARD,HCI_LE_Enable_OTA_UTP_Mode
48,4,OTHER_STANDARD,HCI_LE_UTP_Send
48,5,OTHER_STANDARD,HCI_LE_Connection_Rate_Request
48,6,OTHER_STANDARD,HCI_LE_Set_Default_Rate_Parameters
48,7,OTHER_STANDARD,HCI_LE_Read_Minimum_Supported_Connection_Interval
49,0,CAPABILITY_QUERY,HCI_Read_Local_Supported_Commands [v2]
49,1,OTHER_STANDARD,HCI_LE_Set_Event_Mask [v2]
49,2,OTHER_STANDARD,HCI_LE_CS_Read_Local_Supported_Capabilities [v2]
49,3,OTHER_STANDARD,HCI_LE_CS_Write_Cached_Remote_Supported_Capabilities [v2]
49,4,OTHER_STANDARD,HCI_LE_CS_Set_Security_Requirements
49,5,OTHER_STANDARD,HCI_LE_CS_Set_Default_Security_Requirements
49,6,RESERVED,Reserved for future use
49,7,RESERVED,Reserved for future use
50-250,0-7,RESERVED,Reserved for future use
```

### 9.8 GUIでの判定例

```python
PHY_TEST_SCOPES = {"PHY_TEST_CORE", "PHY_TEST_CS"}

SUPPORTED_COMMANDS_MAP = {
    # Full mapping is represented by the CSV table above.
    # Example:
    (28, 4): {"scope": "PHY_TEST_CORE", "command": "HCI_LE_Receiver_Test [v1]"},
    (28, 5): {"scope": "PHY_TEST_CORE", "command": "HCI_LE_Transmitter_Test [v1]"},
    (28, 6): {"scope": "PHY_TEST_CORE", "command": "HCI_LE_Test_End"},
    (23, 3): {"scope": "PHY_TEST_CS", "command": "HCI_LE_CS_Test"},
    (23, 4): {"scope": "PHY_TEST_CS", "command": "HCI_LE_CS_Test_End"},
    (49, 0): {"scope": "CAPABILITY_QUERY", "command": "HCI_Read_Local_Supported_Commands [v2]"},
}

def is_supported(supported_commands: bytes, octet: int, bit: int) -> bool:
    if octet >= len(supported_commands):
        return False
    return bool(supported_commands[octet] & (1 << bit))

def classify_supported_command(supported_commands: bytes, octet: int, bit: int, mapping: dict) -> dict:
    entry = mapping.get((octet, bit), {
        "scope": "RESERVED" if octet >= 50 else "OTHER_STANDARD",
        "command": "Unknown or reserved"
    })
    return {
        "octet": octet,
        "bit": bit,
        "supported": is_supported(supported_commands, octet, bit),
        "scope": entry["scope"],
        "is_phy_test_command": entry["scope"] in PHY_TEST_SCOPES,
        "command": entry["command"],
    }
```

### 9.9 推奨シーケンス

```text
1. HCI_Read_Local_Supported_Commands [v1] を送る
2. Status が Success であることを確認する
3. Supported_Commands octet 49 bit 0 が 1 なら、HCI_Read_Local_Supported_Commands [v2] を送る
4. v2応答が取れた場合は、251 octets版のbitmaskを以後の真値として使う
5. GUIや送信ツールでは、bitmaskに基づき未対応コマンドをdisableまたは警告表示し、Scopeに基づきコマンドの表示分類を分ける
   - PHY_TEST_CORE / PHY_TEST_CS: PHY試験用コマンドとして表示
   - CAPABILITY_QUERY: capability queryとして表示
   - OTHER_STANDARD: その他の標準HCIコマンドとして表示
   - RESERVED / PREVIOUSLY_USED: 通常は非表示または参考表示
```

### 9.10 implementation specific な事項

`HCI_Read_Local_Supported_Commands` は標準HCIコマンドの対応状況を示す。Vendor Specific HCI command の個別対応、ベンダー独自test mode entry、未公開HDT暫定opcodeなどは、このbitmaskからは判別できない。

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
| Controller初期化 | `HCI_Reset`, `HCI_Read_Local_Version_Information` | `HCI_Reset` は本資料で標準補助コマンドとして定義。その他はテスター/ドライバ依存 |
| Capability確認 | `HCI_Read_Local_Supported_Commands`, `HCI_LE_Read_Local_Supported_Features_Page_0` | `HCI_Read_Local_Supported_Commands` は本資料で標準補助コマンドとして定義。その他は必要に応じて追加 |
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
| `01 02 10 00` | `0x1002` | `HCI_Read_Local_Supported_Commands [v1]` | `0` |
| `01 10 10 00` | `0x1010` | `HCI_Read_Local_Supported_Commands [v2]` | `0` |
| `01 03 0C 00` | `0x0C03` | `HCI_Reset` | `0` |
