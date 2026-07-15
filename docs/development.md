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
src/zte_cfg_tools/format.py  DB 0..4、AES-CBC、zlib、CRC
src/zte_cfg_tools/keys.py    paramtag、INDIVKEY、profile
src/zte_cfg_tools/e8.py      ctce8/e8_Config_Backup 封套
src/zte_cfg_tools/cli.py     PyPI 入口 zte-cfg
scripts/                     BusyBox ash 设备端采集脚本
tests/                       格式、密钥、封套 round-trip
```

## 发布

`.github/workflows/ci.yml` 在 push/PR 时运行测试和构建。
`.github/workflows/publish.yml` 只在 GitHub Release 发布时执行，使用 PyPI Trusted
Publisher。首次发布前，需要在 PyPI 项目设置中把 GitHub 仓库、workflow 文件名和
environment 配置成可信发布者。

项目不提交真实设备的 `db_*.xml`、`paramtag`、`zte-cfg-keys.json` 或 hardcode
文件；这些内容包含设备唯一密钥和用户配置。

