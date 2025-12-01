# NextGen GitOps 效能平台

一个轻量级内部开发者平台，助力DevOps转型：从代码提交到生产灰度发布的零触达自动化。

## 核心功能（对齐照片JD）

- **自助式应用部署**：Portal UI，一键申请K8s环境（Helm + ArgoCD风格）。
- **CI/CD 全链路**：GitLab CI + Tekton Pipeline，支持金丝雀/蓝绿发布，回滚<2min。
- **效能度量**：DORA 4键指标看板（Prometheus + Grafana），识别瓶颈（如构建时间-62%）。
- **扩展点**：集成信创采集脚本（Python 90+），支持达梦/华为存储。

## 快速启动

1. `minikube start`
2. `flux bootstrap github --owner=你的用户名 --repository=nextgen-gitops-portal --branch=main --path=./clusters/my-cluster`
3. 访问 http://localhost:3000 （Grafana Portal）

## 为什么建这个？

空窗期自驱项目，基于生产经验（银行20+系统CI/CD落地）扩展开源starter，目标：让中小团队交付速度x5。

贡献欢迎！🚀

