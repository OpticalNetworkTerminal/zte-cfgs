# 开发与发布

## 本地检查

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[test]'
python -m pytest -q
python -m build
```

## 目录

```text
src/zte_cfgs/format.py  DB 0..4、AES-CBC、zlib、CRC
src/zte_cfgs/keys.py    paramtag、INDIVKEY、profile
src/zte_cfgs/e8.py      ctce8/e8_Config_Backup 封套
src/zte_cfgs/cli.py     PyPI 入口 zte-cfgs
scripts/                     BusyBox ash 设备端采集脚本
src/zte_cfgs/device_scripts/ PyPI 包内置的脚本资源
tests/                       格式、密钥、封套 round-trip
```

## 发布

`.github/workflows/ci.yml` 在 push/PR 时运行测试和构建。
`.github/workflows/publish.yml` 使用两条发布规则：推送 `release` 或 `release/v*`
分支发布正式 PyPI，推送 `v*` tag 发布 TestPyPI；同时支持手动 workflow_dispatch，并通过
`target` 选择 `pypi` 或 `testpypi`。`pyproject.toml` 和
`src/zte_cfgs/__init__.py` 使用带 `v` 的版本字符串，例如 `v0.2.0`；tag 必须
和该版本完全一致。

首次发布前，需要在 PyPI 和 TestPyPI 分别配置 Trusted Publisher。两边的 GitHub
publisher 字段都填写 `Owner=OpticalNetworkTerminal`、
`Repository=zte-cfgs`、`Workflow name=publish.yml`；Environment 分别填写：

| 平台 | Environment |
| --- | --- |
| PyPI | `pypi` |
| TestPyPI | `testpypi` |

官方发布 action 使用 OIDC，不需要把 API token 写入仓库。正式 PyPI 和 TestPyPI
是两个独立索引，即使版本号相同也不会互相覆盖；同一个索引上的版本不能重复上传。

项目不提交真实设备的 `db_*.xml`、`paramtag`、`zte-cfgs-keys.json` 或 hardcode
文件；这些内容包含设备唯一密钥和用户配置。
