# 成分扫一扫（Rihua Ingredient Analyzer）

> 看清商品真实的样子 —— 上传配料表图片，30 秒看懂成分优缺点、风险预警与替代建议。

面向日化洗护产品（洗发水、牙膏、沐浴露、护肤品等）的成分分析工具。用户拍照上传产品配料表，系统自动 OCR 识别文字，匹配本地成分数据库，并调用大模型生成优缺点分析、评分和购买建议。

## 核心功能

- **拍照识成分**：上传配料表图片，OCR 自动识别 + 智能匹配 264 种成分库
- **优缺点分析**：大模型生成产品优点、缺点、综合评分（0-100）和一句话总结
- **成分详情弹窗**：点击任意成分查看分类、风险等级、说明和法规出处
- **成分风险分布饼图**：直观展示安全/注意/慎用/规避的比例
- **评分等级说明**：优秀（86+）/良好（76-85）/一般（60-75）/不推荐（<60）
- **智能预警**：
  - **成分冲突检测**：识别危险组合（如视黄醇+水杨酸、烟酰胺+VC）
  - **过敏原自动预警**：用户标记过敏成分后，扫描命中时醒目提示
  - **成分替代建议**：为慎用成分推荐更温和的替代选择
- **法规检索**：按名称/分类/风险/法规出处搜索成分库
- **历史记录**：保存扫描记录，支持多产品对比、评分趋势图
- **PDF 报告导出**：生成包含品类、评分、优缺点、成分清单的分析报告
- **移动端适配**：响应式设计，手机浏览器可正常使用

## 技术栈

| 层 | 技术 |
|------|------|
| 后端 | Python 3.11+、FastAPI、SQLite |
| 前端 | React 18、TypeScript、Vite、Tailwind CSS、Recharts |
| OCR | 百度云文字识别（高精度版） |
| LLM | DeepSeek Chat API |
| PDF | ReportLab（STSong-Light 中文字体） |

## 项目结构

```
rihua-ingredient-analyzer/
├── backend/                    # 后端 FastAPI 服务
│   ├── app/
│   │   ├── api/routes.py        # API 路由（分析/历史/对比/PDF/检索/过敏原）
│   │   ├── models/schemas.py   # Pydantic 数据模型
│   │   ├── services/
│   │   │   ├── ocr.py           # 百度云 OCR 服务
│   │   │   ├── llm.py           # DeepSeek LLM 分析服务
│   │   │   ├── ingredient.py    # 成分匹配 + 264 种成分库
│   │   │   ├── interaction.py   # 成分冲突 + 替代建议规则
│   │   │   └── pdf_service.py   # PDF 报告生成
│   │   ├── database.py          # SQLite（成分/缓存/历史/过敏原）
│   │   ├── limiter.py           # 接口限流（slowapi）
│   │   ├── config.py            # 环境变量配置
│   │   ├── main.py              # FastAPI 应用入口
│   │   └── seed.py              # 成分库导入脚本
│   ├── requirements.txt
│   └── .env.example             # 环境变量示例
├── frontend/                   # 前端 React 应用
│   ├── src/
│   │   ├── App.tsx              # 首页 + 结果页 + 成分详情弹窗
│   │   ├── History.tsx          # 历史记录 + 对比 + 趋势图
│   │   ├── IngredientSearch.tsx # 法规检索页
│   │   ├── AllergenSettings.tsx # 过敏原设置页
│   │   └── index.css            # 全局样式 + 移动端适配
│   ├── vite.config.ts
│   └── package.json
├── docs/                       # 设计文档
├── pictures/                   # 测试图片
└── render.yaml                 # 部署配置
```

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+
- 百度云 OCR API Key
- DeepSeek API Key

### 后端启动

```bash
cd backend

# 创建虚拟环境
python -m venv rihua_production
# Windows
rihua_production\Scripts\activate
# Linux/Mac
source rihua_production/bin/activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量（复制 .env.example 并填写）
cp .env.example .env
# 编辑 .env 填入以下变量：
#   BAIDU_API_KEY=你的百度云API Key
#   BAIDU_Secret_Key=你的百度云Secret Key
#   DEEPSEEK_API_KEY=你的DeepSeek API Key

# 首次运行：导入成分库到 SQLite
python -m app.seed

# 启动服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 前端启动

```bash
cd frontend

# 安装依赖
npm install

# 开发模式
npm run dev

# 生产构建
npm run build
```

启动后访问 http://localhost:5173

### 手机访问

前端监听 `0.0.0.0:5173`，手机和电脑连接同一 WiFi，用手机浏览器访问：

```
http://<电脑局域网IP>:5173/
```

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/analyze` | 分析配料表图片（限流 5次/分钟） |
| GET | `/api/history` | 获取历史记录列表 |
| GET | `/api/history/{id}` | 获取历史记录详情 |
| DELETE | `/api/history/{id}` | 删除一条历史记录 |
| DELETE | `/api/history` | 清空全部历史记录 |
| GET | `/api/compare?ids=1,2,3` | 对比多条历史记录 |
| GET | `/api/report/{id}` | 导出 PDF 报告 |
| GET | `/api/ingredients/search` | 检索成分库 |
| GET | `/api/allergens` | 获取过敏原列表 |
| POST | `/api/allergens` | 添加过敏原 |
| DELETE | `/api/allergens/{name}` | 删除过敏原 |

## 成分数据库

收录 **264 种**日化洗护常见成分，覆盖 10 大类：

- 表面活性剂、防龋成分、防腐剂、保湿剂、溶剂、增稠剂
- 香精/色素、活性成分（护肤）、防晒剂、染发剂等

风险等级：**安全** / **注意** / **慎用** / **规避**

法规来源：《化妆品安全技术规范》(2015版)、《牙膏用原料规范》GB 22115-2008、CIR 评估、IFRA 标准、欧盟化妆品法规等。

## 数据来源与免责声明

- 成分数据来源于公开法规和评估报告，仅供参考
- 分析结果不替代专业医疗建议
- 实际使用感受因人而异
- 如有严重过敏史，请咨询专业医生

## 许可证

本项目采用 [MIT License](LICENSE) 开源协议。

## 仓库

- GitHub: https://github.com/kurkobin/rihua-ingredient-analyzer
