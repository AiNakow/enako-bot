# gsz-assist 新公式战接口迁移实现方案

## 1. 总体方案

- 保留所有命令、数据库结构和 `GszService` 公共方法名称、参数、同步/异步形式及返回类型。
- 删除对旧 `gsz.rmlinking.com/gszapi` 接口的依赖，不提供旧接口回退或双执行路径。
- 直接复用 `crypto_session_client.py` 的 ECDH/HKDF/HMAC/AES-GCM 实现，在其上增加一个轻量的公式战 API 客户端，统一处理会话、请求、解密、响应校验和一次性重试。
- 服务层把新接口数据整理成简单的模板上下文；静态内容由 Jinja 直接渲染，JavaScript 只负责 Chart.js 图表。
- 使用真实接口采样后的精简、脱敏响应作为稳定测试 fixture，并保留显式启用的真实链路测试。

## 2. 已确认的新接口与数据映射

统一基址为 `https://rmj.club/formula`，先调用：

| 用途 | 新接口 | 核心结果 |
|---|---|---|
| 加密会话 | `POST /security/crypto/session` | `sid/serverPublicKey/salt/expiresAt` |
| 用户信息 | `GET /index/formula/customer/history?name=` | `result.history`、`result.qq` |
| 同桌统计 | `GET /index/formula/customer/partner-stats` | `result.records/total/pages` |
| 对局记录 | `GET /index/formula/customer/records` | 四家姓名、点数、雀庄和时间 |
| 雀庄搜索 | `GET /index/formula/mahjong/list` | `result.records`，ID 字段为 `id` |
| 雀庄段位榜 | `GET /index/formula/rank/grade/grid` | 段位、RATE、成绩、顺位次数 |

主要字段按新结构直接使用：

- 用户：`customerId/name/grade/rate/nationaSort/mahjongSort/totalPosition/knockBackNum`。
- 成绩：`maxPoint/avgPoint/totalScore/upPosition/upAvgPosition/sumPosition`。
- 六维：`fire/attack/technique/luck/stability/defense`，含义分别为平均顺位、通算得点、平均得点、TOP率、连对率、四位回避率。
- 同桌统计：`opponentName/hateValue/meetCount/myWinCount/myWinRate` 及双方顺位次数、平均顺位。
- 排行榜：`gradeText/mahjongName/rate/avgPoint/upPosition/upAvgPosition/totalPosition/position1..4`。
- 新接口点数以百点为单位；个人最高点、平均点、对局点数及排行榜平均点在展示时乘以 `100`。

段位名称使用已确认的 `match_grades` 映射，从“新人”到“十段”。升段规则采用当前官方前端口径：

```text
局数：[7, 7, 10, 10, 12, 16, 16, 20, 25, 25, 30, 40, 45, 50, 0, 0]
顺位和：[20, 19, 27, 27, 31, 41, 40, 50, 60, 60, 69, 84, 90, 95, 0, 0]
均顺：[2.9, 2.8, 2.7, 2.7, 2.6, 2.6, 2.5, 2.5, 2.4, 2.4, 2.3, 2.1, 2.0, 1.9, 0, 0]
```

九段、十段按已通关展示，不继续计算旧版“最快/最宽松升段条件”。

## 3. 实现调整

### 加密 API 客户端

- 新增单一 `FormulaApiClient` 异步上下文管理器，内部持有一个 `httpx.AsyncClient` 和一个 `EncryptedSessionClient`。
- 每个顶层服务调用创建一次客户端并复用加密会话；不建立全局客户端，避免额外的启动和关闭钩子。
- GET 请求统一添加 `X-Crypto-Session` 和必要浏览器请求头，检查 HTTP、JSON、解密结果及业务层 `success/code/result`。
- 对幂等 GET 的传输错误、会话失效或解密失败最多重建会话并重试一次；业务错误和格式错误不重试。
- 定义内部 `FormulaApiError`，包含端点及安全的错误摘要，不记录密钥、完整密文或解密后的个人数据。
- 将 `cryptography` 加入直接运行时依赖；移除 `crypto_session_client.py` 中的可执行示例和调试输出，但保留底层加密接口。

### 服务层

- `exist_gsz_user`：查询 history，以 `result.history is not None` 判断。
- `bind_userinfo`：直接等待私有异步查询，不在事件循环内调用同步网络方法。
- `get_userinfo_by_name`：查询 history 和前十条 records，生成个人展示模型；头像异步获取，失败或 QQ 为空时使用模板占位，不影响主体图片。
- `get_rank_top`：history 获取 `customerId`，再取同桌统计第一页前十条。
- `get_rank_last`：先取第一页获得总页数，再读取最后一至两页，合并后按 `hateValue` 升序取最后十名，并把 `-hateValue` 作为好感值。
- `get_rate_id`：调用雀庄搜索，优先返回名称完全一致的记录，否则保持原行为返回第一条模糊匹配；无结果或请求失败返回 `None`。
- `bind_rateinfo`：只查询一次雀庄 ID。已确认旧 `rateId` 与新 `mahjongId` 相同，无需迁移现有 SQLite 数据。
- `get_rank_list`：调用段位榜，参数固定为当前雀庄、第一页、50 条，沿用服务返回的默认段位/RATE排序。
- 保留同步的 `exist_gsz_user/get_rate_id/exist_rate`；其同步入口通过一个最小线程桥运行相同异步实现，确保即使从已有事件循环调用也不会触发嵌套 `asyncio.run`。
- 缺失用户、缺失雀庄、空分页和头像失败分别处理；必需结构损坏时明确抛出 API 错误，不静默填充伪数据。

### 图片模板

- 个人图直接渲染姓名、段位、RATE、排名、总局数、飞人吃一、成绩及升段进度。
- 最近顺位和记录统一转换为“旧 → 新”；API 返回的最新优先列表只在服务层复制并反转，不原地修改响应。
- 六维雷达图采用官方前端的分段归一化区间；环图使用四个顺位次数并在图例计算百分比；趋势图展示最近十场顺位及乘以 100 后的点数。
- 删除模板中的旧 API 地址、注释掉的浏览器请求、旧字段兼容和复杂 DOM 查询；仅向图表脚本传递必要 JSON。
- 仇恨榜、好人榜和雀庄排行榜模板改用新字段，并防止总局数为零时除零。
- 所有图表无论成功、空数据还是初始化异常，都必须设置 `window.__chartsReady`，保证截图流程不会无意义超时。

## 4. 外部接口兼容

以下接口保持原样，命令处理文件无需调整：

- `exist_gsz_user`
- `bind_userinfo`
- `get_userinfo_by_uid`
- `get_userinfo_by_name`
- `get_rank_top`
- `get_rank_last`
- `get_rate_id`
- `exist_rate`
- `get_rateinfo_by_group_id`
- `bind_rateinfo`
- `get_rank_list`

用户和雀庄数据库表、绑定数据格式、命令名称、失败提示及图片返回形式均不变。

## 5. 测试与验收

- 加密单元测试：Base64URL、会话协商和复用、HKDF/HMAC/AES-GCM 解密、AAD、错误密钥、重复 RID、并发重复 RID、过期会话和非法响应。
- API 客户端测试：使用 `httpx.MockTransport` 完成真实加密响应闭环，覆盖请求参数、响应校验、业务错误、HTTP 错误、一次重试及重试耗尽。
- 服务测试：使用脱敏 fixture 覆盖用户存在/不存在、个人展示模型、点数换算、段位边界、雷达归一化、顺位排序、头像失败、仇恨榜、跨页好人榜、空榜单、雀庄精确/模糊匹配和前 50 排行。
- 模板测试：检查 HTML 转义、空值、零局数、中文标签和 JSON 脚本安全；通过 Playwright 验证三个图表完成、无页面异常、关键文本正确。
- 渲染链路测试：对个人图、仇恨榜、好人榜和排行榜执行真实 Chromium 截图，用 Pillow 验证 JPEG 可解码、尺寸合理且内容非空。
- 接口兼容测试：通过签名断言和模拟命令层调用确认所有公共方法的同步/异步形式、参数及返回类型未变化。
- 真实烟雾测试：由环境变量提供用户名和雀庄名，显式启用后覆盖会话、解密、五类接口和四类图片；测试日志不输出原始响应。实施验收时使用已验证样例运行一次。
- 回归命令运行全部现有测试，并对公式战 Python 模块生成 `term-missing` 覆盖率报告；目标为新加密/API/服务代码行覆盖率不低于 90%，同时报告实际覆盖率。
- 验收条件：仓库中不存在旧公式战 API 调用；全部默认测试通过；真实接口烟雾测试通过；四类图片可正常生成；现有绑定数据无需重绑即可查询排行榜。
