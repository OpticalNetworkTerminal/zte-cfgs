# 配置容器格式

## 结论

文件名可能是 `.xml`，但当前 ZTE 数据库文件不是 XML。数据库容器使用大端
32 位字段，固定 60 字节头，随后是 12 字节块头和分块 payload。

```text
DB file
├── 0x00..0x3b  magic/version/reserved (15 x u32, big-endian)
└── 0x3c..     [plain_len, stored_len, next] + payload ...
                 └─ version 3/4: AES-CBC ciphertext
                    └─ decrypted data: inner compression container
                       └─ zlib block(s) -> XML
```

## 版本模式

| version | payload |
| ---: | --- |
| 0 | 文件本身是内层压缩容器 |
| 1 | 60 字节头之后直接是明文 XML |
| 2 | 60 字节头之后是内层压缩容器 |
| 3 | 外层块 AES 解密后得到内层压缩容器，默认配置 |
| 4 | 外层块 AES 解密后得到内层压缩容器，用户/备份配置 |

### H2-3e 的 version/type 0 变体

H2-3e 当前固件的 Web `config.bin` 仍将内层 payload type 写成 `0`，但块内容
不是 zlib，而是 AES-128-ECB 密文。AES key 是 16 个零字节；块头依次记录明文
有效长度、AES 对齐后的密文长度和续块标记/偏移（最后一块为 0）。读取时先尝试标准
zlib，失败后仅在块结构、AES 对齐和解密结果均通过 XML 校验时接受此变体，避免
把损坏的普通 type 0 文件误判为 H2-3e。

版本 3 和 4 的外层块 `plain_len` 记录解密后有效长度，`stored_len` 必须是
16 的倍数；实现会截掉 AES 零填充，再验证内层 Magic。

## 内层压缩容器

内层头字段：

| 偏移 | 字段 |
| ---: | --- |
| 0x00 | Magic `01 02 03 04` |
| 0x04 | inner version，当前为 0 |
| 0x08 | XML 原始长度 |
| 0x0c | 预留/最后块偏移字段 |
| 0x10 | 分块大小，通常 `0x10000` |
| 0x14 | 压缩内容 CRC32 |
| 0x18 | header CRC32，覆盖 `0x00..0x17` |
| 0x1c.. | 预留 |

每个压缩块包含原始长度、压缩长度、下一块标志和 zlib payload。代码同时接受
raw-deflate 作为兼容读取路径；重新打包固定使用 zlib，因为样本和 cspd 的
`inflate/deflate` 调用链已验证该格式。

## e8 U 盘封套

```text
0x00..0x0f  99 99 99 99 44 44 44 44 55 55 55 55 aa aa aa aa
0x10..0x7f  CFG header/type fields
0x80..      model magic + model length + model bytes
            db_user_cfg.xml container
```

`zte-cfgs e8-pack` 只替换 model header 后的 DB 容器，并更新 wrapper payload
长度；不会修改 DB 内部版本或密文。

H2-3e Web 备份在相同 128 字节封套之后，额外对整个签名和 DB payload 应用
89 字节循环 XOR。工具会自动识别并在解包时去除、重新打包时恢复这一层；XOR 的
位置从 header 指定的 payload offset 开始，不包含前 128 字节封套头。
