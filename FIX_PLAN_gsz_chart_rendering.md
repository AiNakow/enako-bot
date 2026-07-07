# gsz-assist /吃鱼 图表偶发缺失修复方案

## 问题概述

`/吃鱼` 命令返回的图片中，文字数据正常显示，但折线图（近10场顺位走势）、六维雷达图、环形饼图偶发性完全缺失（空白区域）。

**根因：** 模板使用 Tailwind CSS JIT 运行时编译器（`tailwind.js`，398KB）异步注入 CSS，导致 canvas 容器布局在 DOMContentLoaded 之后才确定。Chart.js 通过 `ResizeObserver` 监听容器尺寸变化并触发重绘，但 ResizeObserver 回调经过 `requestAnimationFrame` 节流，是异步的。`html_to_pic` 的固定 `wait=1000` 延时无法保证在所有情况下都覆盖这一异步链路，截图时图表可能尚未完成重绘。

## 涉及文件

| 文件 | 作用 |
|------|------|
| [service.py](/home/enako/dev/py_project/enako-bot-qq/nonebot/src/plugins/gsz-assist/service.py) | `convert_html_to_pic` / `convert_html_to_pic2` 封装、`get_userinfo_by_name` |
| [gsz_info.html](/home/enako/dev/py_project/enako-bot-qq/nonebot/src/plugins/gsz-assist/templates/gsz_info.html) | 模板，Chart.js 初始化逻辑 |
| [data_source.py](/home/enako/dev/py_project/enako-bot-qq/nonebot/.venv/lib/python3.12/site-packages/nonebot_plugin_htmlrender/data_source.py) | `html_to_pic` 实现（第三方库，本方案不修改） |

---

## 修复一（核心）：确定性等待 canvas 绘制完成

**目标：** 用「等待所有 canvas 实际渲染出非空白像素」替代固定 `wait=1000` 延时。

**原理：** `html_to_pic` 内部调用 `page.wait_for_timeout(wait)`。我们无法修改第三方库 `data_source.py`，但可以在 `service.py` 中不再依赖 `wait` 参数做确定性等待，而是自己用 Playwright API 直接操作页面。由于 `html_to_pic` 封装了 `get_new_page` 上下文管理器且不暴露 `page` 对象，需要自行调用 `nonebot_plugin_htmlrender` 的底层 API。

### 方案 1A：新增自定义渲染函数（推荐）

在 `service.py` 中新增一个函数，直接使用 `nonebot_plugin_htmlrender` 的 `get_new_page` 和 Playwright 页面 API，在截图前用 `page.wait_for_function` 确认所有 canvas 已绘制完成。

#### 步骤

1. 在 `service.py` 顶部新增导入。`get_new_page` 的实际位置需验证，可能位于：

```python
from nonebot_plugin_htmlrender.browser import get_new_page
```

> 验证导入路径：
> ```
> python -c "from nonebot_plugin_htmlrender.browser import get_new_page; print(get_new_page)"
> ```

2. 在 `service.py` 中（`convert_html_to_pic2` 定义之后，约第 48 行位置）新增函数：

```python
async def convert_html_to_pic_with_chart_wait(
    content: str,
    canvas_ids: list[str],
    max_wait: int = 5000,
) -> BytesIO:
    """渲染 HTML 到图片，等待所有指定 canvas 绘制完成后再截图。

    Args:
        content: HTML 内容
        canvas_ids: 需要等待的 canvas 元素 ID 列表
        max_wait: 最大等待时间（毫秒）
    """
    from nonebot_plugin_htmlrender.browser import get_new_page

    async with get_new_page(2) as page:
        await page.goto(f"file://{template_dir}")
        await page.set_content(content, wait_until="networkidle")
        await page.wait_for_timeout(500)  # 给 Tailwind JIT + DOMContentLoaded 基本时间

        wait_js = """
        (canvasIds) => {
            for (const id of canvasIds) {
                const canvas = document.getElementById(id);
                if (!canvas) return false;
                const ctx = canvas.getContext('2d');
                if (!ctx) return false;
                if (canvas.width <= 0 || canvas.height <= 0) return false;
                try {
                    const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
                    const data = imageData.data;
                    let hasPixels = false;
                    for (let i = 3; i < data.length; i += 4) {
                        if (data[i] !== 0) { hasPixels = true; break; }
                    }
                    if (!hasPixels) return false;
                } catch (e) {
                    return false;
                }
            }
            return true;
        }
        """

        try:
            await page.wait_for_function(
                f"({wait_js})({json.dumps(canvas_ids)})",
                timeout=max_wait,
            )
        except Exception:
            logger.warning(f"图表等待超时 ({max_wait}ms)，继续截图")
            await page.wait_for_timeout(1000)

        return await page.screenshot(
            full_page=True,
            type="jpeg",
            quality=70,
        )
```

3. 需要在 `service.py` 顶部添加 `import json`（当前未导入）。

4. 修改 `get_userinfo_by_name` 中的调用（约第 155 行）：

**修改前：**
```python
pic = await convert_html_to_pic2(content=content)
```

**修改后：**
```python
pic = await convert_html_to_pic_with_chart_wait(
    content=content,
    canvas_ids=["radarChart", "doughnutChart", "rankTrendChart"],
    max_wait=5000,
)
```

5. 保留 `convert_html_to_pic` / `convert_html_to_pic2` 不变，其他方法（`get_rank_top`、`get_rank_last`、`get_rank_list`）不受影响。

### 方案 1B：仅增大 wait 值（最小改动，缓解而非根治）

如果不想引入 `get_new_page` 直接操作，可以将 `convert_html_to_pic2` 的 `wait` 从 `1000` 增大到 `3000`：

**修改位置：** `service.py` 约第 46 行

```python
wait=3000,  # 原 1000
```

**效果：** 降低出现概率，但无法根治。Tailwind JIT 在高负载机器上可能仍超过 3 秒。

> **建议：** 优先采用方案 1A。1B 可作为临时缓解手段。

---

## 修复二（纵深防御）：模板侧加固

### 2A：为图表容器添加固定尺寸 inline style

**目标：** 减少 canvas 容器对 Tailwind class 的依赖，使布局在 Tailwind 编译前就是最终状态。

**修改文件：** [gsz_info.html](/home/enako/dev/py_project/enako-bot-qq/nonebot/src/plugins/gsz-assist/templates/gsz_info.html)

**修改位置 1 — 折线图容器（约第 132 行）：**

已有 inline style `height: 125px; width: 66.67%`，无需改动。

**修改位置 2 — 雷达图 / 饼图容器（约第 148-155 行）：**

**修改前：**
```html
<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
    <div class="card bg-base-100 shadow-xl p-4">
        <h3 class="text-lg font-bold mb-4"></h3>
        <canvas id="radarChart"></canvas>
    </div>
    <div class="card bg-base-100 shadow-xl p-4">
        <h3 class="text-lg font-bold mb-4"></h3>
        <canvas id="doughnutChart"></canvas>
    </div>
</div>
```

**修改后：**
```html
<div class="grid grid-cols-1 md:grid-cols-2 gap-4"
     style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
    <div class="card bg-base-100 shadow-xl p-4"
         style="background: white; border-radius: 0.75rem; padding: 16px;">
        <h3 class="text-lg font-bold mb-4"></h3>
        <canvas id="radarChart"></canvas>
    </div>
    <div class="card bg-base-100 shadow-xl p-4"
         style="background: white; border-radius: 0.75rem; padding: 16px;">
        <h3 class="text-lg font-bold mb-4"></h3>
        <canvas id="doughnutChart"></canvas>
    </div>
</div>
```

> **原理：** inline style 在 Tailwind JIT 编译前就生效，容器尺寸不再依赖 Tailwind 异步注入。即使 Tailwind 后续注入了相同规则的 CSS，也不会导致布局变化（因为值相同），从而避免触发 ResizeObserver 重绘。

### 2B：在 Chart.js 初始化后手动调用 `chart.resize()`

**目标：** 在 DOMContentLoaded 回调中，初始化所有图表后立即手动触发一次 resize，确保 Chart.js 在当前容器尺寸下同步绘制。

**修改文件：** [gsz_info.html](/home/enako/dev/py_project/enako-bot-qq/nonebot/src/plugins/gsz-assist/templates/gsz_info.html)

**修改位置：** DOMContentLoaded 回调（约第 637-649 行）

**修改前：**
```javascript
document.addEventListener('DOMContentLoaded', async function() {
    try {
        const data = fetchData();
        updatePlayerInfo(data.basicData, data.rateListData);
        initRadarChart(data.techData);
        initDoughnutChart(data.techData);
        initRankTrendChart(data.ratePageData, data.basicData.name);
        updateRankHistory(data.rateListData, data.basicData);
    } catch (error) {
        console.error('初始化失败:', error);
    }
});
```

**修改后：**
```javascript
document.addEventListener('DOMContentLoaded', async function() {
    try {
        const data = fetchData();
        updatePlayerInfo(data.basicData, data.rateListData);
        const radarChart = initRadarChart(data.techData);
        const doughnutChart = initDoughnutChart(data.techData);
        const rankTrendChart = initRankTrendChart(data.ratePageData, data.basicData.name);
        updateRankHistory(data.rateListData, data.basicData);

        // 主动触发一次 resize，确保 Chart.js 在当前容器尺寸下同步重绘
        requestAnimationFrame(() => {
            if (radarChart) radarChart.resize();
            if (doughnutChart) doughnutChart.resize();
            if (rankTrendChart) rankTrendChart.resize();
        });
    } catch (error) {
        console.error('初始化失败:', error);
    }
});
```

> **原理：** `chart.resize()` 是同步方法，会立即根据当前容器尺寸重新计算并绘制。用 `requestAnimationFrame` 包裹是为了确保在 Tailwind 可能注入 CSS 后的下一帧执行，此时容器尺寸已经是最终值。结合修复一（确定性等待），双重保障。

### 2C：设置全局 window 标记供 Playwright 轮询

**目标：** 提供一个更可靠的 JS 侧「所有图表已绘制」信号。

**修改文件：** [gsz_info.html](/home/enako/dev/py_project/enako-bot-qq/nonebot/src/plugins/gsz-assist/templates/gsz_info.html)

在 DOMContentLoaded 回调中添加 `window.__chartsReady` 标记。完整修改后的回调：

```javascript
document.addEventListener('DOMContentLoaded', async function() {
    window.__chartsReady = false;
    try {
        const data = fetchData();
        updatePlayerInfo(data.basicData, data.rateListData);
        const radarChart = initRadarChart(data.techData);
        const doughnutChart = initDoughnutChart(data.techData);
        const rankTrendChart = initRankTrendChart(data.ratePageData, data.basicData.name);
        updateRankHistory(data.rateListData, data.basicData);

        requestAnimationFrame(() => {
            if (radarChart) radarChart.resize();
            if (doughnutChart) doughnutChart.resize();
            if (rankTrendChart) rankTrendChart.resize();
            window.__chartsReady = true;
        });
    } catch (error) {
        console.error('初始化失败:', error);
        window.__chartsReady = true;  // 即使失败也标记为 ready，避免死等
    }
});
```

如果使用了此标记，方案 1A 中的 `wait_for_function` 可以简化为：

```python
await page.wait_for_function("() => window.__chartsReady === true", timeout=max_wait)
await page.wait_for_timeout(200)  # 确保 rAF 回调中的 resize() 完全执行
```

---

## 修复三：修正 `get_userinfo_by_name` 异常处理缺陷

**目标：** 修复 API 请求失败后变量未定义导致 `UnboundLocalError` 的 bug。

**修改文件：** [service.py](/home/enako/dev/py_project/enako-bot-qq/nonebot/src/plugins/gsz-assist/service.py)

**修改位置：** 约第 103-120 行，`get_userinfo_by_name` 方法的 `try/except` 块

**问题：** `try/except` 块捕获异常后仅 `logger.debug`，不 re-raise 也不 return，代码继续执行到模板渲染部分。此时 `basic_data` 等变量可能未定义。

**修改前：**
```python
        except httpx.ConnectError as e:
            logger.debug(f"连接失败：{e}")
        except httpx.ReadTimeout as e:
            logger.debug(f"读取超时：{e}")
        except httpx.HTTPStatusError as e:
            logger.debug(f"响应状态码错误: {e.response.status_code}")
        except httpx.RequestError as e:
            logger.debug(f"请求失败：{e}")
        except Exception as e:
            logger.debug(f"其他错误：{e}")
```

**修改后（在每个 except 块中添加 `raise`）：**
```python
        except httpx.ConnectError as e:
            logger.debug(f"连接失败：{e}")
            raise
        except httpx.ReadTimeout as e:
            logger.debug(f"读取超时：{e}")
            raise
        except httpx.HTTPStatusError as e:
            logger.debug(f"响应状态码错误: {e.response.status_code}")
            raise
        except httpx.RequestError as e:
            logger.debug(f"请求失败：{e}")
            raise
        except Exception as e:
            logger.debug(f"其他错误：{e}")
            raise
```

或者更简洁的方式，将整个 except 块合并并 re-raise：

```python
        except Exception as e:
            logger.debug(f"API请求失败：{e}")
            raise
```

> **注意：** `get_userinfo_by_name` 的调用方（`__init__.py` 中的 `get_gsz_userinfo_handler`）需要捕获此异常并向用户返回友好的错误提示，而非让 bot 崩溃。需检查 `__init__.py` 中的处理逻辑是否已有 try/except。

---

## 修复优先级与实施建议

| 优先级 | 修复项 | 效果 | 风险 |
|--------|--------|------|------|
| P0 | 修复一（方案 1A）+ 修复二（2C） | 根治图表缺失 | 需验证 `get_new_page` 导入路径；增加最多 5 秒等待（实际通常 <1 秒） |
| P1 | 修复二（2A + 2B） | 纵深防御，降低对确定性等待的依赖 | inline style 可能与 Tailwind class 冲突，需视觉验证 |
| P2 | 修复三 | 修复 API 失败时的崩溃 bug | 需确认调用方异常处理 |
| P3 | 修复一（方案 1B） | 临时缓解 | 仅降低概率，不根治 |

### 推荐实施路径

1. 先做修复二 2A + 2B（模板侧，零风险，不涉及 Python 代码）
2. 再做修复二 2C + 修复一 1A（确定性等待，根治问题）
3. 最后做修复三（异常处理，需同步检查 `__init__.py` 调用方）

### 验证方法

实施后用以下方式验证：

1. **手动测试：** 反复调用 `/吃鱼` 命令 20 次以上，确认图表不再缺失
2. **对比图片大小：** 图表缺失的 JPEG 通常比正常的小 30-50KB（因为大片白色区域压缩率更高），可以对比多次生成的图片字节数
3. **可选自动化验证脚本：**
   ```python
   import asyncio
   from nonebot.src.plugins.gsz_assist.service import GszService

   async def test():
       for i in range(20):
           pic = await GszService.get_userinfo_by_name("测试用户名")
           print(f"Run {i+1}: {len(pic.getvalue())} bytes")

   asyncio.run(test())
   ```

---

## 附录：实施前验证检查点

确认 `get_new_page` 导入路径可用：

```bash
python -c "from nonebot_plugin_htmlrender.browser import get_new_page; print('OK')"
```

如果不可用，检查实际路径：

```bash
rg -n "def get_new_page" .venv/lib/python3.12/site-packages/nonebot_plugin_htmlrender/
```
