# 操作流程与调用关系

## 本地离线流程

```mermaid
flowchart LR
    A["ONU: device_collect.sh"] --> B["cfg + tagparam archive"]
    B --> C["本地 zte-cfgs keys"]
    C --> D["zte-cfgs-keys.json"]
    D --> E["unpack db_user/default/e8"]
    E --> F["编辑 XML"]
    F --> G["pack DB version 3/4"]
    G --> H["e8-pack 可选封套"]
    H --> I["人工备份后替换/导入"]
```

## 数据库解包调用关系

```mermaid
sequenceDiagram
    participant CLI as zte-cfgs
    participant Key as keys.py
    participant DB as format.py
    participant AES as AES-CBC
    participant Z as zlib
    CLI->>Key: 读取 key profile / INDIVKEY
    CLI->>DB: parse_header()
    alt version 0
        DB->>Z: unpack compressed container
    else version 1
        DB-->>CLI: 60 字节头后的 XML
    else version 2
        DB->>Z: 解包头后的 inner container
    else version 3/4
        DB->>AES: 按块解密
        AES-->>DB: inner container
        DB->>Z: 解压并校验 CRC
    end
    DB-->>CLI: XML + metadata
```

## e8 封套关系

```mermaid
flowchart TD
    U["ctce8_型号.cfg"] --> H["解析 0x00 wrapper header"]
    H --> M["解析 model header"]
    M --> DB["提取 db_user_cfg 容器"]
    DB --> K["INDIVKEY / profile"]
    K --> AES["AES-CBC 解密"]
    AES --> INF["zlib + CRC"]
    INF --> XML["XML"]
    XML --> PACK["pack 生成完整 DB"]
    PACK --> WRAP["e8-pack 使用模板重封套"]
```

## 设备生命周期边界

本项目只负责离线文件：`cspd` 在设备启动时把文件加载到 shared memory，运行态
修改由 `sendcmd`/`ztedbcli` 写入 DB server，保存流程再生成文件。离线替换前应
停止会覆盖配置的管理流程，保留原文件和 checksum，并通过设备自身的导入/保存
路径验证；不要把跨设备 key 或跨设备 e8 备份当作可移植配置。

