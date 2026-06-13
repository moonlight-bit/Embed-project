# SO-ARM101 机械臂 — 完整控制指南

> **角色定位**: 专业机械臂控制师视角 — 从机械结构到编程落地的完整路线图
> **适用对象**: 芯伴 X1 (SC171 主控 + SO-ARM101 执行臂)
> **前置阅读**: `SO-ARM101_技术调研与连接检测报告.md` (硬件摸底)

---

## 目录

1. [你现在需要做什么](#一你现在需要做什么)
2. [机械结构与电机接口](#二机械结构与电机接口)
3. [控制原理](#三控制原理)
4. [需要下载的资料清单](#四需要下载的资料清单)
5. [编程方法: 从底层到高层](#五编程方法-从底层到高层)
6. [如何操作: 从零到运动](#六如何操作-从零到运动)
7. [组合动作编程: 拾取/拼装/写字](#七组合动作编程-拾取拼装写字)
8. [语音播报 + 音乐播放集成](#八语音播报--音乐播放集成)
9. [安全体系: 不失控不损坏](#九安全体系-不失控不损坏)
10. [芯伴 X1 综合控制框架](#十芯伴-x1-综合控制框架)

---

## 一、你现在需要做什么

### 1.1 第一优先级: 硬件连接 + 基础通信验证

```
Step 1: 机械臂驱动板 USB-C → SC171 USB 口 (物理连接)
Step 2: ls /dev/ttyACM* /dev/ttyUSB*  (确认设备出现)
Step 3: sudo chmod 666 /dev/ttyACM0    (授权)
Step 4: Python ping 舵机 → 确认12个舵机全部在线
Step 5: 标定零位 → 记录每个关节的 homing_offset
```

### 1.2 第二优先级: 安全原语

```
arm_reset()   → 机械臂回到安全初始姿态 (所有关节扭矩卸载后重新上电并归位)
arm_stop()    → 紧急停止 (立即扭矩卸载, 无减速)
```

这两个原语是整个系统安全的基石, **必须在任何复杂动作之前实现并通过测试**。

### 1.3 第三优先级: Arm Bridge 架构落地

SC171 的 Python 3.8 **不能**直接跑 LeRobot (要求 ≥3.10)。按照方案文档的设计:

```
SC171 (Python 3.8)                 独立环境 (Python 3.10+)
┌──────────────────┐    HTTP     ┌──────────────────────────┐
│  LLM Agent       │ ──────────→ │  Arm Bridge (FastAPI)     │
│  Tool Calling    │ ←────────── │  /arm/status              │
│  TTS / 记忆      │    JSON     │  /arm/reset               │
│  安全验证层       │             │  /arm/execute             │
└──────────────────┘             │  LeRobot + pyserial       │
                                 │  → /dev/ttyACM0           │
                                 └──────────────────────────┘
```

### 1.4 后续路线图

```
M0 (当前)  → 硬件摸底, 串口通信, 舵机 PING
M1        → Arm Bridge 基础 API, arm_reset/arm_stop
M2        → 关节空间点对点控制, 标定完成
M3        → LeRobot 遥操作数据采集
M4        → 组合动作 (拾取放置)
M5        → 模仿学习策略部署
M6        → 语音+音乐集成, 完整任务演示
M7        → 儿童场景安全验证, 产品化
```

---

## 二、机械结构与电机接口

### 2.1 整体架构: Leader-Follower 双主从臂

SO-ARM101 由两套独立的 6 轴机械臂组成:

```
┌──────────────────────────┐    ┌──────────────────────────┐
│  LEADER ARM (主臂/示教臂) │    │  FOLLOWER ARM (从臂/执行臂)│
│  人手拖动 → 记录轨迹      │    │  自主执行 → 复现动作       │
│  舵机 ID: 7-12            │    │  舵机 ID: 1-6             │
│  轻量化齿轮 (易拖动)       │    │  高扭矩齿轮 (大力输出)     │
└──────────────────────────┘    └──────────────────────────┘
```

**芯伴 X1 实际只需要 Follower Arm (ID 1-6)** 来执行动作。Leader Arm 在数据采集时使用。

### 2.2 六关节运动链 (Follower Arm)

```
          J1 (垂直旋转)
      ┌──────┘
      │  底座转台
      │
      ├── J2 (水平俯仰, 肩部)
      │   └── 上臂连杆 (~130mm)
      │       └── J3 (水平俯仰, 肘部)
      │           └── 前臂连杆 (~120mm)
      │               └── J4 (前臂方向俯仰)
      │                   └── J5 (手腕旋转, 360°)
      │                       └── J6 (夹爪开合)
      │                           └── 平行夹爪 (~50mm)
      │
      └── 底座固定
```

| 关节 | 名称 | 舵机 ID | 运动范围 (度) |
|------|------|---------|---------------|
| J1 | shoulder_pan (底座旋转) | 1 | **±135°** |
| J2 | shoulder_lift (肩部俯仰) | 2 | **约 -45° ~ +90°** |
| J3 | elbow_flex (肘部俯仰) | 3 | **约 -120° ~ +30°** |
| J4 | wrist_flex (腕部俯仰) | 4 | **约 -90° ~ +90°** |
| J5 | wrist_roll (腕部旋转) | 5 | **360° 连续旋转** |
| J6 | gripper (夹爪开合) | 6 | **约 0 ~ 70° (开合行程)** |

**臂展**: 完全伸展约 **280mm**, 最大负载约 **200g** (标准) / **500g+** (Pro 版 12V 供电)

### 2.3 STS3215 总线舵机 — 核心执行单元

每个关节由一颗 **STS3215 串行总线舵机** (Feetech/飞特出品) 驱动。

| 参数 | 值 |
|------|-----|
| 编码器 | **12 位磁编码器** = 4096 步/360°, 分辨率 **0.088°/步** |
| 齿轮 | **全金属铜齿轮**, 减速比 1:345 (标准) / 1:191 / 1:147 (轻量) |
| 扭矩 | **19.5 kg·cm** @7.4V (标准) / **30 kg·cm** @12V (Pro) |
| 转速 | **52 RPM** (空载 @7.4V), 约 **312°/s** |
| 电压 | 4V ~ 7.4V (标准) / 4V ~ 14V (Pro 款 C047) |
| 通信 | **TTL 半双工串行总线**, 默认 1 Mbps, 单线可挂 253 个舵机 |
| 尺寸重量 | 45.2 × 24.7 × 35mm, **55g** |
| PID 控制 | 开放参数, 寄存器 21(P)/22(D)/23(I), 默认 P=32 |

### 2.4 舵机总线物理拓扑

```
PC/SC171 (USB-C)
    │
    ▼
┌──────────────────┐
│  舵机驱动板        │  CH340 USB → TTL 转换
│  (Waveshare 定制) │  半双工方向控制
│  VID=1a86         │
└──────┬───────────┘
       │ 3 线总线 (GND / VCC / DATA)
       │ TTL 信号, 1 Mbps, 单线半双工
       ├── Servo ID=1 (J1 底座)
       ├── Servo ID=2 (J2 肩部)
       ├── Servo ID=3 (J3 肘部)
       ├── Servo ID=4 (J4 腕部俯仰)
       ├── Servo ID=5 (J5 腕部旋转)
       └── Servo ID=6 (J6 夹爪)
```

### 2.5 供电架构

| 电压域 | 电压 | 用途 |
|--------|------|------|
| **逻辑电** | 5V (USB-C) | CH340 芯片 + 舵机 MCU 逻辑 |
| **动力电** | 7.4V (标准) / 12V (Pro) | 舵机直流电机驱动 |

> ⚠️ **注意**: 12 个舵机同时全扭矩运转时理论峰值电流可达 **30A**。Pro Kit 标称 12V/2A 电源仅适用于常规负载。重载任务需要更大的电源。

### 2.6 运动学参数 (DH 表)

使用 Modified DH (Craig) 约定重建的运动学链:

| 关节 i | α_{i-1} | a_{i-1} | d_i | θ_i 范围 |
|--------|---------|---------|-----|----------|
| 1 | 0 | 0 | ~60mm | ±135° |
| 2 | -90° | 0 | 0 | ±120° |
| 3 | 0 | ~130mm | 0 | ±120° |
| 4 | 0 | ~120mm | 0 | ±135° |
| 5 | -90° | 0 | 0 | ±180° |
| 6 | 90° | 0 | ~55mm | 0~70° (夹爪) |

> 精确 DH 参数需从 [官方 GitHub 仓库](https://github.com/EmbodiedAI-Group/SO-ARM101-6DoF) 的 STEP/URDF 文件中提取。上述为根据已知结构估算值, 用于运动学理解。

---

## 三、控制原理

### 3.1 完整控制栈

```
┌──────────────────────────────────────────┐
│  第5层: Task Executor (组合动作引擎)      │  ← 本指南重点
│  拾取/放置/装配/写字/分拣                 │
├──────────────────────────────────────────┤
│  第4层: LeRobot 框架 (HuggingFace)       │  ← 数据采集+训练+推理
│  Teleoperate / Record / Train / Replay   │
├──────────────────────────────────────────┤
│  第3层: Python 串口 SDK                   │  ← pyserial / feetech-sdk / scservo
│  指令帧封装 / 同步读写 / 总线扫描         │
├──────────────────────────────────────────┤
│  第2层: 驱动板 (CH340 USB-TTL)            │  ← 硬件信号转换
│  USB ↔ TTL 半双工                         │
├──────────────────────────────────────────┤
│  第1层: STS3215 舵机 (6颗)               │  ← 物理执行
│  磁编码回读 / PID 位置控制 / 电流监测     │
└──────────────────────────────────────────┘
```

### 3.2 STS3215 通信协议帧格式

舵机通信采用 **Dynamixel 兼容** 二进制协议, 这是底层编程的**核心知识**:

#### 指令帧 (主控 → 舵机)

```
[0xFF] [0xFF] [ID] [Length] [Instruction] [Params...] [Checksum]
```

#### 应答帧 (舵机 → 主控)

```
[0xFF] [0xFF] [ID] [Length] [Error] [Data...] [Checksum]
```

#### 字段含义

| 字段 | 字节 | 说明 |
|------|------|------|
| Header | 2 | 固定 `0xFF 0xFF` |
| ID | 1 | 舵机编号 (1~253, 254=广播) |
| Length | 1 | 后续字节数 (Instruction + Params + Checksum) |
| Instruction | 1 | 指令类型 |
| Params | N | 参数 (依赖于指令) |
| Error | 1 | 错误码 (仅应答帧, 0=正常) |
| Checksum | 1 | `~((ID + Length + Instruction + sum(Params)) & 0xFF)` |

#### 核心指令

| 指令 | 代码 | 用途 |
|------|------|------|
| **PING** | 0x01 | 检测舵机在线 (返回型号) |
| **READ** | 0x02 | 读取寄存器 (位置/电流/温度等) |
| **WRITE** | 0x03 | 写入寄存器 (设置目标位置/速度/扭矩等) |
| **SYNC_WRITE** | 0x83 | **多舵机同步写入** (关键! 用于协调多关节运动) |

### 3.3 关键寄存器映射

| 地址 | 名称 | 大小 | 访问 | 说明 |
|------|------|------|------|------|
| 0x05 | ID | 1B | R/W | 舵机 ID |
| 0x06 | Baud Rate | 1B | R/W | 1=1Mbps, 3=500k, 4=115200 |
| 0x21 | **Torque Enable** | 1B | R/W | **0=卸力, 1=上力** (必须先上力才能动!) |
| 0x2A | **Goal Position** | 2B | R/W | 目标位置 0-4095 (0°~360°) |
| 0x2E | **Goal Speed** | 2B | R/W | 运动速度 |
| 0x38 | **Present Position** | 2B | R | 当前位置 (回读) |
| 0x3A | Present Speed | 2B | R | 当前速度 |
| 0x3C | **Present Load** | 2B | R | 当前负载 (0~1000), 碰撞检测 |
| 0x3E | Present Voltage | 1B | R | 当前电压 (0.1V/单位) |
| 0x3F | Present Temperature | 1B | R | 当前温度 (°C) |
| 0x15 | **P Coefficient** | 1B | R/W | 位置环比例增益 (默认 32) |
| 0x16 | D Coefficient | 1B | R/W | 位置环微分增益 |
| 0x17 | I Coefficient | 1B | R/W | 位置环积分增益 (默认 0) |
| 0x42 | Moving | 1B | R | **0=停止, 1=运动中** |

### 3.4 一个完整的控制周期

```
 1. Torque Enable → 0x01 (上力)
 2. Goal Position → 0x2A (设目标位置)
 3. Goal Speed    → 0x2E (设运动速度)
 4. [执行运动...]
 5. Read Moving   → 0x42 (轮询是否运动完毕)
 6. Read Position → 0x38 (验证到位精度)
 7. Read Load     → 0x3C (确认无异常负载)
 8. Torque Enable → 0x00 (可选, 到达后卸力省电/安全)
```

### 3.5 位置换算公式

```
raw_position = int((angle_degrees / 360.0) * 4096)

angle_degrees = (raw_position / 4096.0) * 360.0

# 带零位补偿
actual_angle = ((raw_position - homing_offset) / 4096.0) * 360.0
```

### 3.6 SYNC_WRITE 的关键作用

如果不使用 SYNC_WRITE 而逐个发送 WRITE 指令, 6 个关节到达目标位置的时间会错开约 **50~150ms**, 导致末端轨迹偏移和视觉上的"爬行"效果。SYNC_WRITE 通过一个广播帧同时更新所有舵机目标位置, 保证**亚毫秒级同步**。

---

## 四、需要下载的资料清单

### 4.1 必装软件

| 序号 | 资源 | 下载方式 | 功能说明 |
|------|------|---------|---------|
| 1 | **LeRobot 框架** | `git clone https://github.com/huggingface/lerobot && pip install -e ".[feetech]"` | 核心控制框架: 数据采集/训练/回放/标定 |
| 2 | **scservo-sdk** | `pip install scservo-sdk` | SCServo 协议 Python SDK (低层寄存器读写) |
| 3 | **feetech-servo-sdk** | `pip install feetech-servo-sdk` | Feetech 高级 SDK (扫描/位置/速度/温度) |
| 4 | **pyserial** | `pip install pyserial` (已安装) | 串口通信基础库 |

### 4.2 GitHub 仓库

| 仓库 | 用途 | 何时需要 |
|------|------|---------|
| [TheRobotStudio/SO-ARM100](https://github.com/TheRobotStudio/SO-ARM100) | STL 3D 打印文件 + URDF 模型 | 自打印结构件 / 运动学仿真 |
| [EmbodiedAI-Group/SO-ARM101-6DoF](https://github.com/EmbodiedAI-Group/SO-ARM101-6DoF) | 组装手册 + STEP 文件 | 重新组装 / 结构改造 |
| [masato-ka/gym-soarm](https://github.com/masato-ka/gym-soarm) | MuJoCo 仿真环境 `pip install gym-soarm` | **训练前先在仿真中测试策略** |
| [roboninecom/SO-ARM100-101-Parallel-Gripper](https://github.com/roboninecom/SO-ARM100-101-Parallel-Gripper) | 改进版平行夹爪 (3D 打印) | 提高夹持精度 |

### 4.3 舵机配置工具

| 工具 | 平台 | 功能 |
|------|------|------|
| **FD Debug (FD1.9.8.x)** | Windows | 舵机固件升级 + ID 配置 + 零位校准 (官方标配) |
| **feetech-servo-tool** | 全平台 | FD Debug 的 Python 替代品 |

### 4.4 音频相关 (已安装/可复用)

| 工具 | 安装 | 用途 |
|------|------|------|
| **edge-tts** | `pip install edge-tts` | 高质量中文 TTS (在线, 免费) |
| **espeak-ng** | `apt install espeak-ng` (已装) | 离线中文 TTS 降级方案 |
| **pygame** | `pip install pygame` | 音乐播放 + 独立音量控制 |
| **ffplay** | `apt install ffmpeg` | 命令行音频播放 |

### 4.5 参考文档

| 文档 | 链接 |
|------|------|
| Waveshare Wiki (CN) | https://www.waveshare.net/wiki/SO-ARM100/101 |
| HuggingFace LeRobot 文档 | https://huggingface.co/docs/lerobot |
| Hiwonder 用户手册 | https://docs.hiwonder.com/projects/LeRobot/en/latest/ |
| STS3215 数据手册 | [Core Electronics](https://core-electronics.com.au/attachments/uploads/sts3215-smart-servo-datasheet-translated.pdf) |

---

## 五、编程方法: 从底层到高层

### 5.1 方法一: 纯 pyserial 裸协议 (最快、最可控)

适合: 实时性要求最高的场景, 完全掌控每一帧。

```python
import serial
import struct

def checksum(data):
    return (~sum(data) & 0xFF)

def build_write_position_packet(servo_id: int, raw_position: int, speed: int = 2400):
    """
    构建写位置指令帧
    raw_position: 0-4095
    speed: 步/秒 (2400 ≈ 210°/s)
    """
    pos_low = raw_position & 0xFF
    pos_high = (raw_position >> 8) & 0xFF
    spd_low = speed & 0xFF
    spd_high = (speed >> 8) & 0xFF

    # 指令格式: WRITE 从地址 0x2A 开始写4字节 (位置2B + 速度2B)
    core = bytes([
        servo_id,
        0x07,       # Length = inst(1) + addr(1) + pos(2) + spd(2) + cksum(1)
        0x03,       # WRITE
        0x2A,       # 起始地址: Goal Position
        pos_low, pos_high,
        spd_low, spd_high
    ])
    ck = checksum(core)
    return b'\xFF\xFF' + core + bytes([ck])

def ping_servo(ser, servo_id: int) -> bool:
    """检测舵机是否在线"""
    packet = b'\xFF\xFF' + bytes([servo_id, 0x02, 0x01]) + bytes([checksum([servo_id, 0x02, 0x01])])
    ser.write(packet)
    response = ser.read(6)  # 0xFF 0xFF ID Len Err Cksum
    return len(response) >= 6 and response[0] == 0xFF

# 使用
ser = serial.Serial('/dev/ttyACM0', baudrate=1000000, timeout=0.1)

# 扫描所有舵机
for i in range(1, 13):
    if ping_servo(ser, i):
        print(f"✅ 舵机 {i} 在线")

# 上力
ser.write(build_write_packet(1, 0x28, [0x01]))  # Torque Enable(0x28) = 1

# 移动到中心位置 (2048)
ser.write(build_write_position_packet(1, 2048, 2400))
```

### 5.2 方法二: scservo-sdk (推荐日常开发)

```python
from scservo_sdk import *

# 初始化
port = PortHandler('/dev/ttyACM0')
port.openPort()
port.setBaudRate(1000000)
device = sms_sts(port)

# 基础操作
device.write1ByteTxRx(1, 0x28, 1)          # 关节1 上力
device.WritePosEx(1, 2048, speed=2400, acc=50)  # 关节1 移到中心
pos, _, _ = device.ReadPos(1)              # 读取关节1 位置
load, _, _ = device.ReadLoad(1)            # 读取关节1 当前负载
temp = device.read1ByteTx(1, 0x3F)         # 读取关节1 温度

# 12个舵机批量上力
for i in range(1, 13):
    device.write1ByteTxRx(i, 0x28, 1)

port.closePort()
```

### 5.3 方法三: LeRobot API (数据采集/训练/部署)

```bash
# 标定
python -m lerobot.calibrate \
    --robot.type=so101_follower \
    --robot.port=/dev/ttyACM0 \
    --robot.id=my_arm

# 遥操作 (Leader 控制 Follower)
python -m lerobot.teleoperate \
    --robot.type=so101_follower --robot.port=/dev/ttyACM1 --robot.id=my_follower \
    --teleop.type=so101_leader --teleop.port=/dev/ttyACM0 --teleop.id=my_leader

# 采集数据
python -m lerobot.record \
    --robot.type=so101_follower --robot.port=/dev/ttyACM1 --robot.id=my_follower \
    --teleop.type=so101_leader --teleop.port=/dev/ttyACM0 --teleop.id=my_leader \
    --dataset.repo_id=my_user/my_dataset --dataset.num_episodes=10

# 回放
python -m lerobot.replay \
    --robot.type=so101_follower --robot.port=/dev/ttyACM1 --robot.id=my_follower \
    --dataset.repo_id=my_user/my_dataset --dataset.episode=0
```

### 5.4 完整独立控制类 (推荐用于芯伴 X1)

```python
import time
import numpy as np
from scservo_sdk import *

class SOARM101Controller:
    """芯伴 X1 机械臂独立控制器 — 不依赖 LeRobot"""

    JOINTS = ["shoulder_pan", "shoulder_lift", "elbow_flex",
              "wrist_flex", "wrist_roll", "gripper"]

    # 关键寄存器
    REG_TORQUE_ENABLE = 0x28
    REG_GOAL_POSITION = 0x2A
    REG_GOAL_SPEED    = 0x2E
    REG_PRESENT_POS   = 0x38
    REG_PRESENT_LOAD  = 0x3C
    REG_PRESENT_VOLT  = 0x3E
    REG_PRESENT_TEMP  = 0x3F
    REG_MOVING        = 0x42
    REG_P_COEFF       = 0x15

    STEPS_PER_REV = 4096
    DEG_PER_STEP = 360.0 / STEPS_PER_REV  # 0.08789

    def __init__(self, port="/dev/ttyACM0", baudrate=1000000):
        self.port = PortHandler(port)
        self.port.openPort()
        self.port.setBaudRate(baudrate)
        self.dev = sms_sts(self.port)

    def ping(self, sid):  # 检测在线
        model, result, _ = self.dev.ping(sid)
        return result == COMM_SUCCESS

    def scan(self):  # 扫描所有舵机
        return [i for i in range(1, 254) if self.ping(i)]

    def torque(self, sid, enable=True):
        self.dev.write1ByteTxRx(sid, self.REG_TORQUE_ENABLE, 1 if enable else 0)

    def torque_all(self, enable=True):
        for i in range(1, 7): self.torque(i, enable)

    def move_joint(self, sid, degrees, speed=2400):
        """移动单个关节: degree 角度, speed 步/秒"""
        raw = int((degrees / 360.0) * self.STEPS_PER_REV) & 0xFFF
        self.dev.WritePosEx(sid, raw, speed=speed, acc=50)

    def move_joints(self, angles_deg: dict, speed=2400):
        """移动多个关节: {joint_name: degrees} 或 {joint_id: degrees}"""
        for key, deg in angles_deg.items():
            if isinstance(key, str):
                idx = self.JOINTS.index(key)
            else:
                idx = key
            self.move_joint(idx + 1, deg, speed)

    def get_position(self, sid):
        raw, _, _ = self.dev.ReadPos(sid)
        return raw * self.DEG_PER_STEP

    def get_all_positions(self):
        return {self.JOINTS[i]: self.get_position(i+1) for i in range(6)}

    def get_load(self, sid):
        """负载 0~1000 (1000 = 100% 扭矩)"""
        load, _, _ = self.dev.ReadLoad(sid)
        return load

    def get_all_loads(self):
        return [self.get_load(i+1) for i in range(6)]

    def get_temp(self, sid):
        return self.dev.read1ByteTx(sid, self.REG_PRESENT_TEMP)

    def get_all_temps(self):
        return [self.get_temp(i+1) for i in range(6)]

    def is_moving(self):
        for i in range(1, 7):
            if self.dev.read1ByteTx(i, self.REG_MOVING):
                return True
        return False

    def wait(self, timeout=5.0):
        t0 = time.time()
        while time.time() - t0 < timeout:
            if not self.is_moving():
                return True
            time.sleep(0.05)
        return False

    def stop(self):
        """紧急停止 — 所有关节扭矩卸载"""
        self.torque_all(False)

    def reset(self):
        """安全复位: 卸力 → 上力 → 归零"""
        self.torque_all(False)
        time.sleep(0.3)
        self.torque_all(True)
        time.sleep(0.2)
        # 各关节归零 (具体零位需标定)
        default = {"shoulder_pan": 0, "shoulder_lift": 0, "elbow_flex": 0,
                    "wrist_flex": 0, "wrist_roll": 0, "gripper": 45}
        self.move_joints(default)
        self.wait()

    def close(self):
        self.torque_all(False)
        self.port.closePort()
```

---

## 六、如何操作: 从零到运动

### 6.1 完整的首次启动流程

```bash
# ─── Phase 0: 固件升级 (Windows, 仅首次!) ───
# 1. 下载 FD Debug 工具
# 2. 逐个连接舵机, 升级到同一固件版本
# 3. 设置每个舵机的零位 (令其旋转到机械中位, 写入偏移)

# ─── Phase 1: 环境准备 ───
cd ~/hxg
conda create -n armbridge python=3.10 -y
conda activate armbridge
pip install pyserial scservo-sdk feetech-servo-sdk

# ─── Phase 2: 物理连接 ───
# 将机械臂驱动板 USB-C 插入 SC171 USB 口
# 插入 12V DC 电源

# ─── Phase 3: 设备识别 ───
ls /dev/ttyACM* /dev/ttyUSB*    # 查找设备
sudo chmod 666 /dev/ttyACM0     # 授权

# ─── Phase 4: 舵机检测 ───
python3 << 'EOF'
from scservo_sdk import *
port = PortHandler('/dev/ttyACM0')
port.openPort()
port.setBaudRate(1000000)
dev = sms_sts(port)
for i in range(1, 13):
    model, result, _ = dev.ping(i)
    if result == COMM_SUCCESS:
        print(f"✅ 舵机 ID={i} 在线, 型号={model}")
port.closePort()
EOF

# ─── Phase 5: 标定 (LeRobot 方式) ───
git clone https://github.com/huggingface/lerobot.git
cd lerobot
pip install -e ".[feetech]"
python -m lerobot.calibrate \
    --robot.type=so101_follower \
    --robot.port=/dev/ttyACM0 \
    --robot.id=x1_arm

# ─── Phase 6: 基础运动测试 ───
python3 << 'EOF'
from soarm101_controller import SOARM101Controller
ctrl = SOARM101Controller("/dev/ttyACM0")
print("在线舵机:", ctrl.scan())
ctrl.torque_all(True)
ctrl.move_joints({
    "shoulder_pan": 0, "shoulder_lift": 0, "elbow_flex": -30,
    "wrist_flex": 0, "wrist_roll": 0, "gripper": 30
})
ctrl.wait()
print("到位:", ctrl.get_all_positions())
ctrl.torque_all(False)
ctrl.close()
EOF
```

### 6.2 PID 振荡排查

如果舵机到达目标位置后抖动/啸叫:

```python
# 原因: P 增益过高 → 减小 P_Coefficient (地址 0x15)
from scservo_sdk import *

port = PortHandler('/dev/ttyACM0')
port.openPort()
port.setBaudRate(1000000)
dev = sms_sts(port)

for sid in range(1, 7):
    dev.write1ByteTxRx(sid, 0x15, 16)  # 从 32 降到 16
    dev.write1ByteTxRx(sid, 0x16, 4)   # 加点 D 抑制过冲
```

| 现象 | 原因 | 解决方法 |
|------|------|----------|
| 到位后高频尖叫 | P 太高 | P_Coefficient 32→16→8 |
| 到位后慢速来回晃 | I 太高或 P 太低 | 调整 P/I 比例 |
| 过冲再弹回 | D 太低 | D_Coefficient 0→4→8 |
| 运动中抖动 | 加速太快 | 降 Goal Speed, 增 Goal Time |
| 吊着重物往下掉 | P 太低或扭矩不足 | 增 P, 检查供电电压 |

---

## 七、组合动作编程: 拾取/拼装/写字

### 7.1 核心思想: 原语(Primitive) → 序列(Sequence) → 任务(Task)

```
Primitive (原语)       = 最小执行单元
  ├── move_joints(joint_dict)    # 关节空间移动
  ├── move_pose(x,y,z,r,p,y)     # 笛卡尔空间移动
  ├── gripper_open()             # 张开夹爪
  ├── gripper_close(value)       # 合拢夹爪 (value: 0~1)
  ├── wait(seconds)              # 等待
  └── home()                     # 归零

Sequence (序列)        = 有序原语链 + 错误处理
  pick_and_place = [approach, pre_grasp, grasp, lift, transport, place, release, retract]

Task (任务)            = 序列 + 前置检查 + 后置验证 + 降级策略
  task = {pre_checks, sequence, post_checks, fallback}
```

### 7.2 拾取与放置 (Pick & Place)

```python
import numpy as np

def pick_and_place(ctrl, pick_xyz, place_xyz, lift_height=0.08):
    """
    标准拾取放置流程 (8步)

    pick_xyz: [x, y, z] 拾取点 (米, 相对底座)
    place_xyz: [x, y, z] 放置点
    lift_height: 抬升高度 (米)
    """

    # Step 1: 张开夹爪, 归零
    ctrl.torque_all(True)
    ctrl.move_joints({"gripper": 45})  # 张开
    ctrl.move_joints({
        "shoulder_pan": 0, "shoulder_lift": 0, "elbow_flex": 0,
        "wrist_flex": 0, "wrist_roll": 0
    })
    ctrl.wait()

    # Step 2: 接近 (上方 5cm)
    above_pick = pick_xyz.copy()
    above_pick[2] += 0.05
    pick_joints = solve_ik(ctrl, above_pick)  # IK 求解
    ctrl.move_joints(pick_joints, speed=1200)
    ctrl.wait()

    # Step 3: 降下 (接触)
    pick_joints = solve_ik(ctrl, pick_xyz)
    ctrl.move_joints(pick_joints, speed=600)  # 慢速
    ctrl.wait()

    # Step 4: 夹取 (监控电流)
    ctrl.move_joints({"gripper": 5})  # 闭合 (留余量)
    time.sleep(0.5)
    # 确认夹紧: 检查 J6 负载
    load = ctrl.get_load(6)
    if load < 100:  # 负载太低 = 没夹到
        print("⚠️ 未检测到抓取负载!")
    ctrl.wait()

    # Step 5: 抬升
    lift_joints = solve_ik(ctrl, above_pick)
    ctrl.move_joints(lift_joints, speed=1200)
    ctrl.wait()

    # Step 6: 搬运 (抬高到放置点上方)
    above_place = place_xyz.copy()
    above_place[2] += 0.05
    transport_joints = solve_ik(ctrl, above_place)
    ctrl.move_joints(transport_joints, speed=1800)
    ctrl.wait()

    # Step 7: 放置
    place_joints = solve_ik(ctrl, place_xyz)
    ctrl.move_joints(place_joints, speed=600)
    ctrl.wait()

    # Step 8: 释放 + 退回
    ctrl.move_joints({"gripper": 45})
    ctrl.wait()
    ctrl.move_joints(lift_joints, speed=1200)
    ctrl.wait()
    ctrl.reset()
```

### 7.3 装配 (Peg-in-Hole 插销入孔)

装配的关键是**螺旋搜索 + 力反馈闭环**:

```python
def peg_in_hole(ctrl, hole_xyz, insertion_depth=0.03, search_radius=0.003):
    """
    插销入孔: 下降过程中用螺旋轨迹搜索孔位
    通过电流反馈检测插入成功
    """
    # Step 1: 移动到孔上方
    above = hole_xyz.copy()
    above[2] += 0.04
    ctrl.move_joints(solve_ik(ctrl, above), speed=1200)
    ctrl.wait()

    # Step 2: 缓慢下降, 监控 J3/J4 电流 (Z方向力)
    target = hole_xyz.copy()
    target[2] -= insertion_depth

    for depth in np.linspace(0, insertion_depth, 20):
        z = hole_xyz[2] - depth
        # 螺线搜索 (Archimedean spiral)
        theta = depth / insertion_depth * 4 * np.pi
        r = search_radius * (1 - depth / insertion_depth)  # 半径递减

        search_xyz = hole_xyz.copy()
        search_xyz[0] += r * np.cos(theta)
        search_xyz[1] += r * np.sin(theta)
        search_xyz[2] = z

        joints = solve_ik(ctrl, search_xyz)
        ctrl.move_joints(joints, speed=300)  # 极慢
        ctrl.wait()

        # 力反馈: 如果 Z 向负载突然增大 → 插入成功
        loads = ctrl.get_all_loads()
        if max(loads[2:5]) > 300:  # J2/J3/J4 任一超阈值
            print(f"✅ 检测到插入力, depth={depth*1000:.1f}mm")
            break

    # Step 3: 垂直下压确认
    ctrl.move_joints(solve_ik(ctrl, target), speed=300)
    ctrl.wait()

    # Step 4: 释放并退回
    ctrl.move_joints({"gripper": 45})
    ctrl.wait()
    retract = above.copy()
    retract[2] += 0.05
    ctrl.move_joints(solve_ik(ctrl, retract), speed=1800)
    ctrl.wait()
```

### 7.4 写字/绘图

```python
def draw_text(ctrl, text: str, start_xyz, font_size=0.02, pen_offset_z=-0.002):
    """
    写字: 将文本分解为曲线航点, 笛卡尔空间线性插补

    简化版: 仅画横线做演示, 真实写字需要字体轮廓→航点转换
    """
    # 1. 移动到起点上方
    above = start_xyz.copy()
    above[2] += 0.03
    ctrl.move_joints(solve_ik(ctrl, above), speed=1500)
    ctrl.wait()

    # 2. 落笔
    pen_down = start_xyz.copy()
    pen_down[2] += pen_offset_z
    ctrl.move_joints(solve_ik(ctrl, pen_down), speed=600)
    ctrl.wait()

    # 3. 沿路径画线
    strokes = text_to_strokes(text, start_xyz, font_size)  # 你需要实现此函数
    for i, point in enumerate(strokes):
        joints = solve_ik(ctrl, point)
        ctrl.move_joints(joints, speed=300)  # 慢速保证平滑
        time.sleep(0.02)  # 50Hz 控制频率

    # 4. 抬笔
    ctrl.move_joints(solve_ik(ctrl, above), speed=1200)
    ctrl.wait()
```

### 7.5 分拣 (颜色/形状分类)

```python
def sort_objects(ctrl, detected_objects: list, zone_map: dict):
    """
    分类分拣: 相机检测 → 按类别放置到不同区域

    detected_objects: [{"label": "red", "xyz": [x,y,z]}, ...]
    zone_map: {"red": [x1,y1,z1], "blue": [x2,y2,z2], ...}
    """
    for obj in detected_objects:
        label = obj["label"]
        pick = np.array(obj["xyz"])
        place = np.array(zone_map.get(label, zone_map["unknown"]))

        print(f"🎯 分拣 {label}: {pick[:2]} → {place[:2]}")
        pick_and_place(ctrl, pick, place)

    ctrl.reset()
```

### 7.6 逆运动学 (IK) 求解

```python
# 方案1: LeRobot 内置 IK
from lerobot_kinematics.lerobot import get_robot, lerobot_IK
robot = get_robot("so100")
target_pose = np.array([0.35, 0.0, 0.25, 0.0, 0.0, 0.0])
joints, success = lerobot_IK(current_joints, target_pose, robot)

# 方案2: 数值 IK (牛顿-拉夫森)
def solve_ik_numeric(ctrl, target_xyz, max_iter=100, tolerance=1e-3):
    """
    简化版: 仅考虑末端位置 (3DOF)
    使用 Jacobian 伪逆迭代求解
    """
    joints = np.array(list(ctrl.get_all_positions().values()))  # 起始猜测
    joints = np.deg2rad(joints)

    for _ in range(max_iter):
        # 前向运动学 (FK)
        current_xyz = forward_kinematics(joints)  # 需实现
        error = target_xyz[:3] - current_xyz

        if np.linalg.norm(error) < tolerance:
            return np.rad2deg(joints)

        # Jacobian (3x6) 伪逆
        J = compute_jacobian(joints)  # 需实现
        delta = np.linalg.pinv(J) @ error
        joints += 0.1 * delta  # 小步长更新

    return None  # 未收敛
```

---

## 八、语音播报 + 音乐播放集成

### 8.1 架构: 三条独立音频通道

```
┌────────────┐  ┌────────────┐  ┌────────────┐
│ Channel 0  │  │ Channel 1  │  │ Channel 2  │
│ 背景音乐    │  │ 语音播报    │  │ 动作音效    │
│ 音量: 30%  │  │ 音量: 100% │  │ 音量: 80%  │
│ pygame混音器│  │ edge-tts   │  │ pygame SFX │
└────────────┘  └────────────┘  └────────────┘
       │               │               │
       └───────────────┼───────────────┘
                       │
               USB声卡输出 (plughw:0,0)
```

### 8.2 音乐管理器 (pygame.mixer)

```python
import pygame.mixer
import threading
import time

class MusicManager:
    """背景音乐管理 — 独立通道, 支持淡入淡出和音量闪避"""

    def __init__(self, music_vol=0.3, speech_vol=1.0):
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=4096)
        self.ch_music = pygame.mixer.Channel(0)    # 音乐频道
        self.ch_sfx = pygame.mixer.Channel(1)      # 音效频道
        self.ch_music.set_volume(music_vol)
        self.ch_sfx.set_volume(speech_vol)
        self.music_vol = music_vol

    def play_music(self, filepath: str, loop=-1, fade_in_ms=1500):
        """播放背景音乐 (非阻塞), loop=-1=无限循环"""
        sound = pygame.mixer.Sound(filepath)
        self.ch_music.play(sound, loops=loop, fade_ms=fade_in_ms)

    def fade_out_music(self, duration_ms=2000):
        """平滑淡出"""
        self.ch_music.fadeout(duration_ms)

    def duck_for_speech(self, duck_vol=0.08, restore_after_s=3.0):
        """
        语音播报时自动降低音乐 (音频闪避/Ducking)
        你说话 → 音乐自动变小声 → 说完 → 音乐恢复
        """
        orig = self.music_vol
        self.ch_music.set_volume(duck_vol)
        threading.Timer(restore_after_s, lambda: self.ch_music.set_volume(orig)).start()

    def play_sfx(self, filepath: str, volume=0.8):
        """短促音效 (夹取/放置/完成)"""
        sound = pygame.mixer.Sound(filepath)
        self.ch_sfx.set_volume(volume)
        self.ch_sfx.play(sound)

    def stop(self):
        self.ch_music.stop()
        self.ch_sfx.stop()
```

### 8.3 语音播报管理器 (TTS)

```python
import asyncio
import edge_tts
import tempfile
import subprocess
import threading
import os

class VoiceManager:
    """中文 TTS 语音播报 — 默认非阻塞, 不打断机械臂控制"""

    def __init__(self, voice="zh-CN-XiaoxiaoNeural"):
        self.voice = voice
        self._loop = asyncio.new_event_loop()
        threading.Thread(target=self._loop.run_forever, daemon=True).start()

    def speak(self, text: str, blocking=False):
        """播报中文文本"""
        if blocking:
            asyncio.run(self._edge_tts_speak(text))
        else:
            # 非阻塞: 后台播放, arm 控制不受影响
            asyncio.run_coroutine_threadsafe(
                self._edge_tts_speak(text), self._loop
            )

    async def _edge_tts_speak(self, text: str):
        """edge-tts 在线合成 → ffplay 播放到 USB 声卡"""
        tmp = tempfile.mktemp(suffix=".mp3")
        try:
            comm = edge_tts.Communicate(text, self.voice)
            await comm.save(tmp)
            subprocess.run([
                "ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet",
                "-af", "volume=1.0", tmp
            ], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
               stderr=subprocess.DEVNULL)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def speak_blocking(self, text: str):
        """阻塞式播报 — 用于紧急提示"""
        self.speak(text, blocking=True)
```

### 8.4 统一音频管理器

```python
class AudioManager:
    """芯伴 X1 统一音频: 音乐 + 语音 + 音效"""

    def __init__(self):
        self.music = MusicManager(music_vol=0.3, speech_vol=1.0)
        self.voice = VoiceManager()

    def start_task(self, task_name: str, music_file: str = None):
        """任务开始: 宣布任务名 + 背景音乐淡入"""
        self.voice.speak(f"开始执行: {task_name}")
        if music_file:
            self.music.play_music(music_file, loop=-1)

    def announce_action(self, text: str):
        """动作前播报 + 自动降低背景音乐"""
        self.music.duck_for_speech()
        self.voice.speak(text)

    def play_action_sfx(self, sfx_file: str):
        """动作音效 (如: 吸尘器声, 咔嗒声)"""
        self.music.play_sfx(sfx_file)

    def end_task(self, task_name: str, success: bool):
        """任务结束: 淡出音乐 + 播报结果"""
        self.music.fade_out_music(2000)
        result = "完成" if success else "失败, 已触发安全保护"
        self.voice.speak(f"任务{task_name}{result}", blocking=True)

    def emergency(self, message="紧急停止"):
        """紧急播报 — 阻塞, 最高优先级"""
        self.music.stop()
        self.voice.speak_blocking(message)
```

### 8.5 集成示例: 伴随语音的拾取动作

```python
audio = AudioManager()

# 任务开始 → 语音 + 背景音乐
audio.start_task("拾取红色积木", music_file="assets/music/gentle_bgm.wav")

# Step 1: 播报 (音乐自动变小)
audio.announce_action("接近目标物体")
ctrl.move_joints(approach_joints, speed=1200)
ctrl.wait()

# Step 2: 播报 + 音效
audio.announce_action("正在拾取")
audio.play_action_sfx("assets/sfx/grab.wav")
ctrl.move_joints({"gripper": 5})
ctrl.wait()

# Step 3: 播报
audio.announce_action("已拾取, 正在搬运")
ctrl.move_joints(transport_joints, speed=1800)
ctrl.wait()

# Step 4: 释放 + 音效
audio.announce_action("放置完成")
audio.play_action_sfx("assets/sfx/release.wav")
ctrl.move_joints({"gripper": 45})
ctrl.wait()

# 任务结束 → 淡出音乐 + 最终播报
audio.end_task("拾取红色积木", success=True)
```

### 8.6 中国语音色

```python
# edge-tts 中文可选音色:
voices = {
    "xiaoxiao": "zh-CN-XiaoxiaoNeural",   # 女声, 活泼温暖 (★推荐)
    "yunxi":    "zh-CN-YunxiNeural",      # 男声, 年轻
    "yunyang":  "zh-CN-YunyangNeural",    # 男声, 专业新闻
    "xiaoyi":   "zh-CN-XiaoyiNeural",     # 女声, 清晰标准
}
```

---

## 九、安全体系: 不失控不损坏

### 9.1 六层安全防护

```
Layer 1: 舵机固件保护 → 温度/电压/过流自动断电 (STS3215 内置)
Layer 2: 软件限位      → 关节角度范围预检
Layer 3: 速率限制      → 不同模式的速度上限
Layer 4: 电流监控      → 20Hz 实时负载检测 → 碰撞感知
Layer 5: 紧急停止      → arm_stop() 立即扭矩卸载
Layer 6: 工作空间边界  → 禁止区域检测 (不撞人/不撞显示器)
```

### 9.2 安全状态机

```
IDLE (空闲)
  │
  ├── 收到运动指令
  ▼
PRE_CHECK (运动前检查)
  ├── 关节限位 ✅
  ├── 温度正常 ✅
  ├── 电流基线正常 ✅
  ├── 工作空间安全 ✅
  │
  ├─ 通过 ──→ IN_MOTION (运动中监控)
  │              ├── 20Hz 电流监控
  │              ├── 温度监控
  │              └── 超时保护
  │
  └─ 不通过 ──→ FAULT (故障, 需人工)
                    │
              运动结束 / 异常检测
                    │
              ┌─────┴─────┐
              ▼           ▼
           IDLE      EMERGENCY_STOP
                      ├── 扭矩卸载
                      ├── 语音告警
                      └── 记录日志
```

### 9.3 关键安全参数 (需实机标定)

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `CURRENT_IDLE_MAX` | 100mA | 空载电流上限 |
| `CURRENT_NORMAL_MAX` | 500mA | 正常运动电流上限 |
| `CURRENT_EMERGENCY` | 1000mA | 紧急停止电流阈值 |
| `TEMP_WARN` | 60°C | 温度警告 |
| `TEMP_MAX` | 75°C | 温度上限 |
| `MOTION_TIMEOUT` | 10s | 运动超时 (防止堵转) |
| `SPEED_SAFE` | 0.2 (20%) | 安全模式速度系数 |
| `SPEED_NORMAL` | 0.6 (60%) | 正常工作速度 |
| `MONITOR_RATE` | 20Hz | 安全监控频率 |

### 9.4 安全控制器实现

```python
import threading
import time

class SafetyLayer:
    """所有运动指令必须经过此层"""

    JOINT_LIMITS = [  # (min_deg, max_deg)
        (-150, 150), (-45, 90), (-120, 30),
        (-90, 90), (-180, 180), (0, 70),
    ]

    def __init__(self, ctrl: SOARM101Controller):
        self.ctrl = ctrl
        self.mode = "normal"
        self._stop_flag = threading.Event()
        self._monitor = None

    def pre_check(self, target_joints: dict) -> bool:
        """运动前安全检查"""
        # 1. 关节限位
        for key, deg in target_joints.items():
            if isinstance(key, str):
                idx = self.ctrl.JOINTS.index(key)
            else:
                idx = key - 1
            lo, hi = self.JOINT_LIMITS[idx]
            if deg < lo or deg > hi:
                print(f"🛑 关节{idx+1} 超出限位: {deg}° (允许 [{lo}, {hi}]°)")
                return False

        # 2. 温度检查
        temps = self.ctrl.get_all_temps()
        for i, t in enumerate(temps):
            if t > 75:
                print(f"🛑 关节{i+1} 过热: {t}°C")
                self.emergency_stop()
                return False
            if t > 60:
                print(f"⚠️ 关节{i+1} 温度偏高: {t}°C")

        # 3. 速度限制
        if self.mode == "safe":
            for key in target_joints:
                # 限制目标变化量
                pass

        return True

    def with_monitor(self, func, timeout=10.0):
        """执行运动 + 后台安全监控"""
        self._stop_flag.clear()

        def monitor():
            t0 = time.time()
            while not self._stop_flag.is_set():
                # 电流监控
                loads = self.ctrl.get_all_loads()
                for i, load in enumerate(loads):
                    if load > 800:  # 800/1000 = 80% 扭矩
                        print(f"🛑 关节{i+1} 过载: {load}/1000")
                        self.emergency_stop()
                        return

                # 超时
                if time.time() - t0 > timeout:
                    print(f"🛑 运动超时 ({timeout}s)")
                    self.emergency_stop()
                    return

                time.sleep(0.05)  # 20Hz

        self._monitor = threading.Thread(target=monitor, daemon=True)
        self._monitor.start()

        try:
            result = func()
        finally:
            self._stop_flag.set()

        return result

    def emergency_stop(self):
        """紧急停止: 所有舵机立即卸力"""
        self.ctrl.stop()
        print("🛑 紧急停止 — 所有关节扭矩已卸载")

    def soft_stop(self):
        """软停止: 速度归零 → 短暂保持 → 卸力"""
        for i in range(1, 7):
            self.ctrl.dev.write2ByteTxRx(i, 0x2E, 0)  # 速度归零
        time.sleep(0.5)
        self.ctrl.stop()

    def post_verify(self, target_joints: dict, tolerance=2.0):
        """运动后验证到位精度"""
        actual = self.ctrl.get_all_positions()
        for name, target in target_joints.items():
            error = abs(actual.get(name, 0) - target)
            if error > tolerance:
                print(f"⚠️ {name} 到位偏差 {error:.1f}° (容差 {tolerance}°)")
```

### 9.5 安全原则总结

1. **LLM 不直接输出舵机角度** — 所有 LLM 输出必须经过安全验证层翻译为关节指令
2. **先软限位, 再硬限位** — 软件层面先拦截, 舵机固件限位做兜底
3. **每次运动前上力, 运动后卸力** — 空闲状态不保持扭矩, 省电+安全
4. **紧急停止不可逆** — arm_stop() 后必须人工确认才能恢复
5. **任何异常优先停止** — 宁愿误触发安全停止, 也不能漏过真实碰撞
6. **儿童安全** — 工作空间定义必须排除儿童头部/手部可能出现的区域; 所有自动运动限制在 "safe" 模式速度 (20%)

---

## 十、芯伴 X1 综合控制框架

### 10.1 顶层架构

```python
#!/usr/bin/env python3
"""
芯伴X1 顶层控制器 — 整合 Arm + Safety + Voice + Music + LLM
"""

class X1Controller:
    """芯伴X1 总控 — 五层架构的执行层"""

    def __init__(self, arm_port="/dev/ttyACM0"):
        # 底层
        self.arm = SOARM101Controller(arm_port)

        # 安全层 (必经之路)
        self.safety = SafetyLayer(self.arm)

        # 音频层
        self.audio = AudioManager()

        # 任务注册表
        self.tasks = {
            "home":         self._task_home,
            "pick_place":   self._task_pick_place,
            "sort":         self._task_sort,
            "point_to":     self._task_point_to,
            "wave":         self._task_wave,       # 挥手
            "nod":          self._task_nod,         # 点头 (底座旋转)
        }

    # ── LLM Tool Calling 接口 ──

    def arm_reset(self):
        """重置机械臂到安全初始姿态"""
        return self._run_safe("arm_reset", self.arm.reset)

    def arm_stop(self):
        """紧急停止"""
        self.safety.emergency_stop()
        self.audio.emergency("紧急停止")
        return {"status": "stopped"}

    def arm_point_to(self, zone: str):
        """指向某个区域 (学习卡指读)"""
        zones = {
            "左前": (0.1, 0.15, 0.1),
            "右前": (0.1, -0.15, 0.1),
            "正前": (0.2, 0.0, 0.1),
        }
        xyz = zones.get(zone, zones["正前"])
        return self._run_task("point_to", xyz)

    def arm_pick_and_place(self, from_zone: str, to_zone: str):
        """从 A 区域拾取, 放置到 B 区域"""
        return self._run_task("pick_place",
                              pick_zone=zones[from_zone],
                              place_zone=zones[to_zone])

    def arm_execute_policy(self, policy_id: str):
        """执行 LeRobot 训练好的策略"""
        # 通过 Arm Bridge HTTP 调用 LeRobot 环境
        pass

    # ── 内部方法 ──

    def _run_task(self, task_name, **params):
        """运行注册任务 + 完整音频包装"""
        task_fn = self.tasks.get(task_name)
        if not task_fn:
            self.audio.voice.speak(f"未知任务: {task_name}")
            return {"error": "unknown_task"}

        self.audio.start_task(task_name, music_file="assets/bgm/task.wav")

        try:
            result = self.safety.with_monitor(lambda: task_fn(**params))
            self.audio.end_task(task_name, success=True)
            return {"status": "ok", "result": result}
        except Exception as e:
            self.audio.end_task(task_name, success=False)
            self.safety.emergency_stop()
            return {"status": "error", "message": str(e)}

    # ── 预定义任务 ──

    def _task_wave(self):
        """挥手 (交互演示)"""
        self.arm.reset()
        for _ in range(3):
            self.arm.move_joints({"shoulder_pan": 30, "elbow_flex": -20}, speed=1800)
            self.arm.wait()
            self.arm.move_joints({"shoulder_pan": -30}, speed=1800)
            self.arm.wait()
        self.arm.reset()

    def _task_nod(self):
        """点头 (J1 底座来回旋转)"""
        self.arm.reset()
        for _ in range(2):
            self.arm.move_joints({"shoulder_pan": 20}, speed=1500)
            self.arm.wait()
            self.arm.move_joints({"shoulder_pan": -20}, speed=1500)
            self.arm.wait()
        self.arm.reset()
```

### 10.2 与 LLM Agent 的交互流程

```
用户语音: "小芯, 帮我把那个红色积木放到左边"
    │
    ▼
LLM (DeepSeek-V4-Flash)
    │ Tool Calling
    ▼
{
  "name": "arm_pick_and_place",
  "parameters": {
    "from_zone": "正前",
    "to_zone": "左前"
  }
}
    │
    ▼
X1Controller.arm_pick_and_place("正前", "左前")
    │
    ├── audio.start_task("拾取放置")
    │
    ├── safety.pre_check(joints)     ← 关节限位/温度/电流基线
    │
    ├── safety.with_monitor(motion)   ← 20Hz 电流监控 + 超时保护
    │       │
    │       ├── arm.move_joints(approach)   ← 接近
    │       ├── audio.announce("接近目标")  ← 语音 (音乐自动降低)
    │       ├── arm.move_joints(grasp)      ← 夹取
    │       ├── audio.play_sfx("grab.wav")  ← 音效
    │       ├── arm.move_joints(lift)       ← 抬升
    │       ├── arm.move_joints(transport)  ← 搬运
    │       ├── arm.move_joints(place)      ← 放置
    │       └── arm.move_joints(retract)    ← 退回
    │
    ├── safety.post_verify(target_joints)
    │
    └── audio.end_task("拾取放置", success=True)
    │
    ▼
返回 LLM: {"status": "ok"}
    │
    ▼
LLM 生成回复: "好的, 我已经把红色积木放到左边了~"
    │
    ▼
TTS 播报 → 用户听到
```

---

## 附录 A: 快速参考卡片

### 舵机寄存器速查

```
上力:     WRITE ID 0x28 0x01
卸力:     WRITE ID 0x28 0x00
设位置:   WRITE ID 0x2A 0x[Lo] 0x[Hi]
设速度:   WRITE ID 0x2E 0x[Lo] 0x[Hi]
读位置:   READ  ID 0x38 0x02
读负载:   READ  ID 0x3C 0x02
读温度:   READ  ID 0x3F 0x01
读运动:   READ  ID 0x42 0x01
调PID:   WRITE ID 0x15 P 0x16 D 0x17 I
```

### ser 常用波特率

```
0 → 1,000,000 (1 Mbps, 默认)
1 → 500,000
3 → 250,000
4 → 115,200
```

### SYNC_WRITE 多舵机位置 (帧格式)

```
FF FF FE [Len] 83 2A 02 [ID1 PosL PosH] [ID2 PosL PosH] ... [Cksum]
```

---

## 附录 B: 芯伴 X1 项目文件索引

| 文件 | 说明 |
|------|------|
| `芯伴X1_完整方案与Codex协作交接.md` | 项目基线文档 |
| `SO-ARM101_技术调研与连接检测报告.md` | 本系列第1篇 — 硬件摸底 |
| `SO-ARM101_完整控制指南.md` | 本文档 — 控制指南 |
| `audio_sweep.py` | 变声器 (espeak-ng + scipy) |
| `rvc_vc.py` | WORLD 声码器变声 |
| `voice_profile.py` | 音色指纹提取器 |
| `voice_profiles/` | 音色配置目录 |

---

> **下一步行动**: 将机械臂物理连接到 SC171 USB 口 → `ls /dev/ttyACM*` → `python3 -c "from scservo_sdk import *; ... "` → 确认 6 个舵机全部在线 → 从 `arm_reset()` 和 `arm_stop()` 开始编写安全原语。
