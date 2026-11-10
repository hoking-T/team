# 智慧仓储与物流协同系统

## 项目简介

本项目是一个**仓库管理系统**，支持：
- 入库
- 在库管理
- 出库

## 团队分工

| 成员 | GitHub 用户名 | 负责模块 | 分支 |
|------|--------------|----------|------|
| 陶豪情 | hoking-T | 用户登录/注册 | feature/user-auth |
| 成员B | （填队友真实信息） | （待填） | feature/xxx |
| 成员C | （填队友真实信息） | （待填） | feature/xxx |

## 技术栈

Java 21 · Spring Boot 3 · Spring Data JPA · MySQL

## 本地运行

.\mvnw.cmd spring-boot:run

## 协作规范

- main 分支保持可运行，禁止直接在 main 上开发
- 功能开发一律走 feature/ 分支 → PR → Review → 合并
- commit message 格式：feat/fix/docs/refactor/chore: 描述