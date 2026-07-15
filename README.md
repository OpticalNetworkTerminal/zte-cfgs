# zte-cfg-tools

ZTE ONU 配置文件的离线解包、解密、修改、重新加密和封套工具。
项目只处理配置文件格式，不连接设备、不修改运行态 DB，也不提供设备入侵功能。

## 安装

发布后：

```bash
python3 -m pip install zte-cfg-tools
```

源码测试：

```bash
cd zte-cfg-tools
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[test]'
```

安装后只有一个主入口：`zte-cfg`。

```text
zte-cfg info FILE
zte-cfg keys PARAMTAG [-o zte-cfg-keys.json]
zte-cfg unpack FILE -o OUTPUT [crypto options]
zte-cfg pack XML OUTPUT [crypto options]
zte-cfg e8-pack TEMPLATE_CFG DB_CONTAINER OUTPUT_CFG
```

## 普通用户流程

先从正在使用的光猫读取本机 `INDIVKEY`。脚本兼容 BusyBox `ash`，只依赖
`hexdump`、`awk`、`md5sum` 和基础 shell 工具，不使用 `command`、`dd` 或 bash：

```bash
scp scripts/device_print_indivkey.sh root@ONT:/tmp/
ssh root@ONT 'ash /tmp/device_print_indivkey.sh'
```

如果要一次导出配置和派生所需的文件：

```bash
scp scripts/device_collect.sh root@ONT:/tmp/
ssh root@ONT 'ash /tmp/device_collect.sh'
scp root@ONT:/tmp/zte-cfg-tools-时间戳.tgz .
tar -xzf zte-cfg-tools-时间戳.tgz
```

也可以只把 `/tagparam/paramtag` 下载到本地。生成本机 key profile：

```bash
zte-cfg keys ./paramtag -o zte-cfg-keys.json
```

解密用户配置：

```bash
zte-cfg unpack ./db_user_cfg.xml -o out-user \
  --paramtag ./paramtag --keys-file ./zte-cfg-keys.json --strict-crc
```

解密默认配置：

```bash
zte-cfg unpack ./db_default_cfg.xml -o out-default \
  --profile default --keys-file ./zte-cfg-keys.json --strict-crc
```

输出目录包含明文 XML 和同名 JSON 元数据。编辑 XML 后，使用原始 DB 文件作为
模板保留版本号：

```bash
zte-cfg pack out-user/db_user_cfg.xml.xml db_user_cfg.new.xml \
  --template ./db_user_cfg.xml --profile user \
  --keys-file ./zte-cfg-keys.json
```

## e8_Config_Backup / U 盘备份

管理台导出的 `e8_Config_Backup/ctce8_*.cfg` 是“封套 + 内嵌 DB 容器”。自动识别
封套并解密：

```bash
zte-cfg unpack ./ctce8_G7615-G-C.cfg -o out-e8 \
  --paramtag ./paramtag --keys-file ./zte-cfg-keys.json --strict-crc
```

把重新打包的 DB 放回原封套：

```bash
zte-cfg e8-pack ./ctce8_G7615-G-C.cfg db_user_cfg.new.xml \
  ./ctce8_G7615-G-C.new.cfg
```

`e8-pack` 不会重新加密 DB；它要求输入已经由 `zte-cfg pack` 生成的完整 DB
容器。这样可以分别验证“XML -> DB”与“DB -> e8 封套”。

## 参数与版本

`--profile auto` 按文件名选择 `default` 或 `user`，`backup` 与 `user` 使用同一
套本机 user key。也可以明确传入：

```bash
zte-cfg unpack db_user_cfg.xml -o out --key-string KEY --iv-string IV
```

兼容 `zxcfg` 的 pack type 也可使用：`--pack-type 0` 为无 AES、`1` 为版本 3
默认 key、`2` 为版本 4 用户 key；更明确的写法是直接使用 `--version 0..4`。

数据库容器版本含义：

| 版本 | 处理方式 |
| --- | --- |
| 0 | zlib 分块容器，无 AES |
| 1 | 60 字节版本头后直接为 XML |
| 2 | 版本头后为 zlib 容器，无 AES |
| 3 | AES-CBC 外层 + zlib 内层，默认 DB key |
| 4 | AES-CBC 外层 + zlib 内层，用户 DB key |

本项目使用已验证的实现：物理 AES key 为
`SHA256(key_string[0:31])`，物理 IV 为 `SHA256(iv_string[0:31])[0:16]`，
AES 模式为 CBC，数据库块使用零填充到 16 字节。`--strict-crc` 会同时检查内层
header CRC、压缩内容 CRC、块长度和 XML 内容长度。

`INDIVKEY` 的当前新设备路径为：

```text
tagparam tag 0x0720 / ID 1824
  -> CspGetMD5(seed, 33)        # 包含 C 字符串 NUL
  -> hex MD5
  -> cspd slot 有效字符串前 31 字节
  -> SHA256
  -> AES-256-CBC key
```

`zte-cfg keys` 会生成四个候选模式，`unpack --paramtag` 会以结构校验自动选择：
`md5-nul-truncated`、`md5-nul-full`、`md5-truncated`、`md5-full`。当前 G7615
样本验证成功的是 `md5-nul-truncated`。不同型号必须以本机配置文件的校验结果为准。

## 参考与边界

本项目参考了 [yuleniwo/zxcfg](https://github.com/yuleniwo/zxcfg) 的命令分层和
版本模型。该项目公开说明了 unpack、XML/CFG pack、default/user key、key generation
和 paramtag 输入等模式；本项目在 Python 中重新实现，并加入当前设备观察到的
`db_user_cfg.xml` 外层 AES 块、`INDIVKEY` 派生和 e8 封套操作。

当前实现不会假设 LOID、SN、MAC 一定参与 user DB key 派生；如果 `INDIVKEY` 不存在，
应显式传入厂商/固件实际使用的 key，不能跨设备复用 key profile。

## 文档

- [格式与版本](docs/format.md)
- [密钥与 INDIVKEY](docs/keys.md)
- [工作流与 Mermaid](docs/workflow.md)
- [发布与开发](docs/development.md)

## 开发

```bash
python3 -m pip install -e '.[test]'
python3 -m pytest -q
python3 -m build
```

GitHub Actions 会测试 Python 3.10 到 3.13，构建 wheel/sdist；创建 GitHub Release
后，`publish.yml` 可通过 PyPI Trusted Publisher 发布，不需要把 token 写入仓库。

## 许可

MIT。设备文件、密钥和导出的 XML 不应提交到公开仓库。
