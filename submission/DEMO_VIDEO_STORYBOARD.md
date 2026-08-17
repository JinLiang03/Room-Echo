# 空间回声 Room Echo｜2 分钟演示视频分镜与生成提示词

> 成片目标时长：**1 分 58 秒**。
> 核心任务：在 2 分钟内回答“为谁而做、解决什么真实需要、如何使用、使用后发生了什么”。
> 当前真实需求人物是 J；Room Echo Care／原居养老只作为下一 MVP 出现。
> 当前作品只允许把环境光反应显示为 `SIMULATED PREVIEW`；轻量确认和照护升级属于下一 MVP，不得伪装成当前行动或真实设备执行。
> 产品部分优先使用最终公网版本的真实录屏。生成画面只用于片头、转场和分镜概念，不得代替真实产品或用户反馈证据。

## 一、总叙事

```text
一个真实的人不愿被拍下
→ 现有产品在“持续拍摄”和“只返回一个状态”之间留下缺口
→ Room Echo 用三个代理信号形成一个可解释的空间 Agent
→ Agent 实时解释、展示克制反应，并在证据不足时不行动
→ J 的真实反馈先推动观点组件上首页并只读最新周期
→ 新定位再把公开表达收敛为“一个 Agent + 一个行动窗口”，等待 J 二次验证
→ 单一 Agent 公网候选版已部署并复验，可开始录制
→ Care 与真实设备是下一 MVP
```

## 二、统一制作规范

### 画幅与交付

- 主画幅：`16:9`，建议 `3840 × 2160` 或 `1920 × 1080`；
- 帧率：24 或 25 fps；产品录屏可采集 60 fps 后按时间线处理；
- 总时长：1:58，前后各保留 1 秒安全余量；
- 字幕：简体中文，最多两行，每行不超过 18 个汉字；
- 音频：人声优先，背景声保持低动态，不使用医疗警报或惊悚音效；
- 录屏：桌面 Chrome，关闭通知、书签栏、个人账号头像与系统敏感信息；
- 公网画面必须拍到 `SIM · REPLAY` 与 `INFERENCE FIELD — NOT A CAMERA IMAGE`。

### 视觉系统

- 背景：温暖纯白 `#FBFBFA`；
- 文字：深墨黑 `#151515`，高对比衬线标题 + 中性无衬线正文；
- 数字彩虹色：红 `#EF476F`、橙 `#F78C6B`、黄 `#E9B949`、绿 `#06A77D`、蓝 `#118AB2`、紫 `#6C63FF`、洋红 `#C445B8`；
- 界面比例：左侧约 31%，右侧约 69%，中间一条极细浅灰分隔线；
- 右侧主体：保留现有由大量彩色数字构成的推断场／数字轮廓；轮廓可以呈现柔和的身体感，但没有面部、骨骼或解剖细节；
- 动效：静息时数字缓慢呼吸，活动上升时数字轮廓展开，证据不足时数字断裂、稀疏并降低饱和度；
- 行动窗口：右下或底部的小尺寸圆角窗口，不抢过实时解释；
- 必须标注：数字轮廓是代理信号驱动的推断场，不是人物影像、人体检测或姿态恢复；
- 禁止：真实或生成的人像、骨骼追踪、姿态关键点、热力图、摄像监控画面、医疗仪表盘、红色报警、精确房间重建。

### 全片统一生成前缀

以下前缀可附加到每个生成镜头前：

```text
16:9 cinematic editorial product film for Room Echo, warm white gallery space,
minimal high-end interaction design, elegant black serif display type placeholders,
fine neutral sans-serif body placeholders, original multicolor numerical inference field
made from hundreds of crisp tiny digits in red orange yellow green blue violet and magenta,
the digits form a soft abstract outline without face bones or anatomy, subtle paper grain,
restrained premium mood, generous negative space, privacy-first technology,
24 fps, natural motion blur, physically plausible light, clean composition.
```

### 全片统一负向提示词

```text
no camera feed, no CCTV wall, no facial recognition boxes, no human heat map,
no photoreal person, no photographed body, no face, no skeleton tracking, no pose keypoints,
do not transform the numerical outline into a detected human, no medical diagnosis dashboard,
no ECG monitor, no red emergency alarm, no exact floor-plan reconstruction,
no readable AI-generated text, no logos invented by the model, no extra buttons,
no cyberpunk neon, no black sci-fi HUD, no humanoid monster, no body organs,
no watermark except the supplied Room Echo product watermark in post-production.
```

> 生成模型不负责排中文。所有可读文字、指标、链接和引用都在剪辑软件中后期叠加；产品 UI 镜头直接使用真实录屏，避免模型改写界面和文字。

## 三、镜头总表

| 镜头 | 时间 | 时长 | 叙事任务 | 素材类型 |
|---|---|---:|---|---|
| 01 | 0:00–0:12 | 12 秒 | 从真实人物 J 与隐私需要开始 | 真实拍摄优先；生成图仅作分镜 |
| 02 | 0:12–0:25 | 13 秒 | 说明现有方案之间的缺口 | 实拍细节 + 抽象转场 |
| 03 | 0:25–0:43 | 18 秒 | 打开公开 Replay，建立真值边界 | 最终产品真实录屏 |
| 04 | 0:43–1:01 | 18 秒 | 展示单一 Agent 的实时解释 | 最终产品真实录屏 |
| 05 | 1:01–1:19 | 18 秒 | 展示克制行动与通用环境光模拟预演 | 产品录屏 + 后期行动标签 |
| 06 | 1:19–1:36 | 17 秒 | 展示证据不足时主动暂缓 | 最终产品真实录屏 |
| 07 | 1:36–1:52 | 16 秒 | 呈现 J 的真实反馈与改动 | 真实截图、原话、录屏 |
| 08 | 1:52–1:58 | 6 秒 | 作品链接、当前与下一步 | 品牌结束卡 |

## 四、逐镜头执行稿

## 镜头 01｜一个不想被持续拍下的人

**时间**：0:00–0:12

**画面**

夜晚的小型创作空间。默认只拍真实空工作台、键盘、投影光和空间细节，不出现人物或可识别影像；显示正在进行的 AI／视觉创作。桌面摄像头或电脑镜头被明确关闭，但不要拍成反监控惊悚片。最后一秒，屏幕白光自然铺满画面，过渡到 Room Echo 的白色界面。

只有在 J 另行书面授权本次匿名影像后，才可补拍不含面部、纹身或其他识别线索的手部／背肩镜头。现有文字与截图授权不自动覆盖视频拍摄；不要生成一个虚构人物冒充 J。

**屏幕文字（后期）**

```text
需求从 J 开始
小型创作空间 · 不希望被持续拍摄
```

**旁白**

> 我从自己 J 开始。我长时间在一个小型空间里做 AI 和视觉创作，想记住房间节奏的变化，但不想让摄像头一直拍着我。

**声音**

键盘轻响、远处低频房间声；第 8 秒进入极轻的 68 BPM 柔和脉冲。

**分镜图／生成视频提示词**

```text
Documentary close-up inside a small contemporary creative studio in Beijing at night,
an empty authentic work desk with no person in frame, generative visual artwork softly
glowing on a monitor out of focus, a laptop camera visibly disabled with a simple physical
cover, intimate calm atmosphere, warm practical desk lamp, white paper, keyboard and
subtle reflections, slow 5 percent camera push-in, shallow depth of field, end with monitor
white light blooming naturally to full frame for a seamless transition. Privacy and
concentration, not fear.
```

**负向补充**

```text
no person, no invented face, no elderly actor, no surveillance camera close-up, no hacker imagery,
no dramatic darkness, no identifiable address, no readable private screen content.
```

## 镜头 02｜在持续拍摄与单一状态之间

**时间**：0:12–0:25

**画面**

三个极简细节依次出现：被关闭的摄像头镜头、只亮一个点的普通传感器、等待输入的空白聊天框。画面不是产品对手批判，而是展示三个能力边界。红、橙、黄、绿、蓝、紫小数字从 Wi-Fi 路由器指示灯附近浮起，汇入纯白界面中的彩色数字推断场。

**屏幕文字（后期）**

```text
摄像头知道太多
普通传感器知道太少
聊天助手只能等待开口
```

**旁白**

> 摄像头知道得太多，普通人体传感器又通常只返回一个状态；聊天助手会回答问题，却接触不到我开口之前的空间变化。

**声音**

三次极轻的材质声，第三次后合并成连续柔和脉冲。

**分镜图／生成视频提示词**

```text
Minimal editorial triptych on a warm white background: first, a small laptop camera with
its privacy shutter closed; second, a simple ambient sensor showing only one soft gray
indicator dot; third, a blank conversational input field waiting without typing. Keep all
objects understated and unbranded. Tiny crisp digits in red orange yellow green blue violet
and magenta emerge from a small home Wi-Fi router status light and flow horizontally across
the triptych, merging into the supplied Room Echo multicolor numerical inference field.
The resulting digit outline stays abstract, with no face bones or anatomy. Locked camera,
gentle 2D-to-3D transition, no text.
```

**负向补充**

```text
no competitor logos, no warning symbols, no red cross, no aggressive comparison chart,
no readable chat text, no person detection graphic.
```

## 镜头 03｜候选版本使用封存 Replay

**时间**：0:25–0:43

**画面**

使用已复验的最终公网候选版本真实录屏。浏览器进入 Room Echo 首页，镜头停留足够久，让观众看见：左侧单一 Agent、右侧实时推断场、底部行动窗口、`SIM · REPLAY` 和非摄像图像水印。静息状态缓慢呼吸。

**屏幕文字（产品内或后期）**

```text
SIM · REPLAY
封存记录 · 不是实时硬件
INFERENCE FIELD — NOT A CAMERA IMAGE
```

**旁白**

> 这是空间回声。公开体验播放一段经过封存校验的 Replay，不冒充实时硬件，也不调用摄像头。

**声音**

音乐只保留稀疏低频；产品声默认静音，不伪装成现场采集声音。

**实际录屏指令**

1. 桌面 Chrome 1440 × 900；
2. 无痕窗口打开最终公网链接；
3. 等待首个稳定周期后录制 20 秒；
4. 不移动鼠标，不出现浏览器个人信息；
5. 后期只做轻微 103% 推近，不裁掉 Replay 标签或水印。

**若制作概念分镜图，使用提示词**

```text
Use the supplied Room Echo UI screenshot as an immutable visual reference. Preserve the
layout exactly: 31 percent left explanation column, thin vertical divider, 69 percent
white canvas, the original large multicolor numerical inference field and digit outline on
the right, one small action window near the bottom, one black pill control. Hundreds of
rainbow digits breathe slowly while preserving the supplied outline. Do not alter, rewrite
or invent any interface text; all readable
labels come from the supplied screenshot or post-production overlay. Locked camera with
a very slow 3 percent push-in.
```

**负向补充**

```text
no new UI panels, no seven agent cards, no floating dashboards, no simulated camera image,
no modified typography, no hallucinated Chinese text.
```

## 镜头 04｜一个 Agent，把变化说清楚

**时间**：0:43–1:01

**画面**

继续真实录屏。Replay 进入活动变化段，右侧彩色数字推断场从静息向展开变化，数字轮廓仍是原有视觉。左栏文字逐步更新，但始终是 Room Echo 一个声音。剪辑用三个局部推近依次强调“观察”“理解”“不知道”。

**建议显示的产品文案**

```text
我观察到：活动强度正在上升
我如何理解：一段连续变化正在形成
我还不知道：这不是身份、人数或姿态判断
```

文案必须由最终产品真实输出或与当前合约一致的确定性展示生成，不要在剪辑中伪造模型结论。

**旁白**

> Wi-Fi 变化先被转成活动强度、遮挡与空间占用代理、相对纵深代理。前台只有一个 Room Echo，说明它观察到什么、如何理解，以及它还不知道什么。

**声音**

活动上升时，柔和脉冲稍微加快；不加入脚步或人物声音，避免暗示识别了真实动作。

**分镜图／图生视频提示词**

```text
Animate the supplied real Room Echo UI capture without changing any text or geometry.
The right-side multicolor numerical inference field gradually expands and elongates while
preserving the original digit outline; individual rainbow digits become slightly faster
and denser, with no face skeleton or pose emerging. In the left column,
use post-production masks to reveal three existing explanation lines one after another;
do not generate new letters. Camera performs three restrained editorial crop moves:
full interface, left explanation detail, then return to full interface. Smooth, calm,
no sudden zoom, preserve the SIM REPLAY label and inference-field watermark at all times.
```

**负向补充**

```text
no body shape emerging from the field, no walking-person icon, no exact trajectory line,
no text mutation, no confidence increase caused by animation.
```

## 镜头 05｜行动是可见的，但当前是模拟预演

**时间**：1:01–1:19

**画面**

底部行动窗口从“继续观察”切换到“模拟预演：环境光反应”。窗口内用三段抽象光区依次柔和展开；主动画继续由当前代理信号驱动，不因行动文案改变测量。右上或窗口标题始终显示 `SIMULATED PREVIEW`。

前 8 秒展示当前行动合约允许的“保持静默／继续观察”，后 10 秒才进入环境光模拟预演。

**屏幕文字（必须明确）**

```text
当前行动：继续观察

SIMULATED PREVIEW
当前模拟：环境光反应
NEXT MVP：预设引导光（待真实验证）
状态：未连接真实灯具
```

**旁白**

> Agent 的反应也单独可见：它可以保持静默、继续观察，或在推断场中预演环境光。这里的环境光明确标为模拟，当前没有控制真实灯具，也没有识别完整路径；轻量确认属于下一 MVP。

**声音**

三段抽象光区出现时各有一个极轻、无音高判断含义的软质声；不得使用设备成功提示音。

**分镜图／图生视频提示词**

```text
Use the supplied real Room Echo interface as immutable reference. Animate only the small
bottom action viewport: begin with a restrained observation state, then transition to a
clearly labeled simulation preview area added in post. Inside that small viewport, three
abstract ambient light blooms appear sequentially from dim warm white to a low-saturation
rainbow glow, without depicting a reconstructed room, floor zone or detected route. Keep
the main multicolor numerical inference field and original digit outline moving continuously
according to its existing signal animation. No device
success state, no notification sent, no external hardware shown as connected. Locked full
interface composition, 24 fps, subtle cross-dissolve between action states.
```

**负向补充**

```text
no real smart-home control confirmation, no green checkmark, no map path, no room geometry,
no elderly person, no fall, no emergency service, no caregiver notification.
```

## 镜头 06｜证据不足时，主动不行动

**时间**：1:19–1:36

**画面**

Replay 进入干扰／歧义段。右侧彩色数字轮廓边缘出现轻微断裂，数字变稀、饱和度下降；左栏明确写出替代解释未排除；底部行动窗口变为“证据有限，继续观察”。镜头最后停一秒，让观众读完。

**建议显示的产品文案**

```text
证据有限
无线干扰尚未排除
当前行动：暂不预演，继续观察下一周期
```

**旁白**

> 如果干扰没有排除，Room Echo 不会把异常叫作跌倒，也不会因为后台多个 Agent 同意就提高置信。它会显示证据有限，并选择暂不行动。

**声音**

脉冲减弱并留出半秒安静，不使用报警声。

**分镜图／图生视频提示词**

```text
Animate the supplied real Room Echo UI during an ambiguous evidence state. Preserve all
layout and text. The multicolor numerical inference field keeps the supplied digit outline,
but digits fragment slightly at the edges, become sparser, lower saturation by about
20 percent and slow their motion; no face skeleton or pose appears. The left explanation
column receives a soft neutral-gray
uncertainty wash added in post; the small action window settles into a withheld state.
Hold the final frame for one full second for readability. Calm restraint, no alarm.
```

**负向补充**

```text
no red flashing, no danger icon, no fall detection text, no emergency call animation,
no medical sound, no agent vote count, no confidence boost.
```

## 镜头 07｜真实反馈推动了什么变化

**时间**：1:36–1:52

**画面**

使用三段真实画面呈现三个阶段：旧版标注“Agent 观点没有进入主位／跨周期混合”；首轮反馈修复标注“观点上首页／只读最新完整周期”；复赛候选版标注“一个公开 Agent／行动窗口独立”。两句 J 原话依次出现。最后保留一行“单一 Agent 公网二次体验：待确认”。

**屏幕文字（逐字一致）**

```text
“这七个agent应该要放到主位，但是现在我们对它的感知不强。”

“虽然系统会持续播放和更新，但是文字内容好像没变化吧。”

单一 Agent 公网二次体验：待确认
```

**旁白**

> 第一次体验时，J 说七个 Agent 的存在感不强，文字看起来也没有变化。反馈先推动我们修复未挂载和跨周期混合；单一 Agent 是随后基于新定位做出的第二阶段收敛，二次体验仍待确认。

**声音**

背景音乐稍微回暖；切换前后截图时使用纸张翻页般的轻声。

**剪辑执行提示词**

```text
Create a clean three-stage editorial timeline using only the supplied authentic Room Echo
screenshots. Do not regenerate any screenshot. Show: first, the earlier interface where
agent viewpoints were absent from the homepage and mixed across cycles; second, the verified
feedback fix with viewpoints mounted and bound to the latest complete cycle; third, the
semifinal candidate with one public agent and a separate action window. Use a warm white
canvas and thin pale-gray dividers. Add the two exact J quotes in post-production, one at a
time with restrained opacity fades. End with a factual label that single-agent public
second-use confirmation is pending. No celebratory checkmark, invented metric or fake user.
```

**负向补充**

```text
no generated testimonial video, no five-star rating, no success percentage, no elderly
user claim, no altered quote punctuation or wording, no claim that the issue is solved.
```

## 镜头 08｜今天与下一步

**时间**：1:52–1:58

**画面**

纯白结束卡。现有彩色数字推断场从右侧缓慢退入白色，数字轮廓逐渐散成一条彩虹数字流，留下作品名、一句话、链接和真值边界。Care 只出现为小号下一步说明。

**屏幕文字（后期）**

```text
空间回声 Room Echo
一个会解释，也知道何时保持沉默的空间 Agent

wifi-spatial-council-replay.onrender.com
SIM · REPLAY · NOT A CAMERA IMAGE

NEXT MVP · Room Echo Care（待真实用户与设备验证）
```

**旁白**

> 候选版本已部署并完成公网复验，空间回声可以直接体验；下一步，我们会用真实设备和真实用户验证，它能否进入原居生活。

**声音**

音乐在第 5 秒自然收束，不做宏大上扬。

**结束卡生成提示词**

```text
Minimal premium end card on a warm white background. The supplied Room Echo multicolor
numerical inference field and original digit outline slowly recede toward the far right,
then disperse into a thin stream of tiny rainbow digits, leaving generous white negative
space for post-production typography on the left. One thin pale-gray divider and one small
black rounded pill placeholder for the public link. Quiet confidence, subtle paper grain,
elegant editorial composition, six-second slow motion, seamless fade to white. Preserve the
numerical visual language; no generated readable text, all wording and URL added in post.
```

**负向补充**

```text
no investor logos, no healthcare certification badge, no smart-home device checkmark,
no claim of live hardware, no claim of validated elder care, no dramatic product launch flare.
```

## 五、完整旁白稿

> 我从自己 J 开始。我长时间在一个小型空间里做 AI 和视觉创作，想记住房间节奏的变化，但不想让摄像头一直拍着我。
>
> 摄像头知道得太多，普通人体传感器又通常只返回一个状态；聊天助手会回答问题，却接触不到我开口之前的空间变化。
>
> 这是空间回声。公开体验播放一段经过封存校验的 Replay，不冒充实时硬件，也不调用摄像头。
>
> Wi-Fi 变化先被转成活动强度、遮挡与空间占用代理、相对纵深代理。前台只有一个 Room Echo，说明它观察到什么、如何理解，以及它还不知道什么。
>
> Agent 的反应也单独可见：它可以保持静默、继续观察，或在推断场中预演环境光。这里的环境光明确标为模拟，当前没有控制真实灯具，也没有识别完整路径；轻量确认属于下一 MVP。
>
> 如果干扰没有排除，Room Echo 不会把异常叫作跌倒，也不会因为后台多个 Agent 同意就提高置信。它会显示证据有限，并选择暂不行动。
>
> 第一次体验时，J 说七个 Agent 的存在感不强，文字看起来也没有变化。反馈先推动我们修复未挂载和跨周期混合；单一 Agent 是随后基于新定位做出的第二阶段收敛，二次体验仍待确认。
>
> 候选版本已部署并完成公网复验，空间回声可以直接体验；下一步，我们会用真实设备和真实用户验证，它能否进入原居生活。

## 六、建议拍摄与剪辑清单

### 必拍真实素材

- [ ] J 的创作空间细节或空工作台，避免可识别隐私；
- [ ] 最终公网首页从静息到变化的连续录屏；
- [ ] `SIM · REPLAY`、水印和单一 Agent 左栏特写；
- [ ] 底部行动窗口的真实产品状态；
- [ ] 干扰／unknown 状态；
- [ ] 旧版与新版真实截图；
- [ ] 最终公网链接无痕窗口打开成功。

### 后期必须添加

- [ ] 所有可读中文与英文标签；
- [ ] `SIMULATED PREVIEW`；
- [ ] “未连接真实灯具”；
- [ ] “单一 Agent 公网二次体验：待确认”；
- [ ] “NEXT MVP · Room Echo Care（待真实用户与设备验证）”；
- [ ] 片尾 Replay 与非摄像图像边界。

### 成片发布前检查

- [ ] 总时长不超过 2:00；
- [ ] 没有把 Replay 说成 Live；
- [ ] 没有把模拟行动说成真实执行；
- [ ] 没有出现跌倒检测、路径识别、人数、姿态或身份主张；
- [ ] J 的两句原话逐字一致；
- [ ] 没有把 J 写成养老用户；
- [ ] Care 始终标为下一 MVP／待验证；
- [ ] 没有 API key、个人账号、通知、精确地址或未授权影像；
- [ ] 链接、界面和最终提交版本一致。
