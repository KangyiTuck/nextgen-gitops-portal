# 代码仓库规范
## 一、项目结构与模块说明

核心目录功能清晰划分，便于团队协作与维护：1. `kubernetes/`：存储GitOps清单（注：GitOps指通过Git管理基础设施与应用配置的运维模式），其中`clusters/<cluster-id>`存放环境覆盖配置（默认集群ID为`cluster-00`），`apps/`按命名空间划分服务配置，`components/`存储可复用配置包，`tenants/`定义Flux租户（注：Flux是GitOps工具，用于自动同步配置至Kubernetes集群）信息；2. `terraform/`：包含基础设施即代码（IaC）脚本，需在厂商专属子目录执行部署计划；3. `talos/`：存储Talos OS（注：专为Kubernetes设计的轻量操作系统）机器配置，加密输出文件统一置于`talos/generated`；4. `docs/`：支撑MkDocs文档站点构建（站点源码位于`.github/mkdocs`）；5. `hack/`：存放运维自动化脚本；6. `.taskfiles/`：存储通用任务定义，支撑各类工作流执行。

## 二、核心操作命令指南

标准化命令流程，保障开发与运维一致性：1. 代码校验：执行`task core:lint`通过yamllint工具校验YAML语法（配置文件为`.yamllint.yaml`），本地执行`pre-commit run --all-files`可模拟CI（持续集成）校验；2. Flux操作：`task flux:bootstrap`初始化Flux与仓库关联，密钥轮换需搭配`task flux:secrets`；变更预览用`task bootstrap:diff -- --cluster-id cluster-00`，确认无误后通过`task bootstrap:bootstrap`应用；3. 文档预览：文档编写者执行`task docs:serve`可本地预览站点效果。

## 三、编码风格与命名规则

统一规范减少协作成本，工具自动强制执行核心规则：1. YAML文件：2个空格缩进，必须添加起始分隔符`---`，文件名采用小写连字符格式（示例：`apps/networking/cloudflared/kustomization.yaml`），与Kubernetes资源名一致；2. Kustomize配置（注：Kustomize是Kubernetes的配置管理工具）：`base/`存通用默认配置，`overlays/`放集群定制配置；3. 其他：Terraform代码需用`terraform fmt`格式化，Shell脚本需通过pre-commit触发的shellcheck工具校验。

## 四、测试与提交规范

1. 前置测试：PR（拉取请求）提交前，需完成`task core:lint`、`pre-commit run --all-files`校验，通过`kubectl kustomize`命令验证Kubernetes清单渲染效果，Flux变更需附加`task bootstrap:diff`输出摘要，基础设施修改需本地执行`terraform plan`（禁止提交计划文件），Talos配置调整需经“解密（`task talos:config`）-编辑（sops工具）-重加密”流程；2. 提交规范：遵循约定式提交（格式：`feat(组件): 描述`、`fix: 描述`、`chore: 描述`），单个提交包含独立逻辑，PR需说明影响范围、关联工单及校验步骤，指定CODEOWNERS（`.github/CODEOWNERS`）审核，仅可视化面板变更需附加截图。

## 五、安全配置建议

密钥与Talos资源通过SOPS工具加密（Age密钥存储于`age.agekey`），编辑加密文件必须使用`sops kubernetes/.../*.enc.yaml`命令（保留加密头信息），严禁提交未加密敏感文件；操作Flux密钥前需通过`task core:gpg`导入签名密钥，密钥轮换需更新加密清单后执行`task flux:secrets`；确保kubeconfig指向测试集群，生产环境变更仅允许通过Flux自动同步。
