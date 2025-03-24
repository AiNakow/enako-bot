# 段位排行榜

| 排名 | 玩家名称 | 段位 | RATE | 雀庄 | 平均点数 | 升段均顺 | 升段局 | 总局数 | 一位率 | 二位率 | 三位率 | 四位率 |
|------|----------|------|------|------|----------|----------|--------|--------|--------|--------|--------|--------|
{% for record in rank_data %}| {{ loop.index }} | {{ record.name }} | {{ record.rankName }} | {{ record.rate }} | {{ record.rateName }} | {{ record.avgPoint }} | {{ "%.2f"|format(record.upAvgPosition or 0) }} | {{ record.upRate or 0 }} | {{ record.totalRate }} | {{ "%.1f"|format((record.position1 or 0) / record.totalRate * 100) }}% | {{ "%.1f"|format((record.position2 or 0) / record.totalRate * 100) }}% | {{ "%.1f"|format((record.position3 or 0) / record.totalRate * 100) }}% | {{ "%.1f"|format((record.position4 or 0) / record.totalRate * 100) }}% |
{% endfor %} 