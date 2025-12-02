# CLAUDE.md

本文档为 Claude Code（claude.ai/code）工具提供操作指引，用于辅助该代码仓库的相关开发与运维工作。

## 一、仓库概述

本仓库是面向个人家庭实验室集群的 Kubernetes GitOps 仓库，基于 FluxCD（GitOps 工具）和 Talos Linux（Kubernetes 专用操作系统）实现集群管理。集群采用企业级安全与可观测性实践，集成了云原生计算基金会（CNCF）生态系统中的多款主流工具。

## 二、架构说明

- **操作系统**：Talos Linux（轻量级、不可变的 Kubernetes 专用操作系统）

- **GitOps 工具**：FluxCD（搭配 Flux Operator 实现声明式集群管理）

- **容器运行时**：containerd（容器标准化运行环境）

- **网络组件**：Cilium CNI（容器网络接口）+ Istio 服务网格

- **存储方案**：Rook-Ceph、OpenEBS、democratic-csi（容器附加存储解决方案）

- **可观测性工具**：Prometheus（指标采集）、Grafana（可视化）、Loki（日志收集）、Jaeger（链路追踪）、Thanos（指标长期存储）

- **安全组件**：Kyverno、OPA Gatekeeper（策略管理）；Falco、Tetragon（运行时安全）

- **负载均衡**：MetalLB（裸金属环境负载均衡工具）

- **混沌工程**：Litmus（混沌测试工具，用于验证系统稳定性）

## 三、目录结构

```bash
├── kubernetes/                       # Kubernetes 清单与配置文件
│   ├── apps/
│   │   ├── base/                     # 应用基础配置（遵循DRY原则：避免重复）
│   │   │   └── [system-name]/        # 系统分类目录（如：observability、kube-system）
│   │   │       ├── [app-name]/
│   │   │       │   ├── app/          # HelmRelease、OCI仓库、密钥、价值观配置
│   │   │       │   └── ks.yaml       # 带依赖的 Flux Kustomization 配置
│   │   │       ├── namespace.yaml    # 命名空间定义
│   │   │       └── kustomization.yaml # Kustomize 配置文件
│   │   └── overlays/
│   │       └── cluster-00/           # 集群专属覆盖配置（cluster-00为默认集群）
│   ├── bootstrap/
│   │   └── helmfile.yaml             # 初始化 Flux Operator 及依赖组件
│   ├── clusters/
│   │   └── cluster-00/
│   │       ├── flux-system/          # Flux Operator 与 FluxInstance 配置
│   │       ├── secrets/              # 集群密钥（SOPS 加密存储）
│   │       └── ks.yaml               # 根级 Kustomization 配置
│   ├── components/
│   │   └── common/alerts/            # 共享监控告警规则
│   └── tenants/                      # 多租户配置
├── talos/                            # Talos Linux 配置文件
│   ├── generated/                    # 生成的 Talos 配置（加密存储）
│   ├── integrations/                 # Cilium、cert-approver 集成配置
│   └── patches/                      # iSCSI、指标采集相关补丁
├── terraform/                        # 基础设施即代码（IaC）目录
│   ├── cloudflare/                   # Cloudflare DNS/CDN 配置
│   └── gcp/                          # GCP 相关配置（KMS加密、Thanos存储、Velero备份）
├── scripts/                          # 辅助脚本
│   ├── cicd/                         # CI/CD 流水线脚本
│   └── sinicization/                 # 信创适配采集脚本（Python）
├── .taskfiles/                       # 任务自动化定义文件
└── docs/                             # 项目文档
```

## 四、常用命令

### 4.1 任务管理（核心构建系统）

本仓库使用 [Task](https://taskfile.dev) 工具实现自动化操作，所有命令需通过 `task` 指令执行：

```bash
# FluxCD 操作
task flux:bootstrap          # 通过 Helmfile 初始化 Flux Operator
task flux:secrets           # 安装集群密钥（SOPS解密 + 应用配置）
task fluxcd:bootstrap       # 备选初始化方式
task fluxcd:diff            # 预览 FluxCD 操作器变更内容

# Talos 操作
task talos:config           # 解密并加载 talosconfig 至 ~/.talos/config

# 核心操作
task core:gpg               # 导入 SOPS PGP 密钥
task core:lint              # 执行 yamllint 语法校验

# 查看所有可用任务
task --list
```

**重要环境变量**：

- CLUSTER：默认集群ID（cluster-00）

- GITHUB_USER：仓库所属用户（xunholy）

- GITHUB_REPO：仓库名称（k8s-gitops）

- GITHUB_BRANCH：主分支（main，FluxCD 自动同步此分支配置）

### 4.2 预提交钩子（pre-commit Hooks）

仓库通过 pre-commit 工具保障代码质量，执行以下命令触发所有校验规则：

```bash
pre-commit run --all-files   # 执行所有预提交校验钩子
```

启用的校验钩子包括：

- YAML/JSON/TOML 格式验证

- yamllint 语法校验（配置文件：.yamllint.yaml）

- shellcheck 脚本校验（针对 Shell 脚本）

- 尾随空格与文件结尾格式修复

### 4.3 密钥管理

密钥通过 [SOPS](https://github.com/mozilla/sops) 工具加密存储（双重加密：PGP + GCP KMS），操作命令如下：

```bash
# 编辑加密文件（自动解密/加密）
sops path/to/file.enc.yaml

# 仅解密查看（不修改）
sops -d path/to/file.enc.yaml
```

**SOPS 配置详情**：

- PGP 密钥：0635B8D34037A9453003FB7B93CAA682FF4C9014

- Age 密钥：age19gj66fq5v2veu940ftyj4pkw0w5tgxgddlyqnd00pnjzyndevurqx70g4t

- GCP KMS：用于存储 PGP 密钥备份

- 加密文件后缀：.enc.yaml 或 .enc.age.yaml

## 五、核心技术与实践模式

### 5.1 FluxCD GitOps 实践

本仓库采用 **Flux Operator** 替代传统的 `flux bootstrap` 方式，核心特性包括：

- FluxInstance CRDs：通过自定义资源（CRD）声明式管理 FluxCD 组件

- OCIRepository：使用 OCI 仓库存储 Helm 图表（替代传统 HelmRepository，示例：oci://ghcr.io/prometheus-community/charts）

- Kustomizations：定义清单应用规则，支持 SOPS 解密、构建后变量替换及依赖链管理

- HelmReleases：通过 `chartRef` 关联 OCIRepository 中的 Helm 图表

- 根级 Kustomization：路径为 kubernetes/clusters/cluster-00/ks.yaml，作为集群配置入口

### 5.2 应用部署模式

所有应用均遵循以下标准化部署结构：

1. **基础配置**（路径：kubernetes/apps/base/[system-name]/[app-name]/）：
       app/helmrelease.yaml：Helm 发布定义

2. app/ocirepository.yaml：Helm 图表的 OCI 仓库源

3. app/secret.enc.yaml：加密存储的应用密钥

4. app/values.yaml：Helm 图表配置参数

5. ks.yaml：Flux Kustomization 配置（包含依赖声明、SOPS 解密设置、变量替换规则）

6. **集群覆盖配置**（路径：kubernetes/apps/overlays/cluster-00/）：通过 Kustomize 补丁实现集群专属定制化

7. **系统分类规范**：应用按功能划分为以下系统目录：
       kube-system：Kubernetes 核心组件（如 Cilium、metrics-server、reflector）

8. network-system：网络相关组件（如 cert-manager、external-dns、oauth2-proxy、dex）

9. observability：可观测性工具（如 Prometheus、Grafana、Loki、Jaeger、Thanos）

10. security-system：安全组件（如 Kyverno、Falco、Gatekeeper、Crowdsec）

11. istio-system & istio-ingress：Istio 服务网格相关组件

12. home-system：家庭自动化与媒体应用

13. rook-ceph：存储解决方案相关组件

### 5.3 HelmRelease 全局默认配置

通过 Kustomization 全局补丁为所有 HelmReleases 应用以下默认配置：

```yaml
install:
  crds: CreateReplace
  createNamespace: true
  replace: true
  strategy: RetryOnFailure
  timeout: 10m
rollback:
  recreate: true
  force: true
  cleanupOnFail: true
upgrade:
  cleanupOnFail: true
  crds: CreateReplace
  remediation:
    remediateLastFailure: true
    retries: 3
    strategy: rollback
```

### 5.4 安全实践规范

- 双重加密机制：SOPS 结合 PGP（主加密方式）和 GCP KMS（备份加密方式）

- 密钥存储禁忌：严禁提交未加密的密钥文件，所有密钥必须使用 .enc.yaml 后缀

- 策略强制：通过 Kyverno 和 OPA Gatekeeper 实现集群策略管控

- 运行时安全：通过 Falco 和 Tetragon 监控容器运行时风险行为

- Pod 安全标签：所有命名空间均配置 Pod 安全标准标签

- 不可变操作系统：采用 Talos Linux 减少攻击面

## 六、开发工作流

### 6.1 新集群初始化流程

```bash
# 1. 设置环境变量（CLUSTER_ID 默认为 cluster-00）
# 2. 初始化 Flux Operator
task fluxcd:bootstrap  # 安装 flux-operator、flux-instance、cert-manager、kustomize-mutating-webhook

# 3. 安装集群密钥
task flux:secrets      # 解密并应用 sops-gpg、sops-age、cluster-secrets、github-auth、cluster-config

# 4. 配置 Talos
task talos:config      # 解密 talosconfig 并加载至 ~/.talos/config
```

### 6.2 应用配置修改流程

1. 在 kubernetes/apps/base/[system-name]/[app-name]/ 目录下编辑基础配置

2. 如需集群专属定制，在 kubernetes/apps/overlays/cluster-00/ 目录下添加覆盖配置

3. 遵循文件命名规范：
       ks.yaml：Flux Kustomization 资源配置（定义清单应用方式）

4. kustomization.yaml：Kustomize 配置（定义包含的资源清单）

5. *.enc.yaml：SOPS 加密文件

6. helmrelease.yaml：Helm 发布定义

7. ocirepository.yaml：OCI 仓库源配置

8. 提交前确保密钥已加密（使用 sops 命令处理）

9. 执行预提交校验：pre-commit run --all-files

10. 推送代码后，FluxCD 会自动从 main 分支同步配置

### 6.3 新增应用部署流程

1. 创建目录结构：kubernetes/apps/base/[system-name]/[app-name]/

2. 添加 app/ 子目录，包含以下文件：
       helmrelease.yaml（通过 chartRef 关联 OCIRepository 中的图表）

3. ocirepository.yaml（Helm 图表的 OCI 仓库源）

4. values.yaml（Helm 图表配置参数）

5. secret.enc.yaml（如需密钥，通过 SOPS 加密）

6. kustomization.yaml（Kustomize 资源配置）

7. 创建 ks.yaml 文件，包含：
       dependsOn：依赖组件声明（定义部署顺序）

8. decryption：SOPS 密钥解密配置

9. postBuild.substituteFrom：ConfigMap/Secret 变量引用配置

10. 将应用添加到上级目录的 kustomization.yaml 中

11. 如需集群专属配置，创建对应的 overlay 覆盖文件

## 七、核心规范与模式

### 7.1 文件命名规范

- ks.yaml：Flux Kustomization 资源（定义清单的应用规则）

- kustomization.yaml：Kustomize 配置（定义待集成的资源清单）

- *.enc.yaml：PGP 加密的 SOPS 文件

- *.enc.age.yaml：Age 加密的 SOPS 文件

- helmfile.yaml：Helmfile 配置文件（用于初始化流程）

- helmrelease.yaml：Helm 发布定义文件

- ocirepository.yaml：OCI 仓库源配置文件

- namespace.yaml：命名空间定义文件（含 Pod 安全标签）

### 7.2 Kustomization 标签规范

- substitution.flux/enabled=true：启用 SOPS 解密与变量替换功能

- 全局补丁：所有 Kustomization 均会应用 HelmRelease 全局默认配置补丁

### 7.3 命名空间规范

所有命名空间需添加以下标准标签：

- pod-security.kubernetes.io/enforce: privileged（或 restricted/baseline，根据安全等级定义）

- goldilocks.fairwinds.com/enabled: "true"（用于资源监控）

- kustomize.toolkit.fluxcd.io/prune: disabled（仅 flux-system 命名空间使用）

### 7.4 依赖管理规范

Flux Kustomization 通过 `dependsOn` 字段定义部署依赖顺序，示例：

```yaml
dependsOn:
  - name: cert-manager
    namespace: flux-system
```

## 八、重要说明

- 默认集群ID：cluster-00（所有未指定集群的操作均默认指向此集群）

- 主分支规则：main 分支为核心分支，FluxCD 会自动同步此分支的配置至集群

- Talos 配置：加密存储于 talos/generated/ 目录，需通过 task talos:config 解密后使用

- 初始化方式：采用 Flux Operator 而非传统的 flux bootstrap 方式

- 图表源：优先使用 OCIRepository 而非传统 HelmRepository

- Yamllint 配置：行长度超过 240 字符会触发警告，统一使用 2 空格缩进

- 自动化更新：Renovate 工具启用自动合并功能（仅针对摘要更新），忽略加密文件

- 多集群支持：通过 overlay 模式实现多集群配置管理，具备多集群扩展能力

- 实践等级：采用企业级 GitOps 实现方案，可作为 CNCF 生态工具的最佳实践参考

## 九、外部依赖

- Cloudflare：提供 DNS 管理与 CDN 服务

- Google Cloud Platform（GCP）：
      GCP KMS：用于 SOPS 加密备份

- Google Cloud Storage：用于 Thanos 指标长期存储与 Velero 备份存储

- OAuth：提供身份认证服务

GitHub：提供代码托管、身份认证、Helm 图表 OCI 仓库服务

SOPS/age：提供密钥加密解密能力（需本地配置 PGP/Age 密钥）

Task：任务自动化运行工具（需本地安装）

Helmfile：用于 Flux Operator 初始化流程

Let's Encrypt：提供免费 SSL/TLS 证书生成服务

NextDNS：提供恶意软件防护与广告拦截服务

UptimeRobot：提供服务可用性监控服务

## 十、Flux MCP 故障排查

本仓库包含 Cursor 规则，可通过 `flux-operator-mcp` 工具排查 Flux 相关资源故障，核心排查流程如下：

### 10.1 HelmReleases 排查流程

1. 通过 `get_flux_instance` 命令查看 helm-controller 运行状态

2. 获取 HelmRelease 资源，分析其 spec（配置）、status（状态）、inventory（资源清单）、events（事件）

3. 检查 valuesFrom 引用的 ConfigMaps 和 Secrets 是否存在且配置正确

4. 验证 OCIRepository 源的连接状态与图表可用性

5. 分析 inventory 中管理的资源是否正常运行

6. 若资源部署失败，查看相关组件日志定位问题

### 10.2 Kustomizations 排查流程

1. 通过 `get_flux_instance` 命令查看 kustomize-controller 运行状态

2. 获取 Kustomization 资源，分析其 spec（配置）、status（状态）、inventory（资源清单）、events（事件）

3. 检查 substituteFrom 引用的 ConfigMaps 和 Secrets 是否配置正确

4. 验证 GitRepository/OCIRepository 源的连接状态与资源同步情况

5. 分析 inventory 中管理的资源是否正常运行

### 10.3 多集群资源对比排查

使用 `get_kubernetes_contexts` 命令查看所有可用的 Kubernetes 上下文，通过 `set_kubernetes_context` 命令切换集群上下文，进而对比不同集群间的资源配置与运行状态。
