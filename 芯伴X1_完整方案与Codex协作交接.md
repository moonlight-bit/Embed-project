# 芯伴 X1 完整方案与 Codex 协作交接

> 文档用途：作为团队成员及其 Codex 的统一项目基线。后续设计、代码、机械结构、模型训练、答辩材料均应以此文档为起点，并通过明确的变更记录更新，不要各自重新发散。
>
> 文档版本：v0.1  
> 更新时间：2026-06-11  
> 当前阶段：总体方案确定，等待硬件摸底、环境搭建和模块原型验证。

---

# 1. 已确认信息

以下信息已经由团队确认，可视为当前项目约束：

1. 竞赛方向为广和通 AIoT 行业场景命题中的“AI 玩具与 AI 陪伴桌面机器人”。
2. 主控平台为广和通 SC171 开发套件 V3。
3. 团队已经收到 SO-ARM101 六轴桌面机械臂套装。
4. 机械臂套装包含 leader arm，可进行 leader-follower 遥操作和 LeRobot 数据采集。
5. 比赛现场可以联网，因此云端大模型可以作为主力能力之一。
6. 产品目标用户为儿童和学生。
7. 团队对软硬件、前后端和模型训练暂时没有固定人员限制，可以按模块重新分工。
8. 产品不强制采用毛绒材质，当前更倾向于圆润、亲和、易清洁的软质或类软质机器人外观。

仍待确认的信息：

- 参赛组别是高职、本科还是研究生。
- 最终比赛和作品提交时间。
- SC171 V3 实机当前系统版本、Python 版本和可用 SDK。
- SO-ARM101 卖家提供的控制板型号、舵机型号、串口协议、SDK 和校准状态。
- 是否已经配备显示屏、麦克风、扬声器、摄像头和独立急停。
- 团队可用于训练的 GPU 型号和显存。
- 整机尺寸、预算和外观加工条件。

---

# 2. 赛题审题与项目定位

## 2.1 官方题眼

项目必须主动回应以下关键词，而不是只做一个会聊天的外壳：

- SC171 V3
- AIoT
- 端侧 AI
- 边云协同
- 语音识别与语音合成
- 角色化聊天
- 多模态环境感知
- Agent 决策规划
- Function Calling
- 用户识别与长期记忆
- 实体动作执行
- 响应时延可量化

官方重点指标之一是：

```text
t = 用户语句结束到 TTS 播报第一个字之间的时间
```

作品界面必须实时显示该时间，精度到 0.001 秒。目标为 `t <= 2s`，最低应稳定控制在 `t <= 4s`。

## 2.2 项目名称

推荐正式名称：

**芯伴 X1：面向儿童与学生学习桌的边云协同具身 AI 陪伴机器人**

可用于产品传播的简称：

**小芯**

## 2.3 一句话定义

芯伴 X1 是一款基于 SC171 V3 的软体陪伴桌面机器人。它通过语音、视觉、长期记忆和大模型 Agent 理解用户需求，并调用 SO-ARM101 执行学习卡指读、物品指引和轻量递送，实现从感知、理解、规划到实体行动的完整 AIoT 闭环。

## 2.4 统一场景叙事

为了避免“儿童玩具”和“创客机械臂”像两个拼接项目，统一使用“成长型学习桌伙伴”叙事。

产品包含两种模式，但仍是同一个学习桌场景：

### 儿童模式

- 学习卡指读
- 故事生成与续讲
- 情绪陪伴
- 专注计时
- 喝水和休息提醒
- 家长端使用管理

### 学生与创客模式

- 创客元件识别
- LED、电阻、杜邦线和开发板指引
- 学习任务拆解
- 实验步骤说明
- 学习记录和复盘
- 机械臂递送轻量卡片或元件盒

项目不要将自己描述为医疗、心理诊断或代替家长/教师的系统。情绪识别仅用于改善交互语气和触发普通关怀。

---

# 3. 产品形态

## 3.1 推荐结构

```text
圆润软体机器人本体
        +
智能底座
        +
SO-ARM101 外置执行机械臂
```

机器人本体负责：

- 角色形象
- LED 表情
- 摄像头
- 麦克风
- 扬声器
- 触摸交互
- 轻微点头、摆动等陪伴动作

智能底座负责：

- SC171 V3 安装
- 散热
- 电源管理
- 状态显示屏
- 网络和 USB 接口
- 舵机控制与通信
- 硬件展示

SO-ARM101 负责：

- 指向学习卡
- 指向手机收纳区
- 指向创客元件
- 抓取和递送轻量卡片
- 执行通过 LeRobot 学习的特定任务

## 3.2 材质建议

竞赛原型不建议直接挑战全硅胶成型，优先考虑：

1. 3D 打印圆润骨架和外壳。
2. 外壳使用白色哑光喷涂。
3. 头部和接触区域增加硅胶、TPU 或 EVA 软垫。
4. 所有边角圆角化。
5. SC171 与电源全部放在底座中。

---

# 4. 总体技术架构

```text
麦克风 / 摄像头 / 触摸 / 手机端
                |
                v
SC171 V3 设备运行时
  - ASR / TTS
  - 视觉感知
  - 用户识别
  - 本地记忆
  - 上下文构建
  - Agent 调度
  - 屏幕和 LED
                |
       HTTPS / MQTT / WebSocket
                |
                v
云端平台
  - DeepSeek 模型代理
  - Tool Calling
  - 内容安全
  - 设备管理
  - 记忆同步
                |
                v
SC171 Tool Executor
                |
         HTTP / LAN / Wi-Fi
                |
                v
Arm Bridge + LeRobot
                |
                v
SO-ARM101 follower
```

核心原则：

1. LLM 负责理解、规划和选择工具。
2. 视觉模块负责描述环境，不让 LLM 猜测物体是否存在。
3. 安全层负责校验动作是否合法。
4. 机械臂技能层负责稳定执行。
5. LLM 不直接输出舵机角度。
6. 儿童敏感图像尽量只在端侧处理。
7. 云端模型故障时，设备仍可完成基础语音、视觉、记忆和预设动作。

---

# 5. 分层智能架构

项目不能退化为“字符串包含某关键词就调用某动作”。建议使用五层架构。

## 5.1 感知层

输入：

- ASR 文本
- 人脸身份
- 情绪类别
- 桌面物体列表
- 学习卡类别
- 物体位置
- 机械臂状态
- 当前模式

输出统一的 `SceneState`：

```json
{
  "user_id": "child_001",
  "mode": "maker",
  "emotion": "neutral",
  "objects": [
    {"id": "led_01", "class": "led", "zone": "led_area", "confidence": 0.94},
    {"id": "board_01", "class": "dev_board", "zone": "board_area", "confidence": 0.91}
  ],
  "arm": {
    "online": true,
    "busy": false,
    "calibrated": true
  }
}
```

## 5.2 上下文层

将以下信息组合为 LLM 输入：

- 用户当前语句
- SceneState
- 最近相关记忆
- 当前模式
- 可用工具清单
- 安全规则
- 角色人设

## 5.3 LLM 规划层

LLM 输出：

- 对用户说的话
- 简短计划摘要
- 结构化工具调用
- 是否需要二次观察
- 是否需要用户确认

## 5.4 安全验证层

所有工具调用必须通过：

- JSON Schema 验证
- 工具白名单
- 参数类型检查
- 目标区域存在性检查
- 机械臂工作空间检查
- 动作速度和负载检查
- 儿童距离检查
- 急停状态检查

## 5.5 执行层

执行层负责：

- TTS
- LED 表情
- 计时器
- 记忆保存
- MQTT 上报
- 机械臂技能
- LeRobot 策略

---

# 6. 推荐技术栈

## 6.1 SC171 V3 设备端

基于现有赛题资料，初步采用：

```text
OS：Ubuntu 20.04
主语言：Python 3.8
AI 工具链：Fibo AI Stack
机器人环境：ROS 2 Galactic，仅按需使用
本地数据库：SQLite
图像处理：OpenCV
通用模型推理：ONNX Runtime 或 Fibo AI Stack
设备通信：paho-mqtt + httpx/requests
状态界面：PyQt5、Qt 或本地 Web UI
日志：structlog / logging
配置：YAML + Pydantic/dataclass
```

注意：

- SC171 当前真实系统和依赖版本必须以实机为准。
- 不要在 SC171 主 Python 环境中盲目升级 PyTorch、NumPy 或系统库。
- 每个模型都先做独立环境验证，再集成到主运行时。

## 6.2 云端 LLM

主力候选：

```text
DeepSeek-V4-Flash
```

用途：

- 自然语言理解
- 儿童友好回复
- 学习任务规划
- 创客知识解释
- Tool Calling
- 对话和故事摘要

要求：

- 模型名称写入配置，不硬编码。
- 上线前重新确认官方可用模型和价格。
- API Key 只保存在云端，不写入 SC171 固件或前端。
- 使用流式响应，收到第一段可播报文本后立即启动 TTS。

端侧研发候选：

```text
MiniCPM5-1B
```

用途：

- 简单意图路由
- 网络故障下的短回复
- 工具调用初筛

兜底候选：

```text
SC171 官方已经适配的 Qwen3-0.6B / 1.7B
```

端侧小模型不是 MVP 的硬依赖。必须先验证模型格式、内存占用、首 token 时延和 Fibo AI Stack 兼容性。

## 6.3 语音

```text
ASR：FiboASR 优先，Whisper-tiny 作为验证或兜底
TTS：FiboTTS-meloTTS 优先
VAD：WebRTC VAD、Silero VAD 或官方例程
音频：PyAudio / sounddevice / ALSA
```

性能优化：

1. VAD 检测到结束后立即开始 ASR 收尾。
2. 云端 LLM 使用流式输出。
3. TTS 按短句或标点分块合成。
4. 不等待完整回答后再播音。
5. 记录每一阶段耗时。

建议记录：

```text
t_vad_end
t_asr_done
t_llm_request
t_llm_first_token
t_tts_request
t_first_pcm
```

官方指标：

```text
t = t_first_pcm - t_vad_end
```

## 6.4 视觉

稳定优先组合：

```text
ArUco / AprilTag：固定区域和学习卡定位
YOLO：物品类别检测
MediaPipe Face / 官方人脸模型：人脸检测
InsightFace / ArcFace：用户身份识别
轻量分类器或规则融合：表情与疲劳状态
```

第一版类别：

```text
phone
book
pen
water_cup
learning_card
led
resistor
dev_board
breadboard
jumper_wire
```

情绪模块只输出普通交互标签：

```text
happy
neutral
tired
sad_like
```

不要宣传为心理诊断。

## 6.5 SO-ARM101 与 LeRobot

建议环境放在独立笔记本或小主机：

```text
Ubuntu 22.04 优先
Miniforge/Conda
LeRobot 官方要求的 Python 版本
PyTorch + CUDA
Feetech SDK
OpenCV
FastAPI Arm Bridge
```

原因：

- LeRobot 主线依赖版本较新。
- SC171 官方 Python 环境较旧。
- 训练和数据采集需要 GPU、摄像头和较大的磁盘。
- 机械臂底层环境与 SC171 AI 环境隔离更稳。

## 6.6 云端

```text
API：FastAPI
数据库：PostgreSQL
缓存和任务状态：Redis
IoT 通信：EMQX MQTT
实时推送：WebSocket
反向代理：Nginx
部署：Docker Compose
对象存储：MinIO 或云 OSS/COS
```

## 6.7 网页端

```text
Vue 3
TypeScript
Vite
Element Plus
ECharts
WebSocket / MQTT over WebSocket
```

## 6.8 手机端

竞赛阶段推荐：

```text
uni-app 或微信小程序
TypeScript
HTTPS API
WebSocket
```

后续产品化可迁移至 Flutter。

---

# 7. 推荐仓库结构

建议使用 monorepo：

```text
xiban-x1/
├── README.md
├── docs/
│   ├── architecture.md
│   ├── hardware.md
│   ├── api.md
│   ├── safety.md
│   └── adr/
├── device-sc171/
│   ├── src/
│   │   ├── audio/
│   │   ├── vision/
│   │   ├── agent/
│   │   ├── memory/
│   │   ├── tools/
│   │   ├── cloud/
│   │   └── ui/
│   ├── config/
│   ├── scripts/
│   └── tests/
├── arm-bridge/
│   ├── app/
│   ├── skills/
│   ├── policies/
│   ├── calibration/
│   ├── scripts/
│   └── tests/
├── cloud-api/
│   ├── app/
│   ├── migrations/
│   ├── tests/
│   └── docker/
├── web-dashboard/
├── mobile-app/
├── model-training/
│   ├── vision/
│   ├── emotion/
│   └── lerobot/
├── datasets/
│   └── README.md
└── deployment/
    ├── docker-compose.yml
    └── nginx/
```

建议分支：

```text
main
develop
feature/device-audio
feature/device-vision
feature/agent
feature/arm
feature/cloud
feature/web
feature/mobile
```

---

# 8. SC171 设备端模块

## 8.1 AudioService

职责：

- 麦克风采集
- VAD
- ASR
- TTS
- 音频播放
- 时延计时

接口：

```python
class AudioService:
    def listen_once(self) -> AudioUtterance: ...
    def transcribe(self, audio: AudioUtterance) -> str: ...
    def speak_stream(self, text_stream) -> None: ...
```

## 8.2 VisionService

职责：

- 摄像头采集线程
- 人脸检测
- 用户识别
- 表情标签
- 学习卡识别
- 桌面物品识别
- ArUco/AprilTag 定位

接口：

```python
class VisionService:
    def latest_scene(self) -> SceneState: ...
    def find_object(self, object_class: str) -> DetectedObject | None: ...
    def identify_user(self) -> UserIdentity | None: ...
```

## 8.3 MemoryService

职责：

- 用户档案
- 最近对话摘要
- 学习任务
- 故事进度
- 情绪交互摘要
- 云端同步

接口：

```python
class MemoryService:
    def retrieve(self, user_id: str, query: str, limit: int = 5): ...
    def save_turn(self, turn): ...
    def save_fact(self, user_id: str, fact): ...
    def delete_user_data(self, user_id: str): ...
```

## 8.4 ContextBuilder

职责：

- 汇总语音、视觉、记忆、模式和设备状态。
- 限制上下文长度。
- 只向 LLM 提供已确认的物体和安全区域。

## 8.5 AgentClient

职责：

- 调用云端 LLM Agent。
- 接收流式文字和 Tool Calls。
- 网络失败时切换本地策略。

## 8.6 ToolValidator

职责：

- JSON Schema 验证。
- 工具白名单验证。
- 机械臂状态验证。
- 儿童安全验证。
- 高风险动作要求用户确认。

## 8.7 ToolExecutor

职责：

- TTS、LED、计时器、记忆和机械臂工具执行。
- 工具执行结果回传给 LLM 或网页端。

## 8.8 StatusUI

答辩界面至少显示：

```text
ASR 文本
当前用户
情绪标签
视觉物体
记忆命中
当前模型
计划摘要
Tool Calls
机械臂状态
端到端响应时延
```

---

# 9. LLM Agent 设计

## 9.1 工具清单

基础工具：

```text
set_mode(mode)
set_study_timer(minutes)
set_light(emotion)
save_memory(type, content)
search_memory(query)
tell_story(theme, duration)
```

视觉工具：

```text
observe_scene()
find_object(object_class)
identify_card()
identify_user()
```

机械臂工具：

```text
arm_reset()
arm_stop()
arm_point_to(zone)
arm_pick_from_zone(zone)
arm_place_to_zone(zone)
arm_pick_and_place(from_zone, to_zone)
arm_execute_policy(policy_id, task)
```

## 9.2 Agent 返回格式

```json
{
  "reply": "可以，我们先准备开发板、LED、电阻和杜邦线。",
  "plan_summary": "根据桌面物体识别结果，依次指向实验所需元件。",
  "requires_confirmation": false,
  "tool_calls": [
    {
      "name": "arm_point_to",
      "arguments": {
        "zone": "board_area"
      }
    },
    {
      "name": "arm_point_to",
      "arguments": {
        "zone": "led_area"
      }
    }
  ]
}
```

## 9.3 安全规则

- 目标不在视觉结果或固定区域中时，不允许抓取。
- 用户手部进入机械臂工作区时暂停运动。
- 未完成校准时只允许 `arm_reset` 和 `arm_stop`。
- 不允许 LLM 设置舵机 ID、波特率或关节底层参数。
- 抓取任务必须限制允许物品类别和最大负载。
- 网络异常时终止新动作，不中断已经开始的安全复位。

---

# 10. SO-ARM101 硬件连接

## 10.1 推荐连接

```text
SO-ARM101 follower
  - 12V 5A 独立供电
  - USB 数据连接到 Arm Bridge 电脑

SO-ARM101 leader
  - 独立供电或按卖家说明供电
  - USB 数据连接到 Arm Bridge 电脑

机械臂摄像头
  - 训练阶段连接 Arm Bridge 电脑
  - 运行阶段可连接 SC171 或 Arm Bridge

SC171
  - LAN/Wi-Fi 连接 Arm Bridge
  - 不为机械臂舵机供电
```

## 10.2 必须增加

- 独立总电源开关。
- 机械臂急停按钮。
- 机械限位或软件限位。
- 底座防倾覆配重。
- 工作区边界标识。
- 用户手部检测或至少物理隔离区域。

---

# 11. Arm Bridge

Arm Bridge 是 SC171 和 LeRobot 之间的隔离层。

推荐 API：

```text
GET  /health
GET  /arm/status
POST /arm/reset
POST /arm/stop
POST /arm/point-to
POST /arm/pick-and-place
POST /arm/execute-policy
POST /arm/calibrate
```

请求示例：

```json
{
  "zone": "led_area",
  "speed": 0.25
}
```

返回示例：

```json
{
  "accepted": true,
  "task_id": "arm_task_1024",
  "state": "queued"
}
```

Arm Bridge 内部模块：

```text
LeRobotAdapter
ServoBusAdapter
SkillRegistry
PolicyRegistry
SafetyController
TaskQueue
CalibrationStore
CameraManager
```

---

# 12. 机械臂能力分级

## 12.1 Level 1：固定技能

必须实现，用于比赛保底：

- 回零
- 指向固定区域
- 从固定区域抓卡片
- 放置到固定区域
- 挥手或展示动作

动作由关节角序列或经过验证的轨迹组成。

## 12.2 Level 2：视觉参数化技能

增强功能：

- ArUco/AprilTag 定位桌面区域。
- YOLO 确认物体类别。
- 相机坐标映射到桌面坐标。
- 机械臂指向检测目标。

需要完成：

- 相机内参标定。
- 相机到桌面平面的单应性变换。
- 桌面坐标到机械臂基座坐标的外参标定。

## 12.3 Level 3：LeRobot 模仿学习

冲奖功能：

- leader-follower 遥操作。
- 采集真实任务 episode。
- 训练 ACT 等策略。
- 由 LLM 调用 `arm_execute_policy`。

推荐只训练两个清晰任务：

1. 从固定区域拿学习卡并放到展示区。
2. 从固定区域拿轻量元件盒并放到用户前方。

---

# 13. LeRobot 数据和训练流程

## 13.1 环境验证

1. 安装 LeRobot 和 Feetech 依赖。
2. 查找 leader/follower 串口。
3. 核对舵机 ID 和波特率。
4. 分别校准 leader 和 follower。
5. 完成 teleoperation。
6. 验证摄像头帧率和时间同步。

不要在未备份卖家配置前重新设置舵机 ID。

## 13.2 数据集设计

每个任务单独建数据集。

建议：

```text
50-100 episodes / task
每条 episode 10-30 秒
训练/验证/测试按用户和物体位置划分
摄像头位置固定
光照有适量变化
起始位置轻微随机
失败 episode 单独标记
```

记录内容：

- RGB 图像
- 关节位置
- 夹爪状态
- 时间戳
- 任务描述
- 成功/失败
- 异常原因

## 13.3 策略选择

优先：

```text
ACT
```

原因：

- 任务短而明确。
- leader-follower 数据适合模仿学习。
- 比端到端大型 VLA 更容易训练和解释。

SmolVLA 等策略作为后续研发，不作为主线依赖。

## 13.4 评估

每个策略至少测试 30 次：

- 成功率
- 平均执行时间
- 最大偏差
- 碰撞次数
- 需要人工干预次数

低于 85% 成功率的策略不能作为答辩唯一演示路径，必须保留固定技能替代。

---

# 14. 视觉模型训练

## 14.1 YOLO 数据集

初期每类目标：

```text
100-300 张有效图像
```

划分：

```text
train 70%
val 20%
test 10%
```

采集变化：

- 不同光照
- 不同桌面背景
- 不同角度
- 部分遮挡
- 距离变化

## 14.2 输出与部署

训练端：

```text
PyTorch / Ultralytics YOLO
```

导出：

```text
ONNX
```

部署顺序：

1. PC 上验证 ONNX 输出一致性。
2. SC171 上使用 ONNX Runtime 做基准。
3. 尝试转换到 Fibo AI Stack 支持格式。
4. 比较 FPS、延迟、内存和精度。

## 14.3 可靠性策略

抓取和指向任务不要只依赖 YOLO：

```text
YOLO 判断类别
+
ArUco/AprilTag 确认区域
+
机械臂固定安全轨迹
```

---

# 15. 记忆系统

## 15.1 本地记忆

SQLite 表建议：

```text
user_profile
conversation_summary
story_progress
learning_task
emotion_event
tool_execution_log
```

## 15.2 云端记忆

只同步：

- 用户配置
- 对话摘要
- 故事进度
- 学习任务
- 使用统计
- 情绪趋势摘要

默认不上传：

- 原始摄像头视频
- 原始人脸图片
- 完整连续录音
- 无必要的完整对话正文

## 15.3 记忆检索

MVP：

```text
SQLite + 关键词/时间/类别检索
```

增强：

```text
摘要向量化 + pgvector
```

系统至少展示 10 轮跨时间记忆的有效调用。

---

# 16. 儿童安全与隐私

必须实现：

- 家长绑定设备。
- 每日使用时长限制。
- 夜间禁用时段。
- 音量上限。
- 摄像头开关。
- 云端模型开关。
- 记忆查看和删除。
- 儿童不适内容过滤。
- 危险动作拒绝。

内容安全三层：

```text
输入过滤
系统 Prompt 约束
输出审核
```

机器人不能：

- 诱导孩子隐瞒家长。
- 提供危险实验操作。
- 进行医疗或心理诊断。
- 鼓励消费或泄露个人信息。
- 对严重负面情绪做确定性判断。

---

# 17. 云端模块

建议服务：

```text
AuthService
DeviceService
AgentService
ModelProxyService
MemoryService
SafetyService
TelemetryService
CommandService
```

数据库表：

```text
parent_user
child_profile
device
device_binding
device_config
conversation_summary
story_progress
learning_record
emotion_summary
model_call_log
tool_call_log
command_log
```

MQTT Topic：

```text
device/{device_id}/status
device/{device_id}/event
device/{device_id}/command
device/{device_id}/config
device/{device_id}/telemetry
```

---

# 18. 网页端

页面：

1. 设备总览。
2. 实时交互日志。
3. 视觉感知结果。
4. LLM 计划和 Tool Calls。
5. 机械臂任务队列。
6. 响应时延分解。
7. 用户记忆摘要。
8. 模型和 Prompt 配置。
9. 内容安全规则。
10. 系统测试数据看板。

答辩首页建议显示：

```text
ASR
Emotion
Objects
Memory Hit
LLM Model
Plan Summary
Tool Calls
Arm Status
Latency
```

---

# 19. 手机端

用户为家长和学生本人。

功能：

- 扫码绑定设备。
- 切换儿童、学习、创客、睡前、安静模式。
- 设置使用时间。
- 设置音量。
- 查看每日摘要。
- 管理故事偏好。
- 查看学习任务。
- 远程停止设备。
- 触发挥手、指读等低风险动作。
- 查看并删除记忆。

手机端不要展示开发日志和复杂模型参数。

---

# 20. 性能指标

| 指标 | 目标 |
|---|---:|
| 用户结束说话到首个 TTS 音频 | `<= 2.000s` 优先 |
| ASR 日常场景可用率 | `>= 90%` |
| 学习卡识别准确率 | `>= 90%` |
| 物品检测 mAP/业务准确率 | 按测试集记录 |
| 用户识别准确率 | `>= 90%` |
| LLM 工具选择正确率 | `>= 90%` |
| Tool Call 参数合法率 | `>= 98%` |
| 固定机械臂技能成功率 | `>= 95%` |
| LeRobot 策略任务成功率 | `>= 85%` |
| 急停生效时间 | 尽可能小于 500ms |
| 手机端命令响应 | `<= 3s` |
| 记忆跨时间调用 | `>= 10` 轮 |

所有指标必须有测试脚本和原始记录，不能只在 PPT 中手写。

---

# 21. 推荐演示流程

## 场景一：用户识别与记忆

```text
用户：小芯，我来了。
机器人：晚上好。你上次说今天要继续做 LED 点灯实验，我还记得。
```

展示：

- 人脸识别
- 记忆命中
- 响应时延

## 场景二：LLM 规划创客任务

```text
用户：我想做 LED 点灯，但不知道要准备什么。
```

系统：

1. 识别桌面物品。
2. LLM 根据任务和视觉结果生成计划。
3. TTS 说明所需元件。
4. 机械臂依次指向开发板、LED、电阻和杜邦线。

展示：

- SceneState
- Plan Summary
- Tool Calls
- Arm Status

## 场景三：学习卡指读

1. 摄像头识别学习卡。
2. LLM 根据年龄和卡片生成问题。
3. 机械臂指向卡片。
4. 用户回答后，机器人继续互动。

## 场景四：LeRobot 递卡

1. 用户请求一张故事卡或复习卡。
2. LLM 调用 `arm_execute_policy`。
3. 机械臂从固定区域取卡并放到展示区。
4. 失败时自动切换固定技能或给出提示。

## 场景五：情绪陪伴

1. 用户表达疲惫或失落。
2. 视觉仅提供辅助标签。
3. LLM 使用温和表达。
4. 本体改变灯光或轻微点头。
5. 不进行诊断。

---

# 22. 研发里程碑

## M0：硬件摸底

- SC171 系统和依赖清单。
- 麦克风、扬声器、摄像头和显示屏测试。
- SO-ARM101 leader/follower 遥操作。
- 卖家 SDK、协议和校准资料归档。

## M1：语音与云端 Agent

- ASR-TTS 闭环。
- DeepSeek 流式调用。
- Tool Calling JSON。
- 时延分解显示。

## M2：机械臂固定技能

- Arm Bridge。
- 急停。
- 回零、指向、固定抓放。
- SC171 到 Arm Bridge 的调用。

## M3：视觉与坐标系统

- ArUco/AprilTag。
- YOLO 第一版。
- 桌面坐标标定。
- 视觉结果输入 LLM。

## M4：记忆与产品模式

- 用户档案。
- 10 轮跨时间记忆。
- 儿童/学生/创客模式。
- 手机端 MVP。

## M5：LeRobot 模仿学习

- 数据采集。
- ACT 训练。
- 策略部署到 Arm Bridge。
- LLM 调用策略。

## M6：网页与云端完善

- 实时日志。
- 指标看板。
- 内容安全。
- 设备管理。

## M7：竞赛联调

- 断网降级。
- 机械臂失败降级。
- 现场演示脚本。
- 备用视频。
- 测试报告。

---

# 23. 建议团队分工

即使人员可以灵活安排，也建议确定责任人：

1. SC171 与语音负责人。
2. 视觉与模型部署负责人。
3. LLM Agent 与记忆负责人。
4. SO-ARM101 与 LeRobot 负责人。
5. 云端和数据库负责人。
6. 网页/手机端负责人。
7. 结构、电源和外观负责人。
8. 测试、文档和答辩负责人。

每个负责人都需要：

- 模块 README。
- 一键启动脚本。
- 测试脚本。
- 已知问题。
- 输入输出接口。

---

# 24. 主要风险

## 24.1 SC171 与 LeRobot 环境冲突

处理：LeRobot 放到独立 Arm Bridge 电脑，SC171 只调 API。

## 24.2 云端 LLM 延迟无法达到 2 秒

处理：

- 流式 LLM。
- 分句 TTS。
- 缩短系统 Prompt。
- 端侧 ASR/TTS。
- 常见意图使用本地路由，但不要伪装成 LLM 推理。

## 24.3 模仿学习成功率不足

处理：

- 保留固定技能。
- 限定任务和物体。
- 固定摄像头。
- 增加数据和失败样本。

## 24.4 机械臂儿童安全

处理：

- 机械臂定位为受控桌面执行器，不让儿童随意触摸。
- 降速、限力、急停、工作区检测。
- 只抓轻量物品。

## 24.5 方案范围过大

处理：比赛主线只承诺一个完整闭环：

```text
语音请求
→ 视觉识别
→ LLM 规划
→ Tool Calling
→ 机械臂指向/递卡
→ 状态展示
→ 记忆保存
```

其他功能作为模式扩展，不得影响主闭环稳定性。

---

# 25. 队友 Codex 接手规则

新的 Codex 接手时应先完成：

1. 阅读本文件和工作区三份 PDF。
2. 检查当前代码和硬件状态，不假设模块已经完成。
3. 将待做事项拆成可验证的小任务。
4. 每个关键技术选型记录 ADR。
5. 不得未经验证就宣称某模型可在 SC171 上运行。
6. 不得绕过安全层让 LLM 直接控制舵机。
7. 不得用字符串匹配替代 Agent，却在答辩中宣传为大模型决策。
8. 固定技能和模仿学习策略必须共存，保证降级。
9. 所有性能数据必须由脚本测量。
10. 修改总体架构时同步更新本文件。

建议队友 Codex 的第一条任务提示：

```text
请先阅读《芯伴X1_完整方案与Codex协作交接.md》和工作区三份广和通 PDF。
不要立即写大规模代码。
先检查当前仓库状态、硬件环境和依赖，输出你负责模块的：
1. 已确认条件；
2. 待验证条件；
3. 模块接口；
4. 两周内可完成的 MVP；
5. 测试和风险。
后续实现必须符合文档中的端云分层、LLM Tool Calling、安全校验和机械臂降级原则。
```

---

# 26. 参考资料

工作区官方资料：

- `芯片应用赛道选题指南 .pdf`
- `边缘AIoT开发套件V3（2026版）--20260203 (2).pdf`
- `【技术分享】全国大学生嵌入式芯片与系统设计竞赛'2026广和通--20260417.pdf`

外部官方资料：

- LeRobot：https://github.com/huggingface/lerobot
- LeRobot 安装：https://huggingface.co/docs/lerobot/main/en/installation
- SO-101：https://huggingface.co/docs/lerobot/main/en/so101
- LeRobot 真实机器人教程：https://huggingface.co/docs/lerobot/main/en/getting_started_real_world_robot
- DeepSeek Function Calling：https://api-docs.deepseek.com/guides/function_calling
- OpenCV ArUco：https://docs.opencv.org/4.x/d5/dae/tutorial_aruco_detection.html
- Ultralytics 训练：https://docs.ultralytics.com/modes/train/
- FastAPI：https://fastapi.tiangolo.com/
- EMQX MQTT over WebSocket：https://docs.emqx.com/en/emqx/latest/connect-emqx/mqtt-over-websocket.html

---

# 27. 最终定版摘要

项目最终不是：

- 一个简单聊天玩具。
- 一个只会关键词触发动作的机械臂。
- 一个全部依赖云端的语音壳。
- 一个高风险、无法稳定演示的端到端机器人模型。

项目最终应是：

```text
SC171 端侧语音与视觉感知
        +
用户身份和长期记忆
        +
云端国产 LLM Agent 规划
        +
结构化 Function Calling
        +
安全工具执行层
        +
SO-ARM101 固定技能与 LeRobot 模仿学习
        +
网页端技术展示
        +
手机端用户与家长控制
```

比赛主线目标：

> 用户以自然语言提出学习或创客需求，SC171 完成语音与视觉感知，LLM 根据场景、记忆和工具能力生成可解释计划，安全层校验后调用 SO-ARM101 完成指向或递送，并在界面中实时展示模型、记忆、工具调用、机械臂状态和响应时延。

