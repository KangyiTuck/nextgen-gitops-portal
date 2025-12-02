# NextGen GitOps 效能平台

一个轻量级内部开发者平台（Internal Developer Platform, IDP），聚焦 DevOps 全链路转型赋能，实现从代码提交、构建验证到生产灰度发布的全流程零触达自动化，大幅降低中小团队 DevOps 落地门槛与运维成本。

## 一、项目简介

### 1.1 核心定位

基于银行等金融级场景20+系统CI/CD落地经验，整合主流开源技术栈封装的GitOps效能平台脚手架。目标是降低中小团队DevOps工具链集成与运维成本，无需从零搭建，通过简单配置即可启用核心功能。实际落地中，交付效率提升因团队基础而异，一般可实现2-3倍提升（需配合团队流程优化）。

### 1.2 设计理念

- **自助化**：开发者通过 Portal 界面自主完成环境申请、应用部署，无需依赖运维团队介入

- **自动化**：全链路零人工干预，覆盖代码提交触发构建、自动测试、环境部署、灰度发布、故障回滚全流程

- **可度量**：内置 DORA 四键指标监控，量化 DevOps 效能，精准识别流程瓶颈

- **可扩展**：预留信创生态与第三方工具集成接口，当前已完成基础适配，企业级定制需结合实际场景开发

## 二、核心功能

### 2.1 自助式应用部署

- 提供可视化 Portal UI，支持开发者一键申请 Kubernetes 开发/测试/生产环境

- 兼容 Helm Chart 部署规范与 ArgoCD 风格的声明式配置管理

- 支持应用命名空间自动创建、资源配额管理、环境隔离配置

- 内置基础应用模板库（含微服务、单体应用常用配置），复杂场景需基于模板二次定制

### 2.2 CI/CD 全链路自动化

- 集成 GitLab CI + Tekton Pipeline，实现代码提交自动触发构建、单元测试、镜像构建与推送

- 支持金丝雀发布、蓝绿发布等多种灰度策略，满足不同风险等级的发布需求

- 优化故障回滚流程，核心场景回滚时间可控制在2分钟内（需依赖镜像仓库与配置存储稳定）

- 内置 Pipeline 模板与自定义扩展能力，适配不同技术栈（Java/Go/Python 等）构建需求

### 2.3 效能度量与监控

- 基于 Prometheus + Grafana 构建 DORA 四键指标看板，实时展示部署频率、变更前置时间、服务恢复时间、变更失败率

- 支持构建时间、部署耗时等关键环节耗时统计，在已落地的3个中小团队场景中，平均实现构建时间降低40%-62%（因代码规模与构建环境有差异）

- 提供应用运行状态监控、Pipeline 执行日志可视化、故障告警等能力

### 2.4 信创适配与扩展能力

- 集成90+个Python编写的信创采集脚本，已在测试环境验证达梦数据库、华为存储的指标采集与状态监控，生产环境适配需额外做兼容性测试

- 适配达梦数据库、华为存储等信创生态组件，满足国产化部署需求

- 提供标准化扩展接口，支持集成企业内部现有工具（如工单系统、权限管理系统）

## 三、技术架构

### 3.1 核心技术栈

- **容器编排**：Kubernetes（基于 Talos Linux 优化部署，提升集群安全性与稳定性）

- **GitOps 工具**：FluxCD（集群配置同步）、ArgoCD（应用部署管理）

- **CI/CD 引擎**：GitLab CI（代码触发）、Tekton Pipeline（流水线编排）

- **监控与度量**：Prometheus（指标采集）、Grafana（可视化看板）、Loki（日志收集）

- **存储方案**：支持 Rook-Ceph、OpenEBS 等容器附加存储，适配华为存储信创场景

- **网络组件**：Cilium CNI（网络策略）、MetalLB（裸金属负载均衡）

- **安全组件**：Kyverno（策略管控）、SOPS（密钥加密）

- **开发语言**：Python（信创脚本、后端接口）、Go（核心组件扩展）、前端（React/Vue）

### 3.2 架构分层

1. **基础设施层**：Talos Linux 操作系统 + Kubernetes 集群，提供稳定的容器运行环境

2. **核心工具层**：FluxCD/ArgoCD、Tekton、Prometheus 等开源工具，构成 GitOps 核心能力底座

3. **平台能力层**：自助部署 Portal、CI/CD 流水线管理、效能度量看板、信创适配模块

4. **应用接入层**：支持多语言应用接入，提供标准化部署与构建模板

## 四、快速启动

### 4.1 前置依赖

- 操作系统：Linux/macOS（Windows 需开启 WSL2）

- 必备工具：minikube v1.30+、kubectl v1.25+、git、flux v2.0+

- 资源要求：本地环境至少 4C8G 内存（推荐 8C16G）

- 代码仓库：GitHub/GitLab 账号（用于存储 GitOps 配置）

### 4.2 部署步骤

```Plain Text
# 1. 启动本地 Kubernetes 集群（minikube）
# 注意：需提前配置国内镜像源，否则可能出现镜像拉取失败
minikube start --memory=8192 --cpus=4 --disk-size=40g --image-mirror-country=cn

# 2. 初始化 FluxCD（关联代码仓库，同步集群配置）
# 前提：GitHub账号需配置SSH密钥或个人访问令牌（repo权限）
flux bootstrap github \
  --owner=你的用户名 \
  --repository=nextgen-gitops-portal \
  --branch=main \
  --path=./clusters/my-cluster \
  --personal

# 3. 等待核心组件部署完成（网络环境影响较大，约5-20分钟）
# 可通过以下命令实时查看部署状态
watch kubectl get pods -n flux-system
watch kubectl get pods -n tekton-pipelines
# 所有pod状态为Running后执行后续步骤
kubectl wait --for=condition=ready pod -n flux-system --all --timeout=300s
kubectl wait --for=condition=ready pod -n tekton-pipelines --all --timeout=300s

# 4. 访问 Grafana 效能看板（默认账号密码：admin/admin，首次登录需修改）
kubectl port-forward -n monitoring svc/grafana 3000:80
# 浏览器访问：http://localhost:3000
# 若访问失败，检查grafana pod是否正常运行：kubectl get pods -n monitoring
```

### 4.3 首次使用指引

1. 访问 Portal UI：部署完成后执行 kubectl port-forward -n portal svc/portal 8080:80（默认地址：http://localhost:8080），若未找到服务，检查portal命名空间是否创建

2. 通过「应用管理」模块创建应用，选择对应部署模板（Helm方式需提前准备Chart包或配置Chart仓库）

3. 关联GitLab代码仓库：需配置GitLab访问令牌（api、read_repository权限），触发规则建议先在测试分支验证

4. 在「环境管理」中申请测试环境，首次部署建议先查看Pipeline执行日志（kubectl logs -n tekton-pipelines -l app=tekton-pipelines-controller -f）

5. 通过Grafana看板查看部署进度与效能指标，部分指标需运行1-2个完整部署流程后才会生成数据

## 五、贡献指南

1. Fork本仓库到个人账号，建议先同步主分支最新代码

2. 创建特性分支：git checkout -b feat/xxx（功能开发）或fix/xxx（问题修复），分支命名清晰易懂

3. 提交代码：遵循Conventional Commits规范，提交信息需明确说明变更内容（如feat(portal): 新增环境申请审批流程），避免模糊表述

4. 执行预提交校验：pre-commit run --all-files，修复所有校验报错（重点关注yamllint、shellcheck报错）

5. 创建Pull Request：详细描述功能变更点、测试场景与结果，附上相关截图（如界面变更、日志输出），等待审核反馈

6. 审核通过后合并分支，合并前需确保与主分支无冲突



## 为什么建这个？

空窗期自驱项目，基于生产经验（银行20+系统CI/CD落地）扩展开源starter，目标：让中小团队交付速度x5。

贡献欢迎！🚀

