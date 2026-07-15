# zte-cfgs

ZTE ONU 配置文件的离线解包、解密、修改、重新加密和 U 盘备份封套工具。
项目只处理本地文件，不连接设备、不修改运行态 DB，也不会自动替换光猫文件。

## 1. 先理解文件类型

这些文件名很容易误导。`db_user_cfg.xml` 的后缀虽然是 `.xml`，但原始文件实际
是二进制数据库容器，不能直接用文本编辑器打开。

| 文件或目录 | 文件状态 | 可以直接编辑吗 | 用途 |
| --- | --- | --- | --- |
| `db_user_cfg.xml` | 原始二进制，通常是 version 4 AES 加密 | 否 | 当前设备的用户配置 |
| `db_backup_cfg.xml` | 原始二进制，通常使用同一台设备的 user key | 否 | 用户配置备份 |
| `db_default_cfg.xml` | 原始二进制，通常是 version 3 默认 key | 否 | 默认配置 |
| `ctce8_型号.cfg` | 原始 U 盘备份，外层封套内含 DB 容器 | 否 | 管理台“备份到 U 盘”的文件 |
| `paramtag` | 设备二进制参数文件，通常来自 `/tagparam/paramtag` | 否 | 读取本机 `INDIVKEY` |
| `zte-cfgs-keys.json` | 本地生成的 JSON key profile | 不要手工修改 | 保存本机 user/default key 信息 |
| `out-user/*.xml` | 解密、解压后的明文 XML | 是 | 修改配置的工作文件 |
| `db_user_cfg.new.xml` | 重新压缩、重新加密后的二进制 DB | 否 | 写回设备或放进 e8 封套 |
| `ctce8_型号.new.cfg` | 新生成的 U 盘备份文件 | 否 | 导入管理台或保存备用 |

最重要的文件流是：

```text
原始 db_user_cfg.xml（二进制）
    -> unpack
out-user/db_user_cfg.xml（明文 XML）
    -> 编辑
db_user_cfg.new.xml（二进制，重新压缩并加密）
    -> e8-pack，可选
ctce8_型号.new.cfg（新的 U 盘备份封套）
```

## 2. 安装

### 从 PyPI 安装

```bash
python3 -m pip install --upgrade zte-cfgs
```

安装完成后使用的命令只有一个：`zte-cfgs`。

```bash
zte-cfgs --help
```

### 从源码安装

```bash
cd zte-cfgs
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[test]'
```

## 3. 设备端准备文件

### 3.1 只读取 INDIVKEY

把脚本上传到光猫，在光猫 root shell 中执行。脚本兼容 BusyBox `ash`，不依赖
`bash`、`command` 或 `dd`。

```bash
scp scripts/device_print_indivkey.sh root@ONT:/tmp/
ssh root@ONT 'ash /tmp/device_print_indivkey.sh'
```

脚本会读取：

```text
/tagparam/paramtag
  -> tag 0x0720 / ID 1824
  -> INDIVKEY
  -> DB_USER_AES_KEY_STRING
  -> DB_USER_AES_IV_STRING
```

它会把 key、IV 和可以复制使用的 `export` 命令打印出来。这个 key 只能用于
对应设备，不能把 A 光猫的 `INDIVKEY` 用到 B 光猫。

### 3.2 一次性采集配置和 paramtag

如果还没有本地配置文件，推荐执行采集脚本：

```bash
scp scripts/device_collect.sh root@ONT:/tmp/
ssh root@ONT 'ash /tmp/device_collect.sh'
```

脚本会在设备 `/tmp` 生成类似下面的文件：

```text
/tmp/zte-cfgs-20260715-120000.tgz
```

下载并解压：

```bash
scp root@ONT:/tmp/zte-cfgs-20260715-120000.tgz .
tar -xzf zte-cfgs-20260715-120000.tgz
```

采集包内包含 `cfg/`、`tagparam/paramtag`、`hardcode` 和 manifest。也可以手工
下载下面这些文件：

```bash
scp root@ONT:/userconfig/cfg/db_user_cfg.xml .
scp root@ONT:/userconfig/cfg/db_backup_cfg.xml .
scp root@ONT:/userconfig/cfg/db_default_cfg.xml .
scp root@ONT:/tagparam/paramtag ./paramtag
scp root@ONT:/path/to/e8_Config_Backup/ctce8_G7615-G-C.cfg .
```

## 4. 命令总览

| 命令 | 作用 | 是否需要 key |
| --- | --- | --- |
| `zte-cfgs info FILE` | 查看文件类型、版本、封套和块信息 | 否 |
| `zte-cfgs keys PARAMTAG` | 从 paramtag 读取 INDIVKEY，生成 JSON key 文件 | 否 |
| `zte-cfgs unpack FILE` | 解密/解压 DB，或解包 e8 U 盘备份 | version 3/4 需要 |
| `zte-cfgs pack XML OUTPUT` | 把明文 XML 压缩并重新加密为 DB | version 3/4 需要 |
| `zte-cfgs e8-pack TEMPLATE DB OUTPUT` | 把新的 DB 放回原始 e8 封套 | 不在此步骤解密 |
| `zte-cfgs scripts` | 把设备端采集脚本导出到本地目录 | 否 |

下面每个命令的参数都单独说明。

## 5. `scripts`：导出设备端脚本

这个命令从已安装的 `zte-cfgs` 包内部导出脚本，不需要打开网站下载，也不需要
知道源码仓库位置。

命令格式：

```bash
zte-cfgs scripts [OPTIONS]
```

| 参数 | 必选 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `-o`, `--output` | 否 | 当前目录 `.` | 脚本导出目录 |
| `--force` | 否 | 关闭 | 覆盖目录中已有的同名脚本 |

导出到当前目录：

```bash
zte-cfgs scripts
```

`collect` 是同一个命令的别名：

```bash
zte-cfgs collect
```

输出：

```text
./device_collect.sh
./device_print_indivkey.sh
```

如果当前目录已经有同名文件，程序会停止并保护原文件。确认需要覆盖时：

```bash
zte-cfgs scripts --force
```

导出到指定目录：

```bash
zte-cfgs scripts --output ./device-scripts
```

然后上传并执行：

```bash
scp ./device-scripts/device_print_indivkey.sh root@ONT:/tmp/
ssh root@ONT 'ash /tmp/device_print_indivkey.sh'

scp ./device-scripts/device_collect.sh root@ONT:/tmp/
ssh root@ONT 'ash /tmp/device_collect.sh'
```

## 6. `info`：查看文件信息

命令格式：

```bash
zte-cfgs info FILE
```

| 参数 | 必选 | 说明 |
| --- | --- | --- |
| `FILE` | 是 | 原始 DB 文件或原始 `ctce8_*.cfg` 文件 |

示例：

```bash
zte-cfgs info db_user_cfg.xml
zte-cfgs info db_default_Henan_cfg.xml
zte-cfgs info ctce8_G7615-G-C.cfg
```

它不会解密文件，只显示：

- DB Magic 和 version
- 外层块数量、明文长度和密文长度
- e8 封套型号、模型长度、内嵌 DB 偏移和 DB version

## 7. `keys`：生成本机 key profile

命令格式：

```bash
zte-cfgs keys PARAMTAG [-o OUTPUT] [--iv USER_IV]
```

| 参数 | 必选 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `PARAMTAG` | 是 | 无 | 从光猫下载的二进制 `/tagparam/paramtag` |
| `-o`, `--output` | 否 | `zte-cfgs-keys.json` | 生成的本地 JSON 文件 |
| `--iv` | 否 | 当前设备常见 user IV | 覆盖 user DB IV 字符串 |

示例：

```bash
zte-cfgs keys ./paramtag -o ./zte-cfgs-keys.json
```

生成的 `zte-cfgs-keys.json` 内包含：

- `user`：本机 INDIVKEY 派生的 user DB key/IV
- `backup`：默认复制 user profile，因为当前设备的 backup DB 使用同一套 user key
- `default`：`PON_Dkey/PON_DIV` 默认配置 key/IV
- `indivkey`：本机 tag 里的原始 seed

注意：`paramtag` 是二进制文件，不是 JSON。以下写法是允许的兼容形式，程序会
自动识别 `TAGH` 头并直接读取 INDIVKEY：

```bash
zte-cfgs unpack db_user_cfg.xml -o out-user --keys-file ./paramtag
```

更清楚的写法是：

```bash
zte-cfgs unpack db_user_cfg.xml -o out-user --paramtag ./paramtag
```

## 8. `unpack`：解密并导出明文 XML

命令格式：

```bash
zte-cfgs unpack INPUT [OPTIONS]
```

### 7.1 `unpack` 参数

| 参数 | 必选 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `INPUT` | 是 | 无 | 原始 DB 文件，或原始 e8 U 盘备份 |
| `-o`, `--output` | 否 | `zte-cfgs-out` | 输出目录 |
| `--type` | 否 | `auto` | `auto`、`db` 或 `e8` |
| `--profile` | 否 | `auto` | `auto`、`default`、`user` 或 `backup` |
| `--keys-file` | 否 | 自动查找 JSON | JSON key 文件；也兼容直接传二进制 paramtag |
| `--paramtag` | 否 | 无 | 原始 `/tagparam/paramtag`，自动读取 INDIVKEY |
| `--indivkey` | 否 | 无 | 手工传入 INDIVKEY seed |
| `--key-string` | 否 | 无 | 手工传入已计算好的 key string |
| `--iv-string` | 否 | 无 | 手工传入已计算好的 IV string |
| `--strict-crc` | 否 | 关闭 | 校验 header CRC、内容 CRC、长度和块链 |

同一条命令只需要选择一种 key 来源，优先级大致如下：

1. `--key-string` 和 `--iv-string`
2. `--indivkey` 或 `--paramtag`
3. `--keys-file`
4. 当前目录的 `zte-cfgs-keys.json` 或 `db_keys.json`
5. `default` profile 的内置默认 key

### 7.2 解包用户 DB

原始输入：

```text
./db_user_cfg.xml
```

这是二进制加密文件，不是明文 XML。推荐直接使用原始 `paramtag`：

```bash
zte-cfgs unpack ./db_user_cfg.xml \
  --output ./out-user \
  --keys-file ./paramtag \
  --strict-crc
```

也可以使用已经生成的 JSON：

```bash
zte-cfgs unpack ./db_user_cfg.xml \
  --output ./out-user \
  --keys-file ./zte-cfgs-keys.json \
  --profile user \
  --strict-crc
```

输出：

```text
./out-user/db_user_cfg.xml       # 明文 XML，可以编辑
./out-user/db_user_cfg.json      # 解包元数据和实际使用的 key 来源
```

### 7.3 解包默认 DB

原始输入：

```text
./db_default_Henan_cfg.xml
```

使用 `default` profile：

```bash
zte-cfgs unpack ./db_default_Henan_cfg.xml \
  --output ./out-default \
  --profile default \
  --strict-crc
```

输出：

```text
./out-default/db_default_Henan_cfg.xml  # 明文 XML
./out-default/db_default_Henan_cfg.json # 解包元数据
```

### 7.4 解包 e8 U 盘备份

原始输入：

```text
./ctce8_G7615-G-C.cfg
```

它是原始 U 盘备份封套，内部仍然是加密的 `db_user_cfg` DB。执行：

```bash
zte-cfgs unpack ./ctce8_G7615-G-C.cfg \
  --output ./out-e8 \
  --keys-file ./paramtag \
  --strict-crc
```

输出：

```text
./out-e8/ctce8_G7615-G-C.embedded.xml  # 从 e8 封套取出并解密后的明文 XML
./out-e8/ctce8_G7615-G-C.embedded.json # e8 和 DB 解包元数据
```

这里的 `embedded.xml` 是明文 XML，可以直接编辑。它不是以后交给
`e8-pack` 的输入；交给 `e8-pack` 的是后面重新加密得到的 DB 容器。

## 9. `pack`：把修改后的明文 XML 重新压缩并加密

命令格式：

```bash
zte-cfgs pack XML_INPUT DB_OUTPUT [OPTIONS]
```

### 8.1 `pack` 参数

| 参数 | 必选 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `XML_INPUT` | 是 | 无 | 已解密、已修改的明文 XML |
| `DB_OUTPUT` | 是 | 无 | 新生成的二进制 DB；名称可带 `.xml`，但内容不是 XML |
| `--template` | 否 | 无 | 原始 DB 文件；自动复制它的 version |
| `--version` | 否 | `auto` | `0` 到 `4`；推荐使用 `--template` 自动匹配 |
| `--pack-type` | 否 | 无 | `0`=无 AES，`1`=version 3 默认 key，`2`=version 4 user key |
| `--profile` | 否 | `auto` | `default`、`user` 或 `backup` |
| `--keys-file` | 否 | 自动查找 JSON | JSON key 文件，也可以直接传 paramtag |
| `--paramtag` | 否 | 无 | 自动读取本机 INDIVKEY |
| `--indivkey` | 否 | 无 | 手工传入 INDIVKEY seed |
| `--key-string` | 否 | 无 | 手工传入 key string |
| `--iv-string` | 否 | 无 | 手工传入 IV string |
| `--level` | 否 | `9` | zlib 压缩等级，范围 `1` 到 `9` |

### 8.2 重新生成 user DB

原始文件和修改后的文件状态：

```text
./db_user_cfg.xml                 # 原始二进制 DB，仅用于 --template 和对照
./out-user/db_user_cfg.xml        # 明文 XML，已经修改
./db_user_cfg.new.xml             # 待生成，目前还不存在
```

执行：

```bash
zte-cfgs pack \
  ./out-user/db_user_cfg.xml \
  ./db_user_cfg.new.xml \
  --template ./db_user_cfg.xml \
  --profile user \
  --keys-file ./paramtag
```

参数对应关系：

| 命令片段 | 实际含义 |
| --- | --- |
| `./out-user/db_user_cfg.xml` | 输入：修改后的明文 XML |
| `./db_user_cfg.new.xml` | 输出：新的二进制 DB，已经压缩并 AES 加密 |
| `--template ./db_user_cfg.xml` | 使用原始 DB 的 version 4，不是读取 XML 内容 |
| `--profile user` | 使用 user DB key |
| `--keys-file ./paramtag` | 从本机 paramtag 派生 user key |

### 8.3 重新生成 default DB

```bash
zte-cfgs pack \
  ./out-default/db_default_Henan_cfg.xml \
  ./db_default_Henan_cfg.new.xml \
  --template ./db_default_Henan_cfg.xml \
  --profile default
```

这里：

- 输入 XML 是明文、可编辑的文件
- 输出 `.new.xml` 是二进制、已压缩、已加密的 DB
- `--profile default` 使用默认配置 key

## 10. `e8-pack`：生成新的 U 盘备份文件

这是最容易用错的命令。命令格式是：

```bash
zte-cfgs e8-pack ORIGINAL_CFG NEW_ENCRYPTED_DB OUTPUT_CFG
```

### 9.1 三个位置参数

| 位置 | 示例 | 文件状态 | 作用 |
| --- | --- | --- | --- |
| `ORIGINAL_CFG` | `./ctce8_G7615-G-C.cfg` | 原始 U 盘备份，二进制，仍是旧封套 | 作为封套模板，保留型号和头部字段 |
| `NEW_ENCRYPTED_DB` | `./db_user_cfg.new.xml` | 新生成的二进制 DB，已经压缩并加密 | 替换模板中原来的 DB 内容 |
| `OUTPUT_CFG` | `./ctce8_G7615-G-C.new.cfg` | 新生成的二进制 U 盘备份 | 最终输出文件，不覆盖原始文件 |

`NEW_ENCRYPTED_DB` 不能填写下面这些文件：

```text
out-user/db_user_cfg.xml                  # 错误：这是明文 XML
out-e8/ctce8_G7615-G-C.embedded.xml       # 错误：这是明文 XML
db_user_cfg.xml                            # 通常不推荐：这是原始旧 DB
```

必须填写 `zte-cfgs pack` 生成的二进制 DB，例如：

```text
db_user_cfg.new.xml                       # 正确：已压缩、已加密的 DB
```

### 9.2 完整命令示例

```bash
zte-cfgs e8-pack \
  ./ctce8_G7615-G-C.cfg \
  ./db_user_cfg.new.xml \
  ./ctce8_G7615-G-C.new.cfg
```

逐项解释：

```text
./ctce8_G7615-G-C.cfg
  原始 U 盘备份。只作为模板读取，不会被修改。

./db_user_cfg.new.xml
  由 zte-cfgs pack 产生的新的二进制 DB。
  虽然文件名以 .xml 结尾，但文件内容不是明文 XML。

./ctce8_G7615-G-C.new.cfg
  zte-cfgs e8-pack 生成的新 U 盘备份文件。
  这个文件可以和原始 cfg 对比，也可以作为后续导入文件。
```

`e8-pack` 只负责替换封套中的 DB 和更新长度字段，不负责 AES 加密。AES 加密
已经在前一步 `zte-cfgs pack` 完成。

### 9.3 e8 备份的完整 Demo

假设当前目录有：

```text
./ctce8_G7615-G-C.cfg       # 原始 U 盘备份
./db_user_cfg.xml           # 从同一台光猫导出的原始 user DB
./paramtag                  # 同一台光猫的 /tagparam/paramtag
```

第一步，解包原始 user DB，得到可编辑 XML：

```bash
zte-cfgs unpack ./db_user_cfg.xml \
  --output ./out-user \
  --keys-file ./paramtag \
  --strict-crc
```

第二步，用文本编辑器修改：

```text
./out-user/db_user_cfg.xml
```

第三步，把修改后的明文 XML 重新压缩并加密：

```bash
zte-cfgs pack \
  ./out-user/db_user_cfg.xml \
  ./db_user_cfg.new.xml \
  --template ./db_user_cfg.xml \
  --profile user \
  --keys-file ./paramtag
```

此时：

```text
./out-user/db_user_cfg.xml  # 明文 XML，输入文件
./db_user_cfg.new.xml       # 二进制 DB，已加密，pack 输出文件
```

第四步，验证新 DB 可以被同一台设备的 key 解包：

```bash
zte-cfgs unpack ./db_user_cfg.new.xml \
  --output ./verify-user \
  --keys-file ./paramtag \
  --strict-crc
```

确认下面文件存在且内容正确：

```text
./verify-user/db_user_cfg.new.xml
```

第五步，把新的二进制 DB 放进原始 U 盘封套，生成新的 cfg：

```bash
zte-cfgs e8-pack \
  ./ctce8_G7615-G-C.cfg \
  ./db_user_cfg.new.xml \
  ./ctce8_G7615-G-C.new.cfg
```

最终文件：

```text
./ctce8_G7615-G-C.cfg      # 原始文件，保留不动
./db_user_cfg.new.xml      # 新的已加密 DB
./ctce8_G7615-G-C.new.cfg  # 新的已封套 U 盘备份
```

## 11. key 参数的三种写法

### 写法 A：直接使用 paramtag，最简单

```bash
zte-cfgs unpack db_user_cfg.xml \
  --keys-file paramtag
```

### 写法 B：显式指定 paramtag

```bash
zte-cfgs unpack db_user_cfg.xml \
  --paramtag paramtag
```

### 写法 C：先生成 JSON，再反复使用

```bash
zte-cfgs keys paramtag -o zte-cfgs-keys.json
zte-cfgs unpack db_user_cfg.xml --keys-file zte-cfgs-keys.json
zte-cfgs pack edited.xml db_user_cfg.new.xml \
  --template db_user_cfg.xml \
  --keys-file zte-cfgs-keys.json
```

如果已经从设备端脚本获得了最终 key string 和 IV，也可以直接传入：

```bash
zte-cfgs unpack db_user_cfg.xml \
  --key-string 'KEY_STRING' \
  --iv-string 'IV_STRING'
```

`--keys-file` 应该指向 JSON key profile 或原始二进制 paramtag，不能指向普通
文本、明文 XML 或已加密 DB。

## 12. DB version 和 pack type

| DB version | 内容 |
| ---: | --- |
| `0` | zlib 分块容器，无 AES |
| `1` | 60 字节头后直接是明文 XML |
| `2` | 头后为 zlib 容器，无 AES |
| `3` | AES-CBC 外层 + zlib 内层，默认配置 key |
| `4` | AES-CBC 外层 + zlib 内层，user/backup key |

通常不要手工猜 version，直接使用原始文件作为模板：

```bash
zte-cfgs pack edited.xml output.xml --template original.xml --profile user
```

兼容 `zxcfg` 的 pack type：

| `--pack-type` | 对应 version | 用途 |
| ---: | ---: | --- |
| `0` | `0` | 压缩，不加 AES |
| `1` | `3` | 压缩，使用 default key 加密 |
| `2` | `4` | 压缩，使用 user key 加密 |

## 13. 校验和安全注意事项

使用 `--strict-crc` 时会检查：

- DB Magic
- version
- AES 块长度
- 内层压缩 Magic
- zlib/raw-deflate 解压结果
- XML 内容长度
- header CRC32
- 压缩内容 CRC32

当前实现的 AES 转换是：

```text
physical_key = SHA256(key_string[0:31])
physical_iv  = SHA256(iv_string[0:31])[0:16]
AES-256-CBC
```

`INDIVKEY` 来源为本机 `paramtag` 的 tag `0x0720` / ID `1824`。LOID、SN、MAC
和 XML 业务数据没有被当前样本证明参与 user DB key 派生，不要据此跨设备复用。

操作前应始终保留：

```text
db_user_cfg.xml
db_backup_cfg.xml
db_default_cfg.xml
原始 ctce8_*.cfg
原始 paramtag
```

## 14. PyPI 发布规则

项目版本统一使用 `v` 前缀，例如：

```toml
# pyproject.toml
version = "v0.2.0"
```

```python
# src/zte_cfgs/__init__.py
__version__ = "v0.2.0"
```

GitHub Actions 发布规则：

| GitHub 操作 | 发布目标 | workflow job |
| --- | --- | --- |
| push 到 `release` 或 `release/v*` 分支 | 正式 PyPI | `publish-pypi` |
| push `v*` tag，例如 `v0.2.0` | TestPyPI | `publish-testpypi` |
| 手动运行 workflow，选择 `pypi` | 正式 PyPI | `publish-pypi` |
| 手动运行 workflow，选择 `testpypi` | TestPyPI | `publish-testpypi` |
| 其他分支或普通 PR | 不发布 | 只由 CI 检查 |

tag 名称必须和 `pyproject.toml` 的版本完全一致：

```text
pyproject.toml: version = "v0.2.0"
Git tag:         v0.2.0
```

tag 版本不一致时，workflow 会在构建阶段失败，不会上传错误版本。

### GitHub 首次配置 Trusted Publisher

需要分别在 PyPI 和 TestPyPI 配置 publisher。进入对应平台的项目设置：
`Manage project -> Publishing -> Add a new publisher -> GitHub`，按下表填写：

| 平台 | Owner | Repository name | Workflow name | Environment name |
| --- | --- | --- | --- | --- |
| PyPI | `OpticalNetworkTerminal` | `zte-cfgs` | `publish.yml` | `pypi` |
| TestPyPI | `OpticalNetworkTerminal` | `zte-cfgs` | `publish.yml` | `testpypi` |

注意：`Workflow name` 填文件名 `publish.yml`，不要填完整路径；不要把
`release/v0.2.0` 填到 publisher 配置中，分支会由 GitHub OIDC claims 自动带上。
如果项目还不存在，使用对应平台的 **pending publisher**，字段仍然按上表填写。

GitHub Environments 名称必须完全一致。workflow 已为发布 job 设置
`id-token: write`，不需要把 API token 写入仓库。

### 手动触发发布

在 GitHub 网页打开 `Actions -> Publish package -> Run workflow`，选择要发布的
分支或 tag，再选择：

| `target` | 发布目标 | 建议选择的 ref |
| --- | --- | --- |
| `testpypi` | TestPyPI | `dev` 或其他测试分支 |
| `pypi` | 正式 PyPI | `release` 或 `release/v0.2.0` |

也可以使用 GitHub CLI：

```bash
# 使用 release/v0.2.0 分支手动发布正式 PyPI
gh workflow run publish.yml --ref release/v0.2.0 -f target=pypi

# 也可以使用 release 分支
gh workflow run publish.yml --ref release -f target=pypi

# 使用 dev 分支手动发布 TestPyPI
gh workflow run publish.yml --ref dev -f target=testpypi
```

手动发布同样不能覆盖已经存在的版本。发布前请确认当前 ref 中的
`pyproject.toml`、`src/zte_cfgs/__init__.py` 和目标索引中的版本没有重复。

### 推荐发布流程

先在开发分支修改版本并测试 TestPyPI：

```bash
git checkout dev

# 同时修改 pyproject.toml 和 src/zte_cfgs/__init__.py：v0.2.0 -> v0.2.1
python -m pytest -q
python -m build

git add pyproject.toml src/zte_cfgs/__init__.py
git commit -m "release: v0.2.1"
git tag v0.2.1
git push origin dev
git push origin v0.2.1
```

推送 tag 后，包会发布到 TestPyPI。验证 TestPyPI 安装：

```bash
python3 -m venv /tmp/zte-cfgs-test-venv
. /tmp/zte-cfgs-test-venv/bin/activate
python -m pip install --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ zte-cfgs==0.2.1
zte-cfgs --version
deactivate
```

验证通过后，把相同版本的提交合并或推送到 `release` 分支：

```bash
git checkout release
git merge dev
git push origin release
```

推送 `release` 后，workflow 会把相同版本发布到正式 PyPI：

```bash
python3 -m pip install --upgrade zte-cfgs
zte-cfgs --version
```

PyPI 不允许覆盖已发布版本。每次发布前必须递增版本号：
`v0.2.0 -> v0.2.1 -> v0.2.2`。

## 15. 文档与开发

- [格式与版本](docs/format.md)
- [密钥与 INDIVKEY](docs/keys.md)
- [工作流与 Mermaid](docs/workflow.md)
- [发布与开发](docs/development.md)

运行测试：

```bash
python3 -m pip install -e '.[test]'
python3 -m pytest -q
python3 -m build
```

设备文件、key profile、paramtag 和导出的 XML 不应提交到公开仓库。

## 许可

MIT License。
