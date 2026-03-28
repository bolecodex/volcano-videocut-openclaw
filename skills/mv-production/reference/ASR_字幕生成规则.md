# ASR 字幕生成规则

## 执行约束（必须遵守）

**每一句歌词在写入 `asr_corrected.json` 或生成字幕前，都必须完整走完本规范规定的全部步骤，不得跳过或只部分执行。**

- 歌词的**每一行**都必须依次经过：**逐句对齐 → 逐字精修 → 行级时间严格取自 words → 全局禁止重叠校正**。
- 不允许对部分行「按规范」、对部分行「粗略处理」；不允许用整句/整段 utterance 的起止时间代替某一行的起止时间。
- 输出前必须对**每一行**做一次「每行校验清单」（见下文）检查，全部通过后方可写出 `asr_corrected.json` 与 SRT。

---

## 常见错误与解耦原则（行级时间 ≠ utterance 时间）

### 问题现象

当**一句 ASR utterance 对应多行歌词**时，若误用该 utterance 的 `start_time`/`end_time` 作为其中某一行的 `start_time_ms`/`end_time_ms`，会出现：

- 该行歌词实际只到某字结束（如「夜」`end_time` = 10880），但纠错后该行被写成 `end_time_ms: 14280`；
- 原因：14280 是**整段 utterance**（如「跳动的烛光摇曳到深夜，独自摸了又摸，还是不够烈。」）的结束时间，**不属于**单行「琵琶洞的烛光摇曳到深夜」。

正确应为：该行的 `end_time_ms` = 该行**最后一个字**在 words 中的 `end_time`（如「夜」的 10880），**不能**用整句的 14280。

### 解耦原则

| 概念 | 用途 | 禁止用法 |
|------|------|----------|
| **utterance 的 start_time / end_time** | 仅用于「逐句对齐」时划定该行可用的 words 范围（初始时间窗口） | **禁止**直接赋给 `lines[i].start_time_ms` / `lines[i].end_time_ms` |
| **行级 start_time_ms / end_time_ms** | 分镜、字幕、口型对齐的权威时间 | **必须**仅来自该行**参与对齐并保留的 words** 的最小 start、最大 end |

即：**行级时间与 utterance 级时间解耦**——每行时间只由「该行实际用到的那些 word」决定，与 utterance 整句起止无关。

### 流程梳理（强制顺序，避免耦合）

1. **逐句对齐**：为每行歌词 `L[i]` 找到对应的 utterance（或合并后的 words 序列），得到「候选 words 范围」；可记录 utterance 的 start/end 仅作**初始窗口**，**不写入**该行的 start_time_ms/end_time_ms。
2. **逐字精修**：在该行的候选 words 内，按歌词字符顺序逐字匹配；只保留**与本行歌词对应**的 words，多余部分（如同一 utterance 中属于下一句的「独自摸了又摸，还是不够烈。」）**丢弃，不参与本行时间计算**。
3. **行级时间计算**（强制公式）：
   - `lines[i].start_time_ms` = **该行保留的 words 中** `min(word.start_time)`；
   - `lines[i].end_time_ms` = **该行保留的 words 中** `max(word.end_time)`；
   - 不得使用 utterance 的 start_time/end_time 或其它句级汇总值。
4. **全局禁止重叠**：对相邻行做 `lines[i+1].start_time_ms >= lines[i].end_time_ms` 校验与必要微调。
5. **每行校验清单**：每行通过后再输出 `asr_corrected.json` 与 SRT。

按上述顺序执行并严格用「该行 words 的 min/max」计算行级时间，即可避免「夜结束 10880 却写成 14280」类错误。

---

# 流程

## 1. 提取 ASR 结果中的 `utterances` 字段， 参考示例如下：

```json
 "utterances": [
      {
        "end_time": 88500,
        "start_time": 76580,
        "text": "holy 那天眼之光照耀苍穹，神刀在手，谁与争锋？我是杨戬，司法天神。",
        "words": [
          {
            "confidence": 0,
            "end_time": 76660,
            "start_time": 76580,
            "text": "holy"
          },
          {
            "confidence": 0,
            "end_time": -1,
            "start_time": -1,
            "text": " "
          },
          {
            "confidence": 0,
            "end_time": 79740,
            "start_time": 79580,
            "text": "那"
          },
          {
            "confidence": 0,
            "end_time": 79900,
            "start_time": 79820,
            "text": "天"
          },
          {
            "confidence": 0,
            "end_time": 80100,
            "start_time": 80060,
            "text": "眼"
          },
          {
            "confidence": 0,
            "end_time": 80380,
            "start_time": 80220,
            "text": "之"
          },
          {
            "confidence": 0,
            "end_time": 80740,
            "start_time": 80420,
            "text": "光"
          },
          {
            "confidence": 0,
            "end_time": 81460,
            "start_time": 81260,
            "text": "照"
          },
          {
            "confidence": 0,
            "end_time": 81620,
            "start_time": 81460,
            "text": "耀"
          },
          {
            "confidence": 0,
            "end_time": 81900,
            "start_time": 81700,
            "text": "苍"
          },
          {
            "confidence": 0,
            "end_time": 82100,
            "start_time": 81940,
            "text": "穹"
          },
          {
            "confidence": 0,
            "end_time": 82980,
            "start_time": 82780,
            "text": "神"
          },
          {
            "confidence": 0,
            "end_time": 83140,
            "start_time": 83100,
            "text": "刀"
          },
          {
            "confidence": 0,
            "end_time": 83420,
            "start_time": 83260,
            "text": "在"
          },
          {
            "confidence": 0,
            "end_time": 83540,
            "start_time": 83420,
            "text": "手"
          },
          {
            "confidence": 0,
            "end_time": 83820,
            "start_time": 83660,
            "text": "谁"
          },
          {
            "confidence": 0,
            "end_time": 83980,
            "start_time": 83860,
            "text": "与"
          },
          {
            "confidence": 0,
            "end_time": 84220,
            "start_time": 84060,
            "text": "争"
          },
          {
            "confidence": 0,
            "end_time": 84420,
            "start_time": 84340,
            "text": "锋"
          },
          {
            "confidence": 0,
            "end_time": 85700,
            "start_time": 85420,
            "text": "我"
          },
          {
            "confidence": 0,
            "end_time": 85940,
            "start_time": 85700,
            "text": "是"
          },
          {
            "confidence": 0,
            "end_time": 86140,
            "start_time": 86100,
            "text": "杨"
          },
          {
            "confidence": 0,
            "end_time": 86460,
            "start_time": 86420,
            "text": "戬"
          },
          {
            "confidence": 0,
            "end_time": 86860,
            "start_time": 86820,
            "text": "司"
          },
          {
            "confidence": 0,
            "end_time": 87260,
            "start_time": 87100,
            "text": "法"
          },
          {
            "confidence": 0,
            "end_time": 87900,
            "start_time": 87540,
            "text": "天"
          },
          {
            "confidence": 0,
            "end_time": 88500,
            "start_time": 88260,
            "text": "神"
          }
        ]
      }
    ]
```

## 2. 使用 歌词文件， 文件格式处理如下：

### 2.1 原始文件

```txt
歌名：《天眼之光》

音乐描述Prompt：Epic rock ballad, powerful male vocals, traditional Chinese instruments mixed with electric guitar, building from soft to intense, inspiring, heroic journey, overcoming adversity, ancient Chinese mythology theme

歌词：
[Verse 1]
当年灌江口，我曾是无名少年郎
三尖两刃刀，还未露锋芒
母亲被压桃山下，日夜思断肠
立下誓言，要让这天也低头
[Pre-Chorus]
他们笑我年少轻狂
不懂天高地厚
可我知道，命运由我不由天
[Chorus]
开天眼！看尽世间善恶
握神刀！劈开前路迷茫
从弱小到强大，我是司法天神
让三界六道，都听我号令！
[Verse 2]
曾在桃山救母，劈开这千年的枷锁
力劈华山，证明我的气魄
灌江口练神功，寒暑从未停歇
七十二变在身，敢与大圣争锋
[Pre-Chorus]
他们说我是叛逆之徒
不懂天规地律
可我知道，正义自在我心
[Chorus]
开天眼！看尽世间善恶
握神刀！劈开前路迷茫
从弱小到强大，我是司法天神
让三界六道，都听我号令！
[Bridge]
从灌江口到凌霄殿
我一步步向前
从无名少年到司法天神
我用血汗铸就传奇
[Chorus]
开天眼！看尽世间善恶
握神刀！劈开前路迷茫
从弱小到强大，我是司法天神
让三界六道，都听我号令！
[Outro]
天眼之光，照耀苍穹
神刀在手，谁与争锋
我是杨戬，司法天神！

```

### 2.2 处理后

```txt
当年灌江口，我曾是无名少年郎
三尖两刃刀，还未露锋芒
母亲被压桃山下，日夜思断肠
立下誓言，要让这天也低头

他们笑我年少轻狂
不懂天高地厚
可我知道，命运由我不由天

开天眼！看尽世间善恶
握神刀！劈开前路迷茫
从弱小到强大，我是司法天神
让三界六道，都听我号令！

曾在桃山救母，劈开这千年的枷锁
力劈华山，证明我的气魄
灌江口练神功，寒暑从未停歇
七十二变在身，敢与大圣争锋

他们说我是叛逆之徒
不懂天规地律
可我知道，正义自在我心

开天眼！看尽世间善恶
握神刀！劈开前路迷茫
从弱小到强大，我是司法天神
让三界六道，都听我号令！

从灌江口到凌霄殿
我一步步向前
从无名少年到司法天神
我用血汗铸就传奇

开天眼！看尽世间善恶
握神刀！劈开前路迷茫
从弱小到强大，我是司法天神
让三界六道，都听我号令！

天眼之光，照耀苍穹
神刀在手，谁与争锋
我是杨戬，司法天神！

```

### 3 对齐与纠错规则（先逐句，后逐字）

**上述执行约束适用于此处：每一句都必须按下列规则完整执行，无例外。**

整体思路：**先逐句对齐，再逐字精修**，并在必要时「移除多余 / 拆分杂音」，始终以歌词为权威文本。

#### 3.1 逐句对齐（句级）

1. 将**处理后的歌词文本**按「非空行」切分为 `lyric_lines`，依次记为 `L[0], L[1], ...`。
2. 将 ASR `utterances` 中的 `text` 做简单清洗（去首尾空格、合并多余空格），得到 `U[0], U[1], ...`。
3. 从前往后进行句级对齐：
   - 对于当前歌词行 `L[i]`，在剩余的 `U[j...]` 中找到**最匹配的一条或若干条**：
     - 如果 `L[i]` 能在某个 `U[j].text` 的子串中高相似度匹配（模糊匹配即可），则认为该条 `utterance` 对应 `L[i]`；
     - 如果某行歌词跨越两个或更多 `utterances`（例如中间有较长停顿），可以合并相邻 `U[j], U[j+1]` 的 `words` 视为同一句。
   - 若出现明显多余的 ASR 片段（如「嗯」「啊」「咳嗽声」「笑声」等）且在歌词中不存在对应文字：
     - 将这些 `utterances` 标记为 `noise`，**不映射到任何歌词行**，可在后续字幕生成中忽略。
4. 对于成功对齐到的每一行歌词 `L[i]`：
   - 记录该句对应的 `utterance`/合并后 `utterances` 的最早 `start_time` 和最晚 `end_time` 作为**初始时间窗口**（仅用于划定候选 words 范围，**不得**直接写入该行的 `start_time_ms`/`end_time_ms`；行级时间必须在逐字精修后由该行保留的 words 的 min/max 计算）。

> 句级对齐的目标：保证每行歌词大致落在正确的时间区间内，为后续逐字精修提供边界。行级时间与 utterance 起止解耦，见上文「常见错误与解耦原则」。

#### 3.2 逐字精修（字级）

在完成句级对齐后，对每一行歌词 `L[i]` 进入逐字阶段：

1. 取出该行对应句级窗口内的所有 `words` 序列，按时间排序。
2. 按歌词文本顺序逐字比对：
   - 对于每个歌词字符（或词）`c_k`，依次在剩余 `words` 中寻找**最可能匹配**的 `word.text`：
     - 可采用「严格等于优先，其次允许常见错别字 / 中英符号混用」的策略；
     - 若某个 `word.text` 是明显的冗余符号（如空格、英文标点、口语填充词），且在歌词中无对应字符，则将其标记为 `extra` 并跳过。
3. 对于成功匹配到的字符 `c_k`：
   - 将该字符的 `start_time_ms` / `end_time_ms` **严格取自**匹配到的那个 `word` 的 `start_time` / `end_time`，不得用句级或其它时间代替。
   - 整行歌词的 `start_time_ms` **必须**为该行所有保留 `words` 中**最小的 `start_time`**（即第一个字的 `start_time`）；
   - 整行歌词的 `end_time_ms` **必须**为该行所有保留 `words` 中**最大的 `end_time`**（即最后一个字的 `end_time`）。
   - 即：**行级 `start_time` / `end_time` 一律以 words 中对应字的时间为准**，保证时间轴与口型一致，并为后续「禁止字幕重叠」校验提供准确边界。
4. 对于**未能匹配到 ASR word** 的歌词字符：
   - 如果该字符处于句中间，且前后字符都有时间戳，可采用「线性插值」或「继承邻近时间」方式近似估算；
   - 若整行几乎没有任何匹配（ASR 识别极差），可以退回使用句级窗口的 `start_time` / `end_time` 作为整行时间，并在内部备注识别质量较差。
5. 对于 ASR 中多出来的 `word`（在歌词中没有对应字符）：
   - 若为短促杂音 / 语气词（如「啊」「嗯」「哈哈」）且不会影响语义，可**直接忽略**，不写入最终行的 `words` 数组；
   - 若为明显错误的词语但占用较长时间，可选择：
     - 从时间上仍保留在该行整体窗口内（以免时间上出现「空白」），
     - 但不在 `words` 中明文保留其 `text`，仅通过邻近字符的 `start/end` 覆盖该时间段。

> **重要约定：行级时间必须严格基于逐字对齐后的 `words` 计算。**  
> - 每一行的 `start_time_ms` **必须**等于该行所有有效 `words` 中 **最小的 `start_time`**（即首字对应 word 的 `start_time`）；  
> - 每一行的 `end_time_ms` **必须**等于该行所有有效 `words` 中 **最大的 `end_time`**（即末字对应 word 的 `end_time`）；  
> - 不得用句级窗口或其它估算值代替，只有在该行**完全缺少可用 words** 时，才允许退回使用句级窗口时间。  
> - 字级精修的目标：在不改变宏观节奏的前提下，让每行歌词的时间轴严格贴合 words，并为全局「禁止字幕重叠」提供可靠时间边界。

##### 3.2.1 示例：句尾截断与前缀语义纠错

以如下 ASR `utterance` 为例：

```json
{
  "start_time": 8269,
  "end_time": 14309,
  "text": "跳动的烛光摇曳到深夜，独自摸了又摸，还是不够烈。",
  "words": [
    {"start_time": 8269, "end_time": 8309, "text": "跳"},
    {"start_time": 8429, "end_time": 8509, "text": "动"},
    {"start_time": 8669, "end_time": 8829, "text": "的"},
    {"start_time": 9109, "end_time": 9189, "text": "烛"},
    {"start_time": 9349, "end_time": 9589, "text": "光"},
    {"start_time": 9909, "end_time": 9949, "text": "摇"},
    {"start_time": 10109, "end_time": 10149, "text": "曳"},
    {"start_time": 10309, "end_time": 10469, "text": "到"},
    {"start_time": 10589, "end_time": 10629, "text": "深"},
    {"start_time": 10829, "end_time": 10869, "text": "夜"},
    {"start_time": 11429, "end_time": 11589, "text": "独"},
    {"start_time": 11589, "end_time": 11669, "text": "自"},
    {"start_time": 11869, "end_time": 11949, "text": "摸"},
    {"start_time": 12029, "end_time": 12229, "text": "了"},
    {"start_time": 12429, "end_time": 12549, "text": "又"},
    {"start_time": 12909, "end_time": 12989, "text": "摸"},
    {"start_time": 13229, "end_time": 13469, "text": "还"},
    {"start_time": 13469, "end_time": 13669, "text": "是"},
    {"start_time": 13669, "end_time": 13869, "text": "不"},
    {"start_time": 13869, "end_time": 14069, "text": "够"},
    {"start_time": 14229, "end_time": 14309, "text": "烈"}
  ]
}
```

目标歌词行为：

```txt
琵琶洞的烛光摇曳到深夜
```

对应的纠错策略：

1. **前缀语义纠错（“跳动的” → “琵琶洞的”）**
   - 语义层面我们认为「`跳动的`」应为「`琵琶洞的`」：
     - `跳` (`8269–8309`) + `动` (`8429–8509`) → 近似对应于「琵」「琶」两字；
     - `的` (`8669–8829`) 保持不变。
   - 时间上，仍沿用原 `words` 的时间片：
     - 「琵」使用 `跳` 的时间；
     - 「琶」使用 `动` 的时间；
     - 「的」沿用原来的「的」时间。
   - 即：**前缀内容可以在文字上纠错，但时间片仍复用原 ASR `words` 的 `start_time` 与 `end_time`。**

2. **句尾截断（丢弃「独自摸了又摸，还是不够烈。」）**
   - 目标歌词只保留到「深夜」，因此在时间轴上应截断到「夜」这个字：
     - 「夜」对应的 `word` 时间为 `10829–10869`。
   - 从时间上：
     - 本行 `start_time_ms` = 最早字符时间 = `8269`；
     - 本行 `end_time_ms` = 最后一个保留字符（「夜」）的 `end_time` = `10869`。
   - 之后所有 `words`（「独自摸了又摸，还是不够烈。」相关）全部视为**多余内容**，在本行对齐中丢弃，不参与时间计算。

3. **行级结果**

最终，该行在 `asr_corrected.json` 中应类似：

```json
{
  "index": 0,
  "lyric": "琵琶洞的烛光摇曳到深夜",
  "start_time_ms": 8269,
  "end_time_ms": 10869,
  "raw_text": "跳动的烛光摇曳到深夜，独自摸了又摸，还是不够烈。",
  "words": [
    { "text": "琵", "start_time_ms": 8269, "end_time_ms": 8309 },
    { "text": "琶", "start_time_ms": 8429, "end_time_ms": 8509 },
    { "text": "洞", "start_time_ms": 8669, "end_time_ms": 8829 },
    { "text": "的", "start_time_ms": 8669, "end_time_ms": 8829 },
    { "text": "烛", "start_time_ms": 9109, "end_time_ms": 9189 },
    { "text": "光", "start_time_ms": 9349, "end_time_ms": 9589 },
    { "text": "摇", "start_time_ms": 9909, "end_time_ms": 9949 },
    { "text": "曳", "start_time_ms": 10109, "end_time_ms": 10149 },
    { "text": "到", "start_time_ms": 10309, "end_time_ms": 10469 },
    { "text": "深", "start_time_ms": 10589, "end_time_ms": 10629 },
    { "text": "夜", "start_time_ms": 10829, "end_time_ms": 10869 }
  ]
}
```

> 重点：**纠错后的行级时间严格由保留的 `words` 决定，多余文本对应的 `words` 必须从该行时间计算中移除。**

##### 3.2.2 反例：行级 end_time_ms 不得超出本行 words 范围

同一句 ASR 被拆成两行歌词时，行级时间**必须只取自该行实际保留的 words**，不能把下一行或整句的结束时间误写到本行。

**错误示例**（不符合规则）：

- 第 2 行歌词为「唐僧说这个月KPI还没达标」，其 `words` 中最后一个字是「标」，对应 `end_time_ms: 18280`。
- 若该行写成 `"end_time_ms": 20960`，则**错误**：20960 来自下一句「悟空在旁边……」中「的」的结束时间，不属于本行。
- 正确做法：该行的 `end_time_ms` **必须**为 `18280`（即本行最后一个字「标」的 `end_time`）。

同理，第 3 行「悟空在旁边等着看我的笑话」的 `start_time_ms` 应为本行第一个字「悟」的 `start_time`（18520），`end_time_ms` 应为本行最后一个字「话」的 `end_time`（21400）。这样第 2 行结束 18280、第 3 行开始 18520，中间有间隙、无重叠，符合「禁止字幕重叠」且时间均来自 words。

**正确示例**（仅时间相关字段）：

```json
{
  "index": 2,
  "lyric": "唐僧说这个月KPI还没达标",
  "start_time_ms": 15400,
  "end_time_ms": 18280,
  "words": [ ..., { "text": "标", "start_time_ms": 18120, "end_time_ms": 18280 } ]
},
{
  "index": 3,
  "lyric": "悟空在旁边等着看我的笑话",
  "start_time_ms": 18520,
  "end_time_ms": 21400,
  "words": [ { "text": "悟", "start_time_ms": 18520, "end_time_ms": 18680 }, ..., { "text": "话", "start_time_ms": 21280, "end_time_ms": 21400 } ]
}
```

- 第 2 行：`start_time_ms` = 本行 words 最小 start = 15400，`end_time_ms` = 本行 words 最大 end = **18280**（「标」）。
- 第 3 行：`start_time_ms` = 18520（「悟」），`end_time_ms` = 21400（「话」）；18280 &lt; 18520，无重叠。

#### 3.3 全局对齐与边界修正（禁止字幕重叠 + 声画同步）

逐句 / 逐字对齐完成后，必须做一轮**全局校正**，核心要求：**不得出现字幕重叠**，并避免声画错位。

**硬性规则：禁止字幕重叠**

- 任意相邻两行字幕**不允许时间重叠**，即必须满足：
  - `lines[i+1].start_time_ms >= lines[i].end_time_ms`
  - 允许两行之间有间隙（后一行开始晚于前一行结束），不允许后一行的开始早于前一行的结束。
- 若逐字精修后出现 `lines[i+1].start_time_ms < lines[i].end_time_ms`，必须在本阶段修正，例如：
  - 将后一行 `start_time_ms` 调整为 `lines[i].end_time_ms` 或 `lines[i].end_time_ms + δ`（如 +30ms～50ms），或
  - 将前一行的 `end_time_ms` 适当提前，使两行边界不重叠（需保证该行仍有合理时长）。
- 行级时间仍应尽量以 words 为准；仅在为消除重叠做微调时，可对边界做最小幅度的平移。

1. **单调性检查**
   - 保证每一行满足：
     - `start_time_ms >= 0`
     - `end_time_ms >= start_time_ms`
   - 多行之间满足（**禁止重叠**）：
     - `lines[i+1].start_time_ms >= lines[i].end_time_ms`
   - 若发现局部逆序或重叠，按上述「禁止字幕重叠」规则修正：
     - 优先将后一句 `start_time_ms` 抬到至少 `lines[i].end_time_ms`（或 +50ms）；
     - 必要时可将前一句 `end_time_ms` 轻微拉回，但保持每行仍有正长度。

2. **与音频时长对齐**
   - 从最终歌曲音频（通常为 `output_dir/song.mp3`）中探测时长（秒），记为 `T_audio`；
   - 对所有行做边界裁剪：
     - `start_time_ms = max(0, start_time_ms)`
     - `end_time_ms = min(end_time_ms, T_audio * 1000)`
   - 若某行被裁剪后 `end_time_ms <= start_time_ms`，说明该行完全落在音频之外，可选择：
     - 直接丢弃该行字幕，或
     - 将其时间钳制在音频末尾附近（例如 `[T_audio*1000 - 500, T_audio*1000 - 100]`），并在内部标记质量较差。

3. **间隙与重叠处理**
   - 对于相邻行 `i` 和 `i+1`：
     - 若 `lines[i+1].start_time_ms - lines[i].end_time_ms` 过大（例如 > 3–5 秒），可以保留间隙（作为无字幕的纯音乐区），无需强行填满；
     - 若出现重叠（`lines[i+1].start_time_ms < lines[i].end_time_ms`），建议：
       - 优先保持时间上更晚出现的行的 `start_time_ms`，将其抬到 `lines[i].end_time_ms + δ`（例如 `+50ms`）；
       - 或对两行进行折中分割，让边界落在两者时间中点附近。

4. **微调以贴合主观体验（可选）**
   - 实际观感中，字幕**略早于**人声出现通常比「略晚」更舒适。
   - 可在全局校正后，对所有行额外应用一个小的负偏移（例如 `-80ms`）：
     - `start_time_ms = max(0, start_time_ms - 80)`
     - `end_time_ms` 一般保持不变或只做轻微缩短；
   - 具体偏移大小可根据实际项目和用户反馈微调。

### 4 每行输出前校验清单（逐句必检）

在写出 `asr_corrected.json` 或 SRT 之前，**必须对 `lines` 中的每一行**执行下列校验，全部满足后方可输出；任一行不满足则必须修正该行后再次校验。

对每一行 `lines[i]`（i 从 0 到 len(lines)-1）：

| 序号 | 校验项 | 要求 |
|------|--------|------|
| 1 | 行级时间来源于 words | `start_time_ms` = 该行所有保留 words 的**最小** `start_time`；`end_time_ms` = 该行所有保留 words 的**最大** `end_time`。若该行无可用 words，才允许用句级窗口并备注。 |
| 2 | 行内时间合法 | `start_time_ms >= 0` 且 `end_time_ms >= start_time_ms`。 |
| 3 | 与上一行不重叠 | 若 i ≥ 1，则 `lines[i].start_time_ms >= lines[i-1].end_time_ms`（禁止字幕重叠）。 |
| 4 | 与音频时长不超界 | `start_time_ms`、`end_time_ms` 均在 [0, T_audio×1000] 内（T_audio 为歌曲音频时长秒数）。 |
| 5 | 内容与歌词一致 | `lyric` 与清洗后的歌词文本对应行一致，未混入 ASR 多余/错误字。 |

只有**每一行**都通过上述 5 项后，才可生成最终 `asr_corrected.json` 与 `lyrics_aligned.srt`；否则应回到逐字精修或全局校正步骤修正，直至每句都符合规范。

### 5 结果生成

在完成逐句+逐字对齐、全局校正，并**通过每行校验清单**后，输出标准化的中间结果与字幕文件：

1. **中间 JSON（推荐结构）**
   - 见 `mv-production/SKILL.md` 中 `asr_corrected.json` 示例，建议包含：
     - `index`：行号；
     - `lyric`：该行歌词文本；
     - `start_time_ms` / `end_time_ms`：行级时间范围（**必须已按 words 与校验清单通过**）；
     - `raw_text`：对应 ASR 原始文本（便于回溯）；
     - `words`：可选的逐字时间信息列表。
2. **字幕文件**
   - 基于 `start_time_ms` / `end_time_ms` 生成：
     - `output_dir/lyrics_aligned.srt`（用于本地硬编码或 VOD 烧录）；
   - 时间格式：`hh:mm:ss,ms`；
   - 每行歌词对应一个或多个字幕块（按需要拆分长句）。

> 注意：字幕内容必须与**清洗后的歌词文本**保持一致，不再暴露 ASR 中的错别字或多余噪声，只在内部 JSON 中保留原始 ASR 以供调试。
