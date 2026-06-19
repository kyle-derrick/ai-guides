---
title: "案例一：从零搭建CI/CD流水线"
type: docs
weight: 1
---
## 案例一：从零搭建CI/CD流水线

本案例以一个典型的中小团队后端项目为背景，完整演示从零开始搭建一套企业级CI/CD流水线的全过程。我们将使用 GitHub Actions 作为 CI/CD 平台，Docker 作为容器化方案，Kubernetes 作为目标部署环境，ArgoCD 实现 GitOps 自动同步。整个过程覆盖代码提交到生产上线的完整链路，每个步骤都给出可直接复用的配置和代码。

> **适合谁读？** 本案例面向有一定开发经验但尚未搭建过完整CI/CD流水线的工程师。如果你已经熟悉某个环节（比如Docker或Kubernetes），可以直接跳到对应章节。全文约 12000 字，建议收藏后分段阅读。

---

### 1. 项目背景与目标

#### 1.1 业务场景

某互联网公司有一个订单微服务（Order Service），技术栈为：

| 维度 | 选型 |
|------|------|
| 语言 | Python 3.12 + FastAPI |
| 数据库 | PostgreSQL 16 |
| 缓存 | Redis 7 |
| 容器化 | Docker + Docker Compose |
| 编排 | Kubernetes 1.29 |
| 代码托管 | GitHub |
| CI/CD | GitHub Actions |
| GitOps | ArgoCD |

团队规模 8 人，采用功能分支工作流（Feature Branch Workflow），每个功能分支通过 Pull Request 合入 main 分支。

#### 1.2 当前痛点

在搭建CI/CD流水线之前，团队面临以下问题：

1. **手动部署**：每次上线需要开发者手动登录服务器，拉取代码，安装依赖，重启服务。一次部署耗时 20-30 分钟，且容易出错（漏装依赖、错误的环境变量、错误的目录等）。
2. **缺乏测试自动化**：代码合并前仅靠人工 Review，没有自动化的测试门禁，线上 Bug 率高。平均每 3 次发布就有 1 次需要紧急修复。
3. **环境不一致**：开发、测试、生产环境的依赖版本不统一，"在我机器上可以运行"是常态。数据库驱动版本、系统库版本、Python 版本都可能不一致。
4. **无回滚机制**：出现问题后只能紧急修复并重新部署，没有快速回滚能力。一次回滚平均需要 30 分钟以上。
5. **部署不可追溯**：无法快速确认生产环境运行的是哪个版本的代码，出了问题难以定位。没有部署记录，没有发布日志。

#### 1.3 改造目标

构建一条覆盖以下阶段的自动化流水线：

代码提交 → 静态检查 → 单元测试 → 集成测试 → 安全扫描 → 构建镜像 → 推送仓库 → 部署到K8s → 健康检查

核心指标要求：

| 指标 | 目标值 | 衡量方式 |
|------|--------|----------|
| 流水线总耗时 | < 15 分钟 | 从代码推送到生产部署完成 |
| 测试覆盖率 | > 80% | coverage.py 度量 |
| 部署成功率 | > 99% | 部署后健康检查通过率 |
| 回滚时间 | < 2 分钟 | 从决策到回滚完成 |

---

### 2. 项目结构设计

#### 2.1 仓库结构

一个良好的CI/CD实践要求将应用代码、基础设施代码和流水线配置分层管理。以下是推荐的仓库结构：

order-service/
├── app/                          # 应用代码
│   ├── main.py
│   ├── models.py
│   ├── routes/
│   └── services/
├── tests/
│   ├── unit/                     # 单元测试
│   ├── integration/              # 集成测试
│   └── conftest.py
├── deploy/
│   ├── k8s/                      # Kubernetes 清单
│   │   ├── base/
│   │   │   ├── kustomization.yaml
│   │   │   ├── deployment.yaml
│   │   │   ├── service.yaml
│   │   │   ├── hpa.yaml
│   │   │   └── serviceaccount.yaml
│   │   └── overlays/
│   │       ├── staging/
│   │       │   └── kustomization.yaml
│   │       └── production/
│   │           ├── kustomization.yaml
│   │           ├── pdb.yaml
│   │           ├── replica-patch.yaml
│   │           └── resource-patch.yaml
│   └── argocd/
│       ├── app-staging.yaml
│       └── app-production.yaml
├── .github/
│   └── workflows/
│       ├── ci.yaml               # CI 流水线
│       ├── cd-staging.yaml       # Staging 部署
│       └── cd-production.yaml    # Production 部署
├── .pre-commit-config.yaml       # 本地提交钩子
├── Dockerfile                    # 多阶段构建
├── docker-compose.yml            # 本地开发环境
├── pyproject.toml                # 项目配置与工具配置
├── requirements.txt              # 运行时依赖
├── requirements-dev.txt          # 开发/测试依赖
├── Makefile                      # 常用命令快捷入口
└── README.md

**为什么这样组织？** 将 `deploy/` 和 `.github/workflows/` 放在应用仓库中（而非独立仓库），对于中小团队来说是更务实的选择——代码变更和部署配置变更可以在同一个 PR 中一起 Review，降低两者不一致的风险。当团队规模超过 30 人或有专门的平台工程团队时，再考虑将基础设施代码拆分到独立仓库。

#### 2.2 项目配置文件

**pyproject.toml — 统一配置**

将 Ruff、mypy、Bandit、pytest 等工具的配置统一放在 `pyproject.toml` 中，避免多个配置文件散落：

```toml
# pyproject.toml
[project]
name = "order-service"
version = "1.0.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "sqlalchemy[asyncio]>=2.0.36",
    "asyncpg>=0.30.0",
    "redis[hiredis]>=5.2.0",
    "pydantic>=2.10.0",
    "alembic>=1.14.0",
    "httpx>=0.28.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "pytest-cov>=6.0.0",
    "httpx>=0.28.0",
    "ruff>=0.8.0",
    "mypy>=1.13.0",
    "bandit>=1.8.0",
    "pre-commit>=4.0.0",
]

# Ruff 配置（替代 flake8 + isort + black）
[tool.ruff]
target-version = "py312"
line-length = 88
src = ["app", "tests"]

[tool.ruff.lint]
select = [
    "E",    # pycodestyle errors
    "W",    # pycodestyle warnings
    "F",    # pyflakes
    "I",    # isort
    "N",    # pep8-naming
    "UP",   # pyupgrade
    "B",    # flake8-bugbear
    "S",    # flake8-bandit
    "A",    # flake8-builtins
    "C4",   # flake8-comprehensions
    "SIM",  # flake8-simplify
]
ignore = ["S101"]  # 允许 assert 在测试中使用

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["S101", "S106"]  # 测试文件放宽限制

# mypy 配置
[tool.mypy]
python_version = "3.12"
strict = false
warn_return_any = true
warn_unused_configs = true
ignore_missing_imports = true

# Bandit 配置
[tool.bandit]
exclude_dirs = ["tests"]
skips = ["B101"]  # 允许 assert 在非测试代码中使用

# pytest 配置
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
markers = [
    "slow: 标记为慢速测试",
    "flaky: 标记为不稳定测试",
]
addopts = "--strict-markers -v"

# coverage 配置
[tool.coverage.run]
source = ["app"]
omit = ["app/main.py"]  # 排除启动入口

[tool.coverage.report]
fail_under = 80
show_missing = true
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "if __name__ == .__main__.",
]
```

**requirements.txt 与 requirements-dev.txt — 依赖分层**

```txt
# requirements.txt（运行时依赖，带版本锁定）
fastapi==0.115.6
uvicorn[standard]==0.32.1
sqlalchemy[asyncio]==2.0.36
asyncpg==0.30.0
redis[hiredis]==5.2.1
pydantic==2.10.3
alembic==1.14.1
httpx==0.28.1
```

```txt
# requirements-dev.txt（开发/测试依赖）
-r requirements.txt
pytest==8.3.4
pytest-asyncio==0.24.0
pytest-cov==6.0.0
ruff==0.8.6
mypy==1.13.0
bandit[toml]==1.8.2
pre-commit==4.0.1
```

#### 2.3 本地开发环境

使用 Docker Compose 在本地启动所有依赖服务，确保开发者无需手动安装 PostgreSQL 和 Redis：

```yaml
# docker-compose.yml
services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://dev:dev@db:5432/order_dev
      - REDIS_URL=redis://redis:6379/0
    volumes:
      - ./app:/app/app  # 热重载：挂载代码目录
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy

  db:
    image: postgres:16
    environment:
      POSTGRES_DB: order_dev
      POSTGRES_USER: dev
      POSTGRES_PASSWORD: dev
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./deploy/init.sql:/docker-entrypoint-initdb.d/init.sql  # 初始化脚本
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U dev -d order_dev"]
      interval: 5s
      timeout: 3s
      retries: 5

  redis:
    image: redis:7
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

volumes:
  pgdata:
```

#### 2.4 Makefile 快捷命令

将常用开发命令封装到 Makefile，降低新人上手门槛：

```makefile
# Makefile
.PHONY: help dev test lint format typecheck security clean

help:  ## 显示帮助信息
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

dev:  ## 启动本地开发环境
	docker compose up -d
	@echo "✅ 开发环境已启动: http://localhost:8000"
	@echo "📊 PostgreSQL: localhost:5432"
	@echo "🔴 Redis: localhost:6379"

test:  ## 运行全部测试
	pytest tests/ -v --cov=app --cov-report=term-missing

test-unit:  ## 仅运行单元测试
	pytest tests/unit/ -v

test-integration:  ## 仅运行集成测试（需要启动 Docker）
	pytest tests/integration/ -v

lint:  ## 代码质量检查
	ruff check app/ tests/
	ruff format --check app/ tests/

format:  ## 自动格式化代码
	ruff check --fix app/ tests/
	ruff format app/ tests/

typecheck:  ## 类型检查
	mypy app/ --ignore-missing-imports

security:  ## 安全扫描
	bandit -c pyproject.toml -r app/
	pip-audit --require-hashes -r requirements.txt

clean:  ## 清理构建产物
	rm -rf __pycache__ .pytest_cache htmlcov coverage.xml .mypy_cache
	docker compose down -v
```

#### 2.5 分支策略

采用 GitHub Flow 作为分支策略，配合环境保护规则（Environment Protection Rules）实现人工审批门禁：

| 分支 | 用途 | 触发动作 |
|------|------|----------|
| `feature/*` | 功能开发分支 | 创建 PR，触发 CI |
| `main` | 主干分支 | 合并后触发 CI + 部署到 Staging |
| `release/*` | 发布分支 | 手动触发部署到 Production |

分支保护规则（Branch Protection Rules）配置步骤：

1. 进入 GitHub 仓库 → Settings → Branches → Add branch protection rule
2. Branch name pattern: `main`
3. 勾选以下选项：
   - ✅ Require a pull request before merging（至少 1 个 Review Approval）
   - ✅ Require status checks to pass before merging（选择 CI workflow 的关键 Job）
   - ✅ Require branches to be up to date before merging
   - ❌ Do not allow bypassing the above settings（管理员也不能绕过）
   - ❌ Do not allow force pushes
   - ❌ Do not allow deletions

---

### 3. 第一步：静态检查与代码质量

静态检查是流水线的第一道防线，在代码进入测试阶段之前就拦截明显的问题。根据 Google 的工程实践，静态检查的成本是运行时 Bug 修复成本的 1/10 到 1/100。

#### 3.1 工具选型

| 工具 | 用途 | 特点 | 替代方案 |
|------|------|------|----------|
| Ruff | Python Lint + Format | 替代 flake8/isort/pyblack，速度快 10-100 倍，Rust 编写 | flake8 + isort + black |
| mypy | 静态类型检查 | 捕获类型错误，渐进式类型系统 | pyright, pytype |
| Bandit | 安全漏洞扫描 | 检测常见安全问题（硬编码密码、SQL注入风险等） | Semgrep, CodeQL |
| pre-commit | 本地钩子 | 在 git commit 前自动运行检查，避免无效推送 | husky (JS生态) |

#### 3.2 pre-commit 配置

在本地开发环境中，通过 pre-commit 在提交前自动运行检查，避免将明显问题推送到远程。安装方式：

```bash
pip install pre-commit
pre-commit install          # 安装 git hook
pre-commit install --hook-type commit-msg  # 安装 commit message 检查
```

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.8.6
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.13.0
    hooks:
      - id: mypy
        additional_dependencies: [types-requests, types-redis]
        args: [--ignore-missing-imports]

  - repo: https://github.com/PyCQA/bandit
    rev: 1.8.2
    hooks:
      - id: bandit
        args: ["-c", "pyproject.toml"]
        additional_dependencies: ["bandit[toml]"]

  # 防止提交大文件和敏感信息
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: detect-private-key
      - id: detect-aws-credentials
      - id: check-added-large-files
        args: ['--maxkb=1024']
      - id: check-merge-conflict
      - id: trailing-whitespace
      - id: end-of-file-fixer
```

**pre-commit 的工作原理**：每次执行 `git commit` 时，pre-commit 会自动运行上述钩子。如果任何钩子发现问题并自动修复了代码（比如格式化），它会中止本次提交并将修复后的文件加入暂存区。你需要重新 `git add` 再次提交。这确保了每次成功提交的代码都是通过检查的。

#### 3.3 CI 中的静态检查 Job

```yaml
# .github/workflows/ci.yaml（片段 — 完整文件见第 9 节）
jobs:
  lint:
    name: Code Quality
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'

      - name: Install dependencies
        run: pip install ruff mypy bandit[toml] types-requests

      - name: Ruff Lint
        run: ruff check app/ tests/ --output-format=github

      - name: Ruff Format Check
        run: ruff format --check app/ tests/

      - name: Type Check
        run: mypy app/ --ignore-missing-imports --no-error-summary

      - name: Security Scan (Bandit)
        run: bandit -c pyproject.toml -r app/ -ll  # -ll 只报告 HIGH 及以上
```

**关键设计决策**：
- `--output-format=github` 让 Ruff 的检查结果直接在 PR 的 Files Changed 面板中显示为行内注释，开发者无需展开日志就能看到问题。
- `-ll` 让 Bandit 只报告 HIGH 及以上严重级别的问题，避免大量 LOW 级别的告警淹没真正的风险。
- 静态检查 Job 不依赖任何其他 Job，作为流水线的最前端，通常在 30 秒内完成。如果检查失败，后续的测试和构建不会启动，节省计算资源。

---

### 4. 第二步：测试策略与执行

测试是CI/CD流水线的核心质量门禁。采用测试金字塔策略：大量快速的单元测试、适量的集成测试、少量关键的端到端测试。

```mermaid
graph TB
    subgraph 金字塔
        E2E["🔺 端到端测试<br/>少量 · 慢 · 高置信度"]
        INT["🔷 集成测试<br/>适量 · 中速 · 组件交互"]
        UNIT["🟩 单元测试<br/>大量 · 极快 · 逻辑正确性"]
    end
    style E2E fill:#ff6b6b,color:#fff
    style INT fill:#4ecdc4,color:#fff
    style UNIT fill:#51cf66,color:#fff
```

#### 4.1 单元测试

单元测试覆盖单个函数或类的逻辑，不依赖外部服务，运行速度极快。使用 pytest 作为测试框架，coverage.py 度量覆盖率。

```python
# tests/unit/test_order_service.py
import pytest
from unittest.mock import AsyncMock, patch
from app.services.order_service import OrderService
from app.models import Order, OrderStatus
from app.exceptions import InsufficientStockError, OrderCannotBeCancelledError


class TestOrderService:
    """订单服务单元测试"""

    @pytest.fixture
    def mock_db(self):
        """模拟数据库会话"""
        return AsyncMock()

    @pytest.fixture
    def mock_cache(self):
        """模拟Redis缓存"""
        cache = AsyncMock()
        cache.get.return_value = None
        return cache

    @pytest.fixture
    def service(self, mock_db, mock_cache):
        return OrderService(db=mock_db, cache=mock_cache)

    async def test_create_order_success(self, service, mock_db):
        """测试创建订单成功场景"""
        order_data = {
            "user_id": 1001,
            "items": [{"product_id": "P001", "quantity": 2}],
            "total_amount": 99.80,
        }
        order = await service.create_order(order_data)

        assert order.status == OrderStatus.PENDING
        assert order.total_amount == 99.80
        assert order.user_id == 1001
        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()

    async def test_create_order_insufficient_stock(self, service):
        """测试库存不足时应抛出异常"""
        order_data = {
            "user_id": 1001,
            "items": [{"product_id": "P001", "quantity": 9999}],
            "total_amount": 0,
        }
        with pytest.raises(InsufficientStockError) as exc_info:
            await service.create_order(order_data)
        assert "库存不足" in str(exc_info.value)

    async def test_cancel_order_before_payment(self, service, mock_db):
        """测试支付前取消订单"""
        order = Order(status=OrderStatus.PENDING)
        result = await service.cancel_order(order)
        assert result.status == OrderStatus.CANCELLED
        mock_db.flush.assert_called_once()

    async def test_cancel_order_after_payment_fails(self, service):
        """测试支付后不允许直接取消（需退款流程）"""
        order = Order(status=OrderStatus.PAID)
        with pytest.raises(OrderCannotBeCancelledError) as exc_info:
            await service.cancel_order(order)
        assert "已支付" in str(exc_info.value)
```

**单元测试编写要点**：
- **每个测试只验证一个行为**：方法名清楚表达意图（`test_create_order_insufficient_stock` 而非 `test_create_order`）。
- **使用 Fixture 管理依赖**：pytest 的 Fixture 机制让测试间共享 mock 对象，避免重复代码。
- **验证行为而非实现**：检查 `order.status == OrderStatus.PENDING` 而非检查内部方法调用顺序。
- **异常测试包含断言消息**：`assert "库存不足" in str(exc_info.value)` 确保抛出的是正确的异常类型。

#### 4.2 集成测试

集成测试验证多个组件之间的交互是否正确，需要真实的外部服务。使用 GitHub Actions 的 `services` 功能在 CI 环境中启动依赖服务容器。

```yaml
# .github/workflows/ci.yaml（集成测试片段）
  integration-tests:
    name: Integration Tests
    runs-on: ubuntu-latest
    timeout-minutes: 15
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_DB: order_test
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      redis:
        image: redis:7
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt

      - name: Run database migrations
        run: alembic upgrade head
        env:
          DATABASE_URL: postgresql+asyncpg://test:test@localhost:5432/order_test

      - name: Run integration tests
        run: pytest tests/integration -v --tb=short
        env:
          DATABASE_URL: postgresql+asyncpg://test:test@localhost:5432/order_test
          REDIS_URL: redis://localhost:6379/0

      - name: Generate coverage report
        if: always()
        run: |
          coverage run -m pytest tests/integration -v
          coverage report --fail-under=80
          coverage html -d htmlcov-integration

      - name: Upload integration test coverage
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: integration-coverage
          path: htmlcov-integration/
```

**GitHub Actions Services 工作原理**：`services` 中定义的容器会在 Job 开始前启动，并在整个 Job 运行期间保持可用。它们通过 Docker 网络与 Runner 上的步骤通信，端口映射到 `localhost`。health check 确保服务就绪后才开始执行后续步骤。

#### 4.3 单元测试 Job

```yaml
  unit-tests:
    name: Unit Tests
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt

      - name: Run unit tests with coverage
        run: |
          pytest tests/unit/ \
            -v \
            --cov=app \
            --cov-report=term-missing \
            --cov-report=xml:coverage.xml \
            --junitxml=test-results.xml

      - name: Check coverage threshold
        run: coverage report --fail-under=80

      - name: Upload coverage to Codecov
        if: always()
        uses: codecov/codecov-action@v4
        with:
          file: coverage.xml
          fail_ci_if_error: false
          flags: unit-tests

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: test-results
          path: test-results.xml
```

#### 4.4 覆盖率门禁

通过覆盖率门禁确保代码质量不会随时间退化：

**覆盖率阈值选择的依据**：

| 阈值范围 | 含义 | 适用场景 |
|----------|------|----------|
| < 60% | 测试严重不足，大量逻辑未覆盖 | 需要立即补充测试 |
| 60-80% | 基本覆盖，但存在盲区 | 逐步提升 |
| 80-90% | 良好覆盖，多数关键路径已测试 | 大多数项目的推荐目标 |
| > 90% | 极高覆盖，可能有低价值测试 | 安全关键系统（金融、医疗） |

覆盖率是质量的**必要非充分条件**——有高覆盖率不等于代码没有 Bug，但低覆盖率几乎一定意味着质量风险。80% 是一个务实的阈值：低于 80% 说明测试严重不足，高于 90% 则可能导致团队为了凑覆盖率而编写低价值测试。

---

### 5. 第三步：安全扫描

DevSecOps 理念要求将安全检查左移到CI阶段。在流水线中集成三层安全扫描，各自覆盖不同的攻击面：

```mermaid
graph LR
    A[代码安全] --> B[依赖漏洞扫描<br/>SCA]
    A --> C[密钥泄露检测<br/>Secrets]
    B --> D[完整安全防线]
    C --> D
    E[运行时安全] --> F[容器镜像扫描<br/>SAST/Container]
    F --> D
    style D fill:#51cf66,color:#fff
```

#### 5.1 依赖漏洞扫描（SCA）

使用 pip-audit 检查 Python 依赖中的已知漏洞（替代已弃用的 Safety）：

```yaml
  security:
    name: Security Scan
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: pip install pip-audit bandit[toml]

      - name: Check dependency vulnerabilities (pip-audit)
        run: pip-audit -r requirements.txt --strict

      - name: Run Bandit security scan (code-level)
        run: |
          bandit -r app/ -f json -o bandit-report.json || true
          # 只有 HIGH 和 MEDIUM 级别的问题才会阻断流水线
          bandit -r app/ -ll  # -ll 表示只报告 HIGH 及以上
```

**pip-audit 工作原理**：它将项目依赖与 OSV（Open Source Vulnerabilities）数据库进行交叉比对，识别已知漏洞。`--strict` 模式下，即使依赖数据库更新失败也会返回非零退出码，防止静默跳过扫描。

#### 5.2 容器镜像扫描

在构建 Docker 镜像后，使用 Trivy 扫描镜像中的操作系统和应用层漏洞：

```yaml
      - name: Build Docker image for scanning
        run: docker build -t order-service:scan .

      - name: Run Trivy vulnerability scanner
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: 'order-service:scan'
          format: 'sarif'
          output: 'trivy-results.sarif'
          severity: 'CRITICAL,HIGH'
          exit-code: '1'  # 发现 CRITICAL/HIGH 漏洞时失败

      - name: Upload Trivy scan results to GitHub Security tab
        uses: github/codeql-action/upload-sarif@v3
        if: always()
        with:
          sarif_file: 'trivy-results.sarif'
```

**Trivy 扫描结果会自动出现在 GitHub 仓库的 Security → Code scanning alerts 中**，与 GitHub 的安全告警体系无缝集成。团队可以在统一界面查看代码漏洞、依赖漏洞和容器漏洞。

#### 5.3 密钥泄露检测

使用 Gitleaks 扫描代码中是否意外提交了敏感信息：

```yaml
      - name: Run Gitleaks
        uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

**为什么三层扫描缺一不可**：

| 扫描层 | 覆盖攻击面 | 典型发现 |
|--------|-----------|----------|
| 依赖漏洞扫描 (SCA) | 第三方库的风险 | OpenSSL CVE-2024-XXXX、SQLAlchemy 注入 |
| 容器镜像扫描 | 操作系统层和系统库的风险 | Alpine Linux CVE、glibc 漏洞 |
| 密钥泄露检测 | 人为失误的风险 | 硬编码的 AWS Key、数据库密码 |

三者各自覆盖不同的攻击面，组合起来才能构建完整的安全防线。缺少任何一层都会留下盲区。

---

### 6. 第四步：构建与推送镜像

#### 6.1 Dockerfile 最佳实践

一个高效的 Dockerfile 应该利用多阶段构建（Multi-stage Build）和层缓存来最小化构建时间和镜像体积：

```dockerfile
# ---- 构建阶段 ----
FROM python:3.12-slim AS builder

WORKDIR /build

# 利用缓存：先安装依赖，再复制代码
# requirements.txt 变化频率远低于 app/ 代码
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- 运行阶段 ----
FROM python:3.12-slim AS runtime

# 安全最佳实践：使用非root用户
# 如果以 root 运行，容器逃逸后攻击者直接获得宿主机 root 权限
RUN groupadd -r appuser &amp;&amp; useradd -r -g appuser -d /app -s /sbin/nologin appuser

WORKDIR /app

# 只复制安装好的依赖（builder 阶段的产物）
COPY --from=builder /install /usr/local

# 复制应用代码
COPY app/ ./app/

# 设置运行用户
USER appuser

# 健康检查：Kubernetes liveness probe 依赖此指令判断容器是否健康
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

**设计要点**：
- **多阶段构建**：builder 阶段安装依赖（可能需要编译工具），runtime 阶段只包含运行时需要的内容。最终镜像体积减少 40-60%。
- **非root用户**：安全最佳实践，防止容器逃逸后获得宿主机 root 权限。`/sbin/nologin` 确保该用户无法交互式登录。
- **层缓存优化**：先 `COPY requirements.txt` 再 `COPY app/`。代码变更不会使依赖安装缓存失效，这是 Docker 构建加速的关键技巧。
- **HEALTHCHECK**：虽然 Kubernetes 使用自己的探针机制，但 `HEALTHCHECK` 指令对非 K8s 环境（如本地 Docker Compose）仍然有用。

#### 6.2 构建与推送流程

```yaml
  build-and-push:
    name: Build &amp; Push Image
    runs-on: ubuntu-latest
    timeout-minutes: 10
    needs: [lint, unit-tests, integration-tests, security]
    outputs:
      image_tag: ${{ steps.meta.outputs.version }}
      image_digest: ${{ steps.build.outputs.digest }}
    permissions:
      contents: read
      packages: write  # 需要写权限推送到 GHCR
    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Login to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata (tags, labels)
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ghcr.io/${{ github.repository }}
          tags: |
            # 基于 Git SHA 的精确标签（每次构建唯一）
            type=sha,prefix=,format=short
            # 语义化版本（基于 Git Tag）
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}
            # main 分支打 latest 标签
            type=raw,value=latest,enable={{is_default_branch}}

      - name: Build and push Docker image
        id: build
        uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
          platforms: linux/amd64

      - name: Generate SBOM (Software Bill of Materials)
        uses: anchore/sbom-action@v0
        with:
          image: ghcr.io/${{ github.repository }}:${{ steps.meta.outputs.version }}
          format: spdx-json
          output-file: sbom.spdx.json

      - name: Upload SBOM as artifact
        uses: actions/upload-artifact@v4
        with:
          name: sbom
          path: sbom.spdx.json
          retention-days: 90
```

**不可变制品原则的体现**：镜像一旦推送成功就不再修改。Staging 和 Production 部署使用完全相同的镜像标签，通过 Kustomize overlay 切换环境配置（副本数、资源限制、环境变量等）。如果镜像需要修改，必须通过新的代码变更触发新的构建。

#### 6.3 镜像标签策略

合理的标签策略让团队在追溯和回滚时事半功倍：

| 标签类型 | 示例 | 用途 | 生成方式 |
|----------|------|------|----------|
| Git SHA 短标签 | `a1b2c3d` | 精确追溯到某次提交 | `type=sha,format=short` |
| 语义化版本 | `1.2.3` | 正式发布版本 | `type=semver,pattern={{version}}` |
| 分支标签 | `latest` | 指向默认分支最新构建 | `type=raw,value=latest` |

**推荐实践**：日常使用 Git SHA 标签部署（每个提交都有唯一标签），正式发布时打 Git Tag 触发 semver 标签生成。

#### 6.4 构建缓存策略

GitHub Actions 的 Actions Cache（`type=gha`）利用 GitHub 的缓存基础设施加速 Docker 构建：

| 缓存层 | 缓存内容 | 命中率 | 加速效果 |
|--------|----------|--------|----------|
| Docker 层缓存 | pip install 安装结果 | 高（依赖未变时） | 30s → 3s |
| BuildKit 缓存 | 中间构建产物 | 中 | 构建时间减少 50% |
| GitHub Actions Cache | 跨 workflow 的缓存共享 | 高 | 首次构建也受益 |

**`mode=max` 的含义**：默认模式只缓存最终镜像用到的层，`max` 模式缓存所有中间层（包括构建阶段的层），对多阶段构建特别有效。

---

### 7. 第五步：部署到 Kubernetes

#### 7.1 Kubernetes 清单设计

使用 Kustomize 管理多环境配置，避免硬编码和复制粘贴。Kustomize 是 Kubernetes 官方推荐的配置管理工具，无需模板语言（相比 Helm 更简单）。

```yaml
# deploy/k8s/base/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-service
  labels:
    app: order-service
spec:
  replicas: 2
  selector:
    matchLabels:
      app: order-service
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1        # 滚动更新时最多多出 1 个 Pod
      maxUnavailable: 0  # 更新期间不允许减少可用 Pod 数
  template:
    metadata:
      labels:
        app: order-service
    spec:
      serviceAccountName: order-service
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
      containers:
        - name: order-service
          image: ghcr.io/org/order-service
          ports:
            - containerPort: 8000
              protocol: TCP
          envFrom:
            - configMapRef:
                name: order-service-config
            - secretRef:
                name: order-service-secrets
          resources:
            requests:
              cpu: 200m
              memory: 256Mi
            limits:
              cpu: 1000m
              memory: 512Mi
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 30
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /ready
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 10
            failureThreshold: 3
```

**探针设计的考量**：
- **livenessProbe**：检测容器是否还活着。如果连续 3 次失败（每次间隔 30s），Kubernetes 会杀掉容器并重启。`initialDelaySeconds: 10` 给应用 10 秒的启动时间。
- **readinessProbe**：检测容器是否准备好接收流量。只有 readinessProbe 通过的 Pod 才会出现在 Service 的 Endpoints 中。这避免了新 Pod 还没初始化完成就被分配请求。
- **`maxUnavailable: 0`**：确保滚动更新期间不会出现服务降级（可用 Pod 数始终不低于期望值）。

```yaml
# deploy/k8s/base/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: order-service
  labels:
    app: order-service
spec:
  type: ClusterIP
  ports:
    - port: 80
      targetPort: 8000
      protocol: TCP
      name: http
  selector:
    app: order-service
```

```yaml
# deploy/k8s/base/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: order-service
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: order-service
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
        - type: Pods
          value: 2
          periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Percent
          value: 10
          periodSeconds: 60
```

**HPA（Horizontal Pod Autoscaler）配置要点**：
- **scaleDown 更保守**：扩容快（每 60s 最多加 2 个 Pod），缩容慢（每 60s 最多减少 10% 的 Pod，且需稳定 5 分钟）。这避免了因瞬时流量波动导致的频繁扩缩容（thrashing）。
- **CPU 70% + Memory 80%**：CPU 更敏感（70% 触发扩容），内存阈值略高（80%），因为内存扩容通常意味着应用有内存泄漏问题，需要人工介入。

```yaml
# deploy/k8s/base/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - deployment.yaml
  - service.yaml
  - hpa.yaml
  - serviceaccount.yaml
commonLabels:
  app.kubernetes.io/managed-by: kustomize
```

```yaml
# deploy/k8s/base/serviceaccount.yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: order-service
  labels:
    app: order-service
```

#### 7.2 多环境 Overlay

```yaml
# deploy/k8s/overlays/production/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: production
namePrefix: prod-
resources:
  - ../../base
  - pdb.yaml
patches:
  - path: replica-patch.yaml
  - path: resource-patch.yaml
```

```yaml
# deploy/k8s/overlays/production/replica-patch.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-service
spec:
  replicas: 4
```

```yaml
# deploy/k8s/overlays/production/resource-patch.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-service
spec:
  template:
    spec:
      containers:
        - name: order-service
          resources:
            requests:
              cpu: 500m
              memory: 512Mi
            limits:
              cpu: 2000m
              memory: 1Gi
```

```yaml
# deploy/k8s/overlays/production/pdb.yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: order-service
spec:
  minAvailable: 1  # 至少保持 1 个 Pod 可用
  selector:
    matchLabels:
      app: order-service
```

**PodDisruptionBudget（PDB）的作用**：防止在节点维护（如 Kubernetes 升级、节点缩容）时同时驱逐所有 Pod。`minAvailable: 1` 确保至少有 1 个 Pod 在服务。

```yaml
# deploy/k8s/overlays/staging/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: staging
namePrefix: staging-
resources:
  - ../../base
patches:
  - path: replica-patch.yaml
```

```yaml
# deploy/k8s/overlays/staging/replica-patch.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-service
spec:
  replicas: 1  # Staging 只需 1 个副本节省资源
```

**Kustomize 的工作原理**：base 目录包含通用配置，overlays 目录通过 patch 文件覆盖特定环境的差异配置。`kustomize build overlays/production` 会合并 base + overlay，输出完整的 Kubernetes 清单。这比 Helm 模板更简单直观，且输出是纯 YAML，易于调试。

#### 7.3 ArgoCD Application 定义

```yaml
# deploy/argocd/app-production.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: order-service-production
  namespace: argocd
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  project: default
  source:
    repoURL: https://github.com/org/order-service.git
    targetRevision: main
    path: deploy/k8s/overlays/production
  destination:
    server: https://kubernetes.default.svc
    namespace: production
  syncPolicy:
    automated:
      prune: true        # 删除 Git 中已移除的资源
      selfHeal: true     # 自动修复手动修改（配置漂移检测）
    syncOptions:
      - CreateNamespace=true
    retry:
      limit: 3
      backoff:
        duration: 5s
        factor: 2
        maxDuration: 1m
  healthChecks:
    - apiVersion: apps/v1
      kind: Deployment
      name: order-service
      namespace: production
```

**ArgoCD 安装（快速启动）**：

```bash
# 1. 安装 ArgoCD
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# 2. 获取初始管理员密码
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d

# 3. 安装 ArgoCD CLI
curl -sSL -o argocd https://github.com/argoproj/argo-cd/releases/latest/download/argocd-linux-amd64
chmod +x argocd &amp;&amp; sudo mv argocd /usr/local/bin/

# 4. 登录
argocd login localhost:8080 --username admin --password <密码>
```

**ArgoCD 的核心机制**：
- **prune: true**：如果 Git 中删除了某个资源定义，ArgoCD 会自动从集群中删除对应的资源。
- **selfHeal: true**：如果有人手动用 `kubectl` 修改了集群中的资源（配置漂移），ArgoCD 会在 3 分钟内自动修复回 Git 中定义的状态。
- **retry**：同步失败时自动重试，最多 3 次，指数退避。

#### 7.4 CD 流水线：Staging 部署

```yaml
# .github/workflows/cd-staging.yaml
name: Deploy to Staging
on:
  push:
    branches: [main]

# 防止并发部署同一环境
concurrency:
  group: deploy-staging
  cancel-in-progress: false  # 不取消正在进行的部署，而是排队

jobs:
  deploy-staging:
    name: Deploy to Staging
    runs-on: ubuntu-latest
    timeout-minutes: 10
    environment:
      name: staging
      url: https://staging.order.example.com
    steps:
      - uses: actions/checkout@v4
        with:
          token: ${{ secrets.DEPLOY_TOKEN }}  # 需要有 push 权限的 Token

      - name: Update Kustomize image tag
        run: |
          cd deploy/k8s/overlays/staging
          kustomize edit set image \
            ghcr.io/${{ github.repository }}=ghcr.io/${{ github.repository }}:${{ github.sha }}

      - name: Commit and push updated manifests
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add deploy/
          git diff --cached --quiet || git commit -m "chore: update staging image to ${{ github.sha }}"
          git push
```

**GitOps 的核心机制**：CD 流水线不直接操作 Kubernetes 集群，而是更新 Git 仓库中的镜像标签。ArgoCD 检测到 Git 变更后自动拉取并应用到集群。这种方式保证了：
1. **所有变更都有 Git 历史记录**：谁在什么时候改了什么，一目了然。
2. **Kubernetes 集群的凭证不需要暴露给 CI 系统**：CI 只需要 push 到 Git，ArgoCD 在集群内部运行，天然拥有集群权限。
3. **审计合规**：生产环境的每一次变更都有对应的 Git commit 和 PR。

**关于 DEPLOY_TOKEN**：默认的 `GITHUB_TOKEN` 没有 push 权限（只能读）。需要在 GitHub Settings → Developer settings → Personal access tokens 创建一个有 `repo` 权限的 Token，存入 Secrets。

#### 7.5 CD 流水线：Production 部署

```yaml
# .github/workflows/cd-production.yaml
name: Deploy to Production
on:
  workflow_dispatch:
    inputs:
      image_tag:
        description: 'Image tag to deploy (e.g., a1b2c3d or v1.2.3)'
        required: true
      skip_smoke_test:
        description: 'Skip smoke test after deployment'
        required: false
        default: 'false'
        type: boolean

# 限制并发，防止同时部署生产
concurrency:
  group: deploy-production
  cancel-in-progress: false

jobs:
  deploy-production:
    name: Deploy to Production
    runs-on: ubuntu-latest
    timeout-minutes: 15
    environment:
      name: production  # 需要手动审批（Environment Protection Rules）
      url: https://order.example.com
    steps:
      - uses: actions/checkout@v4
        with:
          token: ${{ secrets.DEPLOY_TOKEN }}

      - name: Verify image exists in registry
        run: |
          # 确认镜像确实存在于仓库中，防止因镜像标签错误导致部署失败
          docker manifest inspect ghcr.io/${{ github.repository }}:${{ inputs.image_tag }} \
            || { echo "❌ Image not found! Aborting deployment."; exit 1; }
          echo "✅ Image verified: ${{ inputs.image_tag }}"

      - name: Update Kustomize image tag
        run: |
          cd deploy/k8s/overlays/production
          kustomize edit set image \
            ghcr.io/${{ github.repository }}=ghcr.io/${{ github.repository }}:${{ inputs.image_tag }}

      - name: Commit and push
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add deploy/
          git commit -m "release: deploy ${{ inputs.image_tag }} to production"
          git push

      - name: Wait for ArgoCD sync
        run: |
          # 使用 kubectl 等待 ArgoCD 完成同步
          for i in $(seq 1 60); do
            STATUS=$(kubectl get app order-service-production -n argocd \
              -o jsonpath='{.status.sync.status}' 2>/dev/null || echo "Unknown")
            if [ "$STATUS" = "Synced" ]; then
              echo "✅ ArgoCD sync completed"
              exit 0
            fi
            echo "Waiting for sync... ($i/60) - Current status: $STATUS"
            sleep 10
          done
          echo "❌ Sync timeout after 10 minutes"
          exit 1

      - name: Verify rollout status
        run: |
          kubectl rollout status deployment/order-service \
            -n production --timeout=300s

      - name: Smoke test
        if: ${{ inputs.skip_smoke_test == 'false' }}
        run: |
          # 等待 Pod 就绪后运行烟雾测试
          sleep 30
          HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
            https://order.example.com/health)
          if [ "$HTTP_CODE" != "200" ]; then
            echo "❌ Smoke test failed: HTTP $HTTP_CODE"
            echo "🚨 Initiating auto-rollback..."
            kubectl rollout undo deployment/order-service -n production
            exit 1
          fi
          echo "✅ Smoke test passed: HTTP $HTTP_CODE"

      - name: Notify deployment result
        if: always()
        run: |
          STATUS="${{ job.status }}"
          if [ "$STATUS" = "success" ]; then
            MESSAGE="✅ Production 部署成功\n• 镜像: \`${{ inputs.image_tag }}\`\n• 触发者: ${{ github.actor }}\n• 时间: $(date -u +'%Y-%m-%d %H:%M UTC')"
          else
            MESSAGE="🚨 Production 部署失败\n• 镜像: \`${{ inputs.image_tag }}\`\n• 触发者: ${{ github.actor }}\n• 详情: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}\n• 已自动回滚到上一版本"
          fi
          # 接入 Slack/钉钉/飞书 webhook
          curl -X POST "${{ secrets.SLACK_WEBHOOK }}" \
            -H "Content-Type: application/json" \
            -d "{\"text\": \"$(echo -e "$MESSAGE")\"}"
```

**Production 部署的关键设计决策**：

1. **手动触发（workflow_dispatch）**：生产环境部署必须由人工触发，避免自动部署到生产环境带来的风险。操作者需要输入具体的镜像标签。
2. **Environment Protection Rules**：在 GitHub Settings → Environments → production 中配置：
   - ✅ Required reviewers（指定审批人）
   - ✅ Wait timer（可选：部署前等待 N 分钟）
   - ✅ Deployment branches（限制只能从 main 分支部署）
3. **镜像验证**：部署前先验证镜像确实存在，防止因镜像标签错误导致部署失败。
4. **烟雾测试 + 自动回滚**：部署后自动运行健康检查。如果失败，自动执行 `kubectl rollout undo` 回滚到上一个版本，无需人工介入。

---

### 8. 回滚机制

回滚是发布安全的最后防线。一个可以在 2 分钟内回滚的系统，团队才敢于频繁上线。本方案提供三种回滚手段：

#### 8.1 基于 Kustomize 的 GitOps 回滚（推荐）

```bash
# 方法一：回滚到上一个镜像标签
cd deploy/k8s/overlays/production
kustomize edit set image \
  ghcr.io/org/order-service=ghcr.io/org/order-service:<previous-tag>
git add deploy/ &amp;&amp; git commit -m "rollback: revert to <previous-tag>" &amp;&amp; git push
# ArgoCD 自动检测到 Git 变更并回滚
```

**优点**：回滚过程有完整的 Git 记录，所有变更可追溯。

#### 8.2 基于 kubectl 的即时回滚（应急手段）

```bash
# 方法二：直接使用 kubectl 回滚（绕过 GitOps）
kubectl rollout undo deployment/order-service -n production

# 查看回滚历史
kubectl rollout history deployment/order-service -n production

# 回滚到指定版本
kubectl rollout undo deployment/order-service -n production --to-revision=3
```

**注意**：这种方式会导致集群状态与 Git 不一致（配置漂移）。ArgoCD 的 `selfHeal` 会在 3 分钟内将状态修复回 Git 定义。因此这只适合紧急场景，事后需要补一次 GitOps 回滚。

#### 8.3 基于 Git 的审计追溯

每一次部署都在 Git 历史中有记录，可以快速定位：

```bash
# 查看最近的部署记录
git log --oneline deploy/k8s/overlays/production/ | head -10

# 输出示例：
# a1b2c3d release: deploy f4e5d6c to production
# b2c3d4e release: deploy e3d4c5b to production
# c3d4e5f release: deploy d2c3b4a to production

# 查看某次部署的具体变更
git show a1b2c3d -- deploy/

# 查看两个版本之间的所有部署
git log --oneline abc1234..def5678 -- deploy/k8s/overlays/production/
```

#### 8.4 回滚决策流程图

```mermaid
flowchart TD
    A[线上问题发现] --> B{问题严重程度?}
    B -->|P0 紧急<br/>服务不可用| C[kubectl rollout undo<br/>即时回滚 < 1分钟]
    B -->|P1 重要<br/>功能异常| D[Git revert + Push<br/>ArGoCD回滚 < 3分钟]
    B -->|P2 一般<br/>体验问题| E[修复代码 + 新部署<br/>热修复 < 15分钟]
    C --> F[事后复盘]
    D --> F
    E --> F
    F --> G[更新回滚Runbook<br/>补充监控告警]
```

---

### 9. 完整流水线配置

将上述所有阶段组合起来，以下是完整的 CI workflow 文件：

```yaml
# .github/workflows/ci.yaml
name: CI Pipeline

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

# 取消同一 PR 的旧 workflow run，节省资源
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

env:
  PYTHON_VERSION: '3.12'

jobs:
  # ---- 阶段一：快速反馈（并行运行）----
  lint:
    name: Code Quality
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: 'pip'
      - name: Install lint tools
        run: pip install ruff mypy bandit[toml] types-requests
      - name: Ruff Lint
        run: ruff check app/ tests/ --output-format=github
      - name: Ruff Format Check
        run: ruff format --check app/ tests/
      - name: Type Check
        run: mypy app/ --ignore-missing-imports --no-error-summary
      - name: Security Scan (Bandit)
        run: bandit -c pyproject.toml -r app/ -ll

  unit-tests:
    name: Unit Tests
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: 'pip'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
      - name: Run unit tests
        run: |
          pytest tests/unit/ \
            -v \
            --cov=app \
            --cov-report=term-missing \
            --cov-report=xml:coverage.xml \
            --junitxml=test-results.xml
      - name: Check coverage threshold
        run: coverage report --fail-under=80
      - name: Upload coverage to Codecov
        if: always()
        uses: codecov/codecov-action@v4
        with:
          file: coverage.xml
          fail_ci_if_error: false
          flags: unit-tests
      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: unit-test-results
          path: test-results.xml

  security:
    name: Security Scan
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: 'pip'
      - name: Install tools
        run: pip install pip-audit bandit[toml]
      - name: Dependency vulnerability scan
        run: pip-audit -r requirements.txt --strict
      - name: Build image for scanning
        run: docker build -t order-service:scan .
      - name: Trivy container scan
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: 'order-service:scan'
          format: 'sarif'
          output: 'trivy-results.sarif'
          severity: 'CRITICAL,HIGH'
          exit-code: '1'
      - name: Upload scan results
        uses: github/codeql-action/upload-sarif@v3
        if: always()
        with:
          sarif_file: 'trivy-results.sarif'
      - name: Gitleaks secret scan
        uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

  # ---- 阶段二：集成测试（依赖阶段一全部通过）----
  integration-tests:
    name: Integration Tests
    runs-on: ubuntu-latest
    timeout-minutes: 15
    needs: [lint, unit-tests]  # 静态检查和单元测试通过后才运行
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_DB: order_test
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      redis:
        image: redis:7
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: 'pip'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
      - name: Run database migrations
        run: alembic upgrade head
        env:
          DATABASE_URL: postgresql+asyncpg://test:test@localhost:5432/order_test
      - name: Run integration tests
        run: |
          pytest tests/integration/ -v --tb=short \
            --junitxml=integration-results.xml
        env:
          DATABASE_URL: postgresql+asyncpg://test:test@localhost:5432/order_test
          REDIS_URL: redis://localhost:6379/0
      - name: Upload integration results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: integration-test-results
          path: integration-results.xml

  # ---- 阶段三：构建与推送（依赖所有测试通过）----
  build-and-push:
    name: Build &amp; Push Image
    runs-on: ubuntu-latest
    timeout-minutes: 10
    needs: [lint, unit-tests, security, integration-tests]
    permissions:
      contents: read
      packages: write
    outputs:
      image_tag: ${{ steps.meta.outputs.version }}
      image_digest: ${{ steps.build.outputs.digest }}
    steps:
      - uses: actions/checkout@v4
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      - name: Login to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ghcr.io/${{ github.repository }}
          tags: |
            type=sha,prefix=,format=short
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}
            type=raw,value=latest,enable={{is_default_branch}}
      - name: Build and push
        id: build
        uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
          platforms: linux/amd64
      - name: Generate SBOM
        uses: anchore/sbom-action@v0
        with:
          image: ghcr.io/${{ github.repository }}:${{ steps.meta.outputs.version }}
          format: spdx-json
          output-file: sbom.spdx.json
      - name: Upload SBOM
        uses: actions/upload-artifact@v4
        with:
          name: sbom
          path: sbom.spdx.json
          retention-days: 90
```

**Job 依赖关系与并行策略**：

```mermaid
flowchart LR
    subgraph 并行["⚡ 并行阶段（~3分钟）"]
        L[Lint<br/>~30s]
        U[Unit Tests<br/>~3min]
        S[Security Scan<br/>~2min]
    end
    
    subgraph 串行["🔗 串行阶段（~10分钟）"]
        I[Integration Tests<br/>~5min]
        B[Build &amp; Push<br/>~3min]
    end
    
    L &amp; U &amp; S --> I --> B
    
    style 并行 fill:#e8f5e9
    style 串行 fill:#fff3e0
```

---

### 10. 监控与可观测性

CI/CD 流水线本身也需要监控。正如你在生产环境中监控应用一样，流水线的健康状况同样重要。

#### 10.1 DORA 四大指标

DORA（DevOps Research and Assessment）提出的四大指标是衡量 CI/CD 成熟度的行业标准：

| 指标 | 含义 | 精英水平 | 本方案目标 | 采集方式 |
|------|------|----------|------------|----------|
| 部署频率 | 单位时间内的部署次数 | 按需（一天多次） | > 1次/天 | GitHub Releases |
| 变更前置时间 | 代码提交到上线的平均时间 | < 1 小时 | < 30 分钟 | GitHub Actions + ArgoCD |
| 变更失败率 | 导致回滚或热修复的部署占比 | 0-15% | < 5% | 告警 + 人工记录 |
| MTTR | 从故障到恢复的平均时间 | < 1 小时 | < 30 分钟 | 监控系统 + 告警 |

**如何计算这些指标**：
- **部署频率**：`git log --oneline --since="1 month ago" -- deploy/ | wc -l` 或查看 GitHub Releases 数量。
- **变更前置时间**：从 GitHub Actions 的 workflow run 时间戳中提取触发时间到完成时间的差值。
- **变更失败率**：统计导致告警或回滚的部署次数，除以总部署次数。
- **MTTR**：从告警触发到告警恢复的时间差，由监控系统（如 PagerDuty、Grafana OnCall）自动计算。

#### 10.2 流水线通知策略

```yaml
# 在 CI workflow 最后添加通知 Job
  notify:
    name: Notify
    runs-on: ubuntu-latest
    needs: [build-and-push]
    if: always()  # 无论成功失败都发送通知
    steps:
      - name: Notify on success
        if: needs.build-and-push.result == 'success'
        run: |
          curl -X POST "${{ secrets.SLACK_WEBHOOK }}" \
            -H "Content-Type: application/json" \
            -d '{
              "blocks": [{
                "type": "section",
                "text": {
                  "type": "mrkdwn",
                  "text": "✅ *CI Pipeline 成功*\n• 分支: `${{ github.ref_name }}`\n• 提交: `${{ github.sha }}`\n• 触发者: ${{ github.actor }}\n• 耗时: ${{ github.event.workflow_run.duration_seconds || 'N/A' }}s"
                }
              }]
            }'

      - name: Notify on failure
        if: needs.build-and-push.result == 'failure'
        run: |
          curl -X POST "${{ secrets.SLACK_WEBHOOK }}" \
            -H "Content-Type: application/json" \
            -d '{
              "blocks": [{
                "type": "section",
                "text": {
                  "type": "mrkdwn",
                  "text": "🚨 *CI Pipeline 失败*\n• 分支: `${{ github.ref_name }}`\n• 提交: `${{ github.sha }}`\n• 触发者: ${{ github.actor }}\n• 详情: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"
                }
              }]
            }'
```

---

### 11. 常见问题与最佳实践

#### 11.1 流水线运行太慢

**问题**：每次推送代码都要等 20 分钟才能得到反馈，严重影响开发效率。

**解决方案**：

```yaml
# 策略一：分层反馈，快速失败
# 将快速检查放在前面，如果失败就不运行耗时的测试
jobs:
  fast-checks:
    # Lint + Format: 30秒内完成
    steps: [lint, format-check]

  unit-tests:
    needs: [fast-checks]  # 只有快速检查通过才运行
    steps: [unit-test]

  integration-tests:
    needs: [unit-tests]
    steps: [integration-test]
```

```yaml
# 策略二：使用缓存加速依赖安装
- uses: actions/cache@v4
  with:
    path: ~/.cache/pip
    key: pip-${{ runner.os }}-${{ hashFiles('requirements*.txt') }}
    restore-keys: |
      pip-${{ runner.os }}-
```

```yaml
# 策略三：测试分片并行
  test-sharded:
    strategy:
      matrix:
        shard: [1, 2, 3, 4]
    steps:
      - name: Run tests (shard ${{ matrix.shard }}/4)
        run: |
          pytest tests/unit/ -v --splits 4 --group ${{ matrix.shard }} --splitting-algorithm least_duration
```

#### 11.2 Flaky Test（不稳定测试）

**问题**：某些测试有时通过有时失败，与代码质量无关。Flaky test 会严重侵蚀团队对 CI 的信任——如果 CI 经常误报，开发者会开始忽略失败。

**解决方案**：

```yaml
      - name: Run tests with retry (isolate flaky tests)
        run: |
          # 先运行稳定测试
          pytest tests/ -v -m "not flaky" --tb=short
          # 再单独运行不稳定测试（允许重试）
          pytest tests/ -v -m "flaky" --reruns 3 --reruns-delay 5 --tb=short
```

```python
# 在测试代码中标记不稳定测试
import pytest

@pytest.mark.flaky(reruns=3, reruns_delay=2)
async def test_external_api_call():
    """依赖外部API的测试，网络波动可能导致失败"""
    ...
```

**根治方案**：为每个 flaky test 创建 Issue，设置 SLA（如 2 周内修复或删除）。定期清理不再维护的 flaky test。

#### 11.3 密钥管理

**问题**：CI/CD 流水线需要访问 Docker Registry、Kubernetes 集群、Slack Webhook 等敏感凭证。

**分层管理策略**：

| 密钥类型 | 存放位置 | 轮换频率 | 适用场景 |
|----------|----------|----------|----------|
| GITHUB_TOKEN | 自动提供 | 自动 | 读取仓库、推送镜像到 GHCR |
| DEPLOY_TOKEN | GitHub Secrets | 90 天 | push 部署配置到仓库 |
| SLACK_WEBHOOK | GitHub Secrets | 180 天 | 通知 |
| 数据库密码 | K8s Secret + Sealed Secrets | 30 天 | 应用运行时 |
| 云服务密钥 | OIDC（无密钥） | N/A | AWS/GCP/Azure |

```yaml
# 使用 OIDC 访问 AWS（替代长期 Access Key，无需存储任何密钥）
- name: Configure AWS credentials
  uses: aws-actions/configure-aws-credentials@v4
  with:
    role-to-assume: arn:aws:iam::123456789012:role/GitHubActions
    aws-region: ap-northeast-1
```

**OIDC 的优势**：GitHub Actions 通过 OpenID Connect 协议向 AWS STS 申请临时凭证，凭证自动过期，无需在 GitHub Secrets 中存储长期 Access Key。即使 Secret 泄露，攻击者也只能获得短期有效的凭证。

#### 11.4 矩阵构建的资源优化

**问题**：需要在多个 Python 版本和操作系统上测试，但不想每次都运行全量矩阵。

```yaml
  test:
    strategy:
      fail-fast: false  # 一个组合失败不影响其他组合
      matrix:
        python-version: ['3.11', '3.12']
        os: [ubuntu-latest, macos-latest]
        exclude:
          # 排除低版本 Python + macOS 的组合（节省资源）
          - python-version: '3.11'
            os: macos-latest
        include:
          # 只在一个组合上收集覆盖率
          - python-version: '3.12'
            os: ubuntu-latest
            coverage: true
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - run: pytest tests/unit -v
      - name: Upload coverage
        if: matrix.coverage
        uses: codecov/codecov-action@v4
```

**`fail-fast: false` 的重要性**：默认 `fail-fast: true` 意味着一个组合失败后立即取消其他组合。设为 `false` 可以让所有组合都跑完，这样一次就能看到所有平台上的问题，避免修一个再发现另一个。

---

### 12. 实施效果与数据

搭建CI/CD流水线前后的关键指标对比：

| 指标 | 改造前 | 改造后 | 提升幅度 |
|------|--------|--------|----------|
| 部署耗时 | 20-30 分钟（手动） | 15 分钟（自动化） | 50-75% |
| 部署频率 | 每周 1-2 次 | 每天 3-5 次 | 5-10x |
| 回滚时间 | 30+ 分钟（手动） | < 2 分钟（自动化） | 95% |
| 线上 Bug 率 | ~15% 的发布引入 Bug | < 3% | 80% |
| 部署成功率 | ~85% | > 99% | 14% |
| 开发者等待时间 | 20-30 分钟（部署） | 0（无需等待） | N/A |
| 环境一致性问题 | 每周 2-3 次 | 0 | 100% |
| 安全漏洞发现时机 | 上线后 | 构建阶段 | 左移 |

**ROI 分析**：以 8 人团队、平均薪资 30K/月计算，部署效率提升带来的开发时间节约约为每月 40-60 人时（手动部署耗时 × 部署次数 × 团队规模）。加上线上 Bug 减少导致的运维成本降低，通常 2-3 个月即可收回 CI/CD 搭建的投入。

---

### 13. 经验总结

1. **渐进式采用**：不要试图一步到位。建议先搭建最基础的 CI（Lint + Unit Test），运行稳定后再添加集成测试、安全扫描、自动部署。每次只增加一个环节，验证稳定后再添加下一个。急于求成往往导致流水线频繁失败，团队信任度下降。

2. **反馈速度是生命线**：流水线超过 15 分钟，开发者的使用意愿就会显著下降。持续优化构建缓存、测试并行度和增量测试策略。把"等 CI"变成"CI 已经通过了"。

3. **不可变制品是基石**：同一个制品从 Staging 到 Production，绝不重新构建。这是保证"测试通过的代码就是上线的代码"的根本手段。一旦允许"重新构建一下再部署"，就会出现"构建环境不一样导致结果不同"的问题。

4. **Git 是唯一真相源**：通过 GitOps，生产环境的状态完全由 Git 中的声明式配置决定。任何手动修改都会被 ArgoCD 自动修复（selfHeal），消除了配置漂移的风险。

5. **回滚能力决定上线信心**：一个可以在 2 分钟内回滚的系统，团队才敢于频繁上线。回滚不是失败的标志，而是发布安全的保障。

6. **安全左移而非右移**：在代码提交阶段就扫描漏洞，比上线后被外部安全团队报告要好得多。早期修复的成本是后期的 1/10 到 1/100。

7. **度量驱动改进**：部署频率、变更前置时间、变更失败率、MTTR（DORA 四大指标）是衡量 CI/CD 成熟度的核心指标。定期回顾这些指标，针对性地改进薄弱环节。

---

### 14. 延伸方向

完成本案例的基础流水线后，可以在以下方向进一步演进：

| 演进方向 | 工具 | 价值 | 适用阶段 |
|----------|------|------|----------|
| 金丝雀发布 | Argo Rollouts + Istio | 渐进式发布，降低生产风险 | 日部署 > 10 次 |
| 蓝绿部署 | Argo Rollouts | 零停机切换，秒级回滚 | SLA 要求 > 99.99% |
| 混沌工程 | Litmus Chaos / Chaos Mesh | 验证系统在故障场景下的韧性 | 团队 > 15 人 |
| 成本优化 | Kubecost / OpenCost | 监控和优化 K8s 资源使用成本 | 月 K8s 开销 > ¥10,000 |
| 多集群部署 | ArgoCD ApplicationSet | 一次配置，多集群同步 | 多区域部署 |
| E2E 测试 | Playwright / Cypress | 用户视角的端到端验证 | 核心业务流程 |
| 性能回归检测 | k6 / Grafana k6 | 每次部署自动检测性能退化 | 对性能敏感的服务 |
| 策略即代码 | OPA Gatekeeper | 自动化合规检查 | 金融/医疗行业 |
| SBOM 与供应链安全 | SLSA / Sigstore | 验证制品来源的完整性 | 安全合规要求高 |
| 内部开发者平台 | Backstage | 统一开发者门户和自助服务 | 团队 > 30 人 |

**建议的演进路线**：基础 CI/CD（当前阶段）→ 测试优化与并行化 → 安全扫描深化 → 金丝雀/蓝绿发布 → 混沌工程 → 内部开发者平台。每个阶段稳定运行 2-4 周后再进入下一阶段。

---

本案例提供了一个可直接复用的 CI/CD 流水线模板。根据团队规模和业务需求，可以裁剪不需要的阶段（如小型项目可以去掉集成测试和安全扫描），也可以增加更多阶段（如 E2E 测试、性能测试）。核心原则不变：**快速反馈、不可变制品、GitOps 声明式管理、完善的安全防线**。
