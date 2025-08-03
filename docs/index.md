---
layout: home

hero:
  name: "LoveACE"
  text: "教务系统自动化工具"
  tagline: "简化学生教务操作，提高使用效率"
  image:
    src: /images/logo.jpg
    alt: LoveACE Logo
  actions:
    - theme: brand
      text: 快速开始
      link: /getting-started
    - theme: alt
      text: API文档
      link: /api/

features:
  - icon: 🔐
    title: 用户认证与授权
    details: 支持邀请码注册和用户登录，确保系统安全
  - icon: 📚
    title: 教务系统集成
    details: 学业信息查询、培养方案信息查询、课程列表查询
  - icon: ⭐
    title: 自动评教系统（开发中）
    details: 支持评教任务的初始化、开始、暂停、终止和状态查询
  - icon: 💯
    title: 爱安财系统
    details: 总分信息查询和分数明细列表查询
  - icon: 🚀
    title: 高性能架构
    details: 基于FastAPI和异步SQLAlchemy构建，支持高并发访问
  - icon: 📖
    title: 完整文档
    details: 提供详细的API文档、配置指南和部署教程
---

## 技术栈

- **后端框架**: FastAPI
- **数据库ORM**: SQLAlchemy (异步)
- **HTTP客户端**: 基于aiohttp的自定义客户端
- **日志系统**: richuru (rich + loguru)

## 快速体验

```bash
# 克隆项目
git clone https://github.com/LoveACE-Team/LoveACE.git
cd LoveACE

# 安装依赖
pdm install

# 配置数据库
启动 App 生成配置文件并编辑：

```bash
python main.py
```

编辑`config.json`文件，配置以下关键参数：

```json
{
  "database": {
    "url": "mysql+aiomysql://username:password@host:port/database"
  },
  "app": {
    "host": "0.0.0.0",
    "port": 8000
  }
}

# 启动服务
uvicorn main:app --reload
```

## 社区

如果您有任何问题或建议，欢迎：

- 📝 [提交Issue](https://github.com/LoveACE-Team/LoveACE/issues)
- 🔀 [发起Pull Request](https://github.com/LoveACE-Team/LoveACE/pulls)
- 💬 加入讨论组

## 许可证

本项目采用 MIT 许可证开源。详情请查看 [LICENSE](https://github.com/LoveACE-Team/LoveACE/blob/main/LICENSE) 文件。