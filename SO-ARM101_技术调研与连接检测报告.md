# SO-ARM101 机械臂 — 技术调研与连接检测报告

> **生成日期**: 2026-06-13
> **设备**: SC171 开发套件 V3 (Ubuntu 20.04 / aarch64)
> **项目**: 芯伴 X1 — 边云协同具身 AI 陪伴机器人

---

## 一、连接检测结果

### 1.1 当前系统 USB/串口状态

| 检测项 | 结果 |
|---|---|
| USB 串口设备 | **未检测到** — 无 `/dev/ttyUSB*` 或 `/dev/ttyACM*` 设备 |
| 系统串口 | 仅有 Qualcomm 平台内置串口 (`ttyHS0-8`, `ttyMSM0`, `ttyGS0-1`) |
| USB 设备 | 检测到 `QinHeng Electronics USB Single Serial` (VID=1a86, PID=55d3) — 此为 CH34x USB 转串口芯片，但未映射为 `/dev/ttyUSB*` |
| pyserial | ✅ 已安装 |
| 机械臂物理连接 | ❌ **SO-ARM101 机械臂当前未通过 USB 连接到本机** |

### 1.2 结论

**SO-ARM101 机械臂当前未连接到 SC171 开发板**。系统中检测到的 CH34x 串口芯片（VID=1a86, PID=55d3）可能是 SC171 自带调试串口或其他外设，而非机械臂驱动板。

机械臂连接后预期出现：
- `/dev/ttyUSB0` 或 `/dev/ttyACM0`（取决于驱动板固件）
- 或通过 `/dev/serial/by-id/usb-*` 符号链接识别

---

## 二、SO-ARM101 产品概述

### 2.1 基本信息

SO-ARM101 是由 **Waveshare（微雪电子）** 与 **HuggingFace LeRobot Studio** 联合推出的 **开源 6 轴桌面机械臂套装**，采用 **Leader-Follower（主从臂）** 遥操作架构，专为 **模仿学习与具身智能** 研究设计。

| 属性 | 详情 |
|---|---|
| **品牌/厂商** | Waveshare 微雪电子 / Hiwonder（幻尔） |
| **自由度** | 6 DoF × 2 臂（Leader + Follower，共 12 个舵机） |
| **舵机型号** | **STS3215** 串行总线舵机（TTL 半双工） |
| **舵机扭矩** | Follower 臂 12V 供电，堵转扭矩 **30 kg·cm**（Pro 版）/ 标准版 15 kg·cm |
| **编码器** | 12 位磁编码器（4096 分辨率），支持角度回读 |
| **舵机通信** | TTL 串行总线，波特率 **1 Mbps** |
| **上位机接口** | **USB-C → UART**（通过专用舵机驱动板） |
| **供电** | 12V DC（Follower）/ 7.4V（Leader，USB 供电可） |
| **结构件** | 光敏树脂 3D 打印（STL 文件完全开源） |
| **工作范围** | 臂展约 280mm，最大负载约 200g |
| **相机套件** | 可选 USB 相机（用于视觉模仿学习） |

### 2.2 主从臂架构

```
┌─────────────────────────────┐
│  Leader Arm (主臂/示教臂)    │  ← 人手拖动遥操作
│  舵机 ID: 7-12              │    记录关节角度
│  工作模式: 力矩回读          │
└─────────────┬───────────────┘
              │ USB-C → PC (LeRobot 数据采集)
              │
┌─────────────▼───────────────┐
│  Follower Arm (从臂/执行臂)  │  ← 训练后自主执行
│  舵机 ID: 1-6               │    复现录制动作
│  工作模式: 位置控制          │
└─────────────────────────────┘
```

---

## 三、通信协议

### 3.1 物理层

```
PC (Linux/Windows)
  │ USB-C
  ▼
舵机驱动板 (Waveshare 定制)
  │ TTL 半双工串行总线 (单线)
  ├── Servo ID=1 (Follower Base)
  ├── Servo ID=2 (Follower Shoulder)
  ├── ...
  ├── Servo ID=6 (Follower Wrist)
  ├── Servo ID=7 (Leader Base)
  ├── ...
  └── Servo ID=12 (Leader Wrist)
```

### 3.2 STS3215 舵机通信协议

- **物理接口**: TTL 半双工异步串行（单线总线，所有舵机共享）
- **波特率**: 1 Mbps（默认，可通过指令修改）
- **数据位**: 8
- **停止位**: 1
- **校验**: 无/偶校验
- **帧格式**: 自定义指令包，包含：
  - 帧头（Header）
  - 舵机 ID（1 字节）
  - 指令长度
  - 指令类型（读/写）
  - 寄存器地址
  - 数据 payload
  - 校验和（Checksum）

**常用指令**:
| 功能 | 说明 |
|---|---|
| `PING` | 检测舵机在线 |
| `WRITE_POSITION` | 设置目标角度（0-4095 对应 0-360°） |
| `READ_POSITION` | 回读当前角度 |
| `WRITE_SPEED` | 设置转速 |
| `WRITE_TORQUE_ENABLE` | 使能/禁用扭矩输出 |
| `READ_TEMP/VOLTAGE` | 读取温度/电压 |

### 3.3 上位机串口识别

连接机械臂驱动板后，Linux 下预期行为：
```bash
# 查看串口设备
ls /dev/ttyUSB* /dev/ttyACM*
# 或
ls /dev/serial/by-id/

# 赋予权限
sudo chmod 666 /dev/ttyUSB0
```

---

## 四、软件开发框架

### 4.1 LeRobot 框架（核心）

SO-ARM101 **不提供传统独立 SDK**，完全依赖 **HuggingFace LeRobot** 框架：

```
LeRobot (Python / PyTorch)
├── 数据采集层 — Leader 遥操作 → 记录关节角度 + 摄像头
├── 训练层 — ACT / Diffusion Policy 等模仿学习算法
└── 推理层 — 训练模型 → Follower 自主执行
```

**安装**:
```bash
git clone https://github.com/huggingface/lerobot.git
cd lerobot
pip install -e .
```

**核心工作流**:
```bash
# 1. 数据采集（人手拖动 Leader 臂记录轨迹）
python lerobot/scripts/control_robot.py record \
    --robot-path lerobot/configs/robot/so_arm100.yaml

# 2. 模型训练（ACT 策略）
python lerobot/scripts/train.py \
    --policy act \
    --dataset.path /path/to/dataset

# 3. 策略部署（Follower 自主执行）
python lerobot/scripts/control_robot.py replay \
    --robot-path lerobot/configs/robot/so_arm100.yaml \
    --pretrained-model /path/to/checkpoint
```

### 4.2 Python API 示例

LeRobot 中控制 SO-ARM101 的典型代码：

```python
from lerobot.common.robot_devices.robots.so_arm100 import SoArm100Robot

# 初始化机械臂
robot = SoArm100Robot(
    port="/dev/ttyUSB0",       # 串口路径
    servo_ids=[1,2,3,4,5,6],  # Follower 舵机 ID
    calibration_path="calibration.json"
)

# 连接
robot.connect()

# 读取当前关节角度
positions = robot.read("present_position")
print(f"关节角度: {positions}")

# 设置目标位置（范围 0-4095）
goal_positions = [2048, 1500, 2000, 1800, 2048, 1000]
robot.write("goal_position", goal_positions)

# 断开连接
robot.disconnect()
```

### 4.3 依赖环境

| 组件 | 要求 |
|---|---|
| Python | ≥ 3.10（LeRobot 官方）/ ≥ 3.8（部分兼容） |
| PyTorch | ≥ 2.0 |
| pyserial | 最新版 |
| 操作系统 | Ubuntu 20.04+ / Windows 10+ / macOS |
| CUDA | 推荐（训练用，推理可不需） |

> ⚠️ 芯伴 X1 项目当前环境为 Python 3.8，LeRobot 主线要求 ≥ 3.10。文档建议通过 **Arm Bridge (FastAPI)** 隔离机械臂环境与 SC171 AI 环境，即：机械臂控制跑在独立 Python 3.10+ 容器/PC，SC171 通过 HTTP API 调用。

---

## 五、官方资源索引

### 5.1 文档与资料

| 资源 | 链接 |
|---|---|
| **Waveshare Wiki（中文/英文）** | https://www.waveshare.net/wiki/SO-ARM100/101 |
| **GitHub 开源仓库（3D 文件+组装手册）** | https://github.com/EmbodiedAI-Group/SO-ARM101-6DoF |
| **LeRobot 官方框架** | https://github.com/huggingface/lerobot |
| **Waveshare 产品页（购买+教程）** | https://www.waveshare.net/shop/SO-ARM101-CAM-Kit-SE.htm |
| **Seeed Studio Wiki（LeRobot + SO-ARM）** | https://wiki.seeedstudio.com/cn/lerobot_so100m/ |
| **Hiwonder 用户手册** | https://docs.hiwonder.com/projects/LeRobot/en/latest/docs/SO-ARM101%20Open-Source%206-Axis%20Robotic%20Arm%20User%20Manual.html |
| **CNX Software 评测** | https://www.cnx-software.com/2025/05/02/so-arm101-open-source-dual-robotic-arm-kit-works-with-hugging-faces-lerobot/ |
| **Hackster 硬件详解** | https://www.hackster.io/HiwonderRobot/exploring-the-so-arm101-a-hardware-optimized-platform-de637e |
| **硬件技术规格详解** | https://en.hwlibre.com/Technical-features-and-advanced-details-of-the-SO-ARM101-robot |
| **什么值得买 组装教程（中文）** | https://post.smzdm.com/p/al3gz39g/ |
| **21ic 使用教程（中文）** | https://www.21ic.com/a/997974.html |

### 5.2 社区与支持

- **HuggingFace Discord** — LeRobot 频道，全球开发者互助
- **Waveshare 官方技术支持** — 产品页联系客服
- **GitHub Issues** — [SO-ARM101-6DoF](https://github.com/EmbodiedAI-Group/SO-ARM101-6DoF/issues)

---

## 六、芯伴 X1 项目集成要点

### 6.1 当前架构中的角色

```
SC171 (芯伴X1 主控)
  ├── 感知层 → 语音/视觉/记忆
  ├── LLM 规划层 → DeepSeek-V4-Flash
  ├── 安全验证层 → 工作空间检查、力矩限位
  │     │
  │     ▼ HTTP API (Arm Bridge)
  │   ┌─────────────────────┐
  │   │  Arm Bridge (FastAPI) │  ← 独立 Python 3.10+ 环境
  │   │  /arm/status           │
  │   │  /arm/reset            │
  │   │  /arm/execute_policy   │
  │   │  /arm/point_to         │
  │   └──────────┬─────────────┘
  │              │ LeRobot / pyserial
  │              ▼
  │   SO-ARM101 Follower Arm
  │   (/dev/ttyUSB0)
  └───────────────────────────
```

### 6.2 LLM Tool Calling 接口

芯伴 X1 已规划的机械臂工具（来自方案文档）:

```json
{"name": "arm_reset", "description": "重置机械臂到安全初始位姿"}
{"name": "arm_stop", "description": "紧急停止所有舵机"}
{"name": "arm_point_to", "parameters": {"zone": "左前/右前/正前"}}
{"name": "arm_pick_from_zone", "parameters": {"zone": "区域标识"}}
{"name": "arm_place_to_zone", "parameters": {"zone": "区域标识"}}
{"name": "arm_pick_and_place", "parameters": {"from_zone": "...", "to_zone": "..."}}
{"name": "arm_execute_policy", "parameters": {"policy_id": "策略ID", "task": "任务描述"}}
```

### 6.3 待办事项（M0 硬件摸底阶段）

- [ ] 将 SO-ARM101 驱动板通过 USB-C 连接到 SC171
- [ ] 确认 `/dev/ttyUSB0` 或 `/dev/ttyACM0` 出现
- [ ] 测试 pyserial 与舵机驱动板的基本通信（PING 指令）
- [ ] 搭建 Arm Bridge (FastAPI) 独立环境（Python 3.10+）
- [ ] 安装 LeRobot 并跑通 `control_robot.py` 基础流程
- [ ] 校准 12 个舵机 ID 和初始零位
- [ ] 实现 `arm_reset` / `arm_stop` 两个安全基础原语
- [ ] 与 LLM Agent 联调 Tool Calling 通路

---

## 七、关键风险与注意事项

1. **Python 版本不兼容**: SC171 自带 Python 3.8，LeRobot 需要 ≥ 3.10。建议通过 Arm Bridge 隔离，不要升级系统 Python。
2. **舵机 ID 必须预配置**: 12 个舵机出厂 ID 可能不是 1-12，需使用舵机调试工具逐一设置。
3. **安全第一**: LLM **不能**直接输出舵机角度。所有机械臂动作须经过安全验证层（工作空间范围检查 + 力矩限位 + 速度限制）。
4. **串口权限**: Linux 下首次使用需 `sudo chmod 666 /dev/ttyUSB*` 或配置 udev 规则。
5. **驱动板兼容性**: 确保驱动板固件与 LeRobot 版本匹配，固件升级需参考 Waveshare Wiki。
6. **模仿学习数据质量**: Leader-Follower 数据采集质量直接影响模型表现，录数据时需保持操作一致性。

---

> **下一步**: 将机械臂物理连接到 SC171，执行 `ls /dev/ttyUSB*` 确认设备出现，然后按 6.3 节逐步推进。
