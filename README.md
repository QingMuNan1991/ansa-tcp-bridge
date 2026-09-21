<img width="430" height="430" alt="微信图片_20260912110609_11_156" src="https://github.com/user-attachments/assets/00f18553-dd01-40e8-8e47-cf72ca992269" />

欢迎关注“解忧CAE”公众号，共同交流ANSA/META仿真技巧



# ansa-tcp-bridge（中文使用说明）

一个**自托管的 MCP 服务器**，把 AI 客户端（WorkBuddy / Claude / Copilot / Cursor …）连到
BETA CAE Systems **ANSA** 上。它通过 ANSA 原生的 **IAPConnection（TCP）协议**连到
「listener 模式」的 ANSA（`-listenport 9999`），把约 49 个 ANSA 前处理操作封装成 MCP
工具；也可以绕过 MCP，直接在 Python 里把任意 ANSA 脚本发到 ANSA 执行。

---

## 1. 整体架构

```
AI 客户端 (WorkBuddy / Claude / …)
        │  MCP (stdio)
        ▼
  ansa-tcp-bridge  (FastMCP，本仓库)
        │  TCP :9999  (ANSA 原生 IAP 协议)
        ▼
  ANSA  (以 -listenport 9999 启动的 listener)
```

桥本身只是一个很薄的 Python 进程：它从 `<ANSA安装目录>/scripts/RemoteControl/ansa/`
导入 ANSA 自带的 `AnsaProcessModule.py` 来"说"IAP 协议，再把每次工具调用拼成一段
Python 片段发给 ANSA，由 ANSA 自己在它的解释器里执行并返回 `dict[str, str]`。

---

## 2. 前置条件

| 条件 | 说明 |
|---|---|
| ANSA 已正确授权 | 测试环境 ANSA 25.1.4，理论上 ≥18.1 可用 |
| ANSA 必须以 **listener 模式**启动 | `ansa64.bat -nolauncher -listenport 9999 -foregr -b` |
| 独立的 Python venv | **不要**用 WorkBuddy 共享的 venv（那里 `mcp` 锁死 1.29.1 给 ansa-tools/meta-api 用）。本机专用：`C:\Users\Admin\.workbuddy\binaries\python\envs\ansa-tcp\` |
| `ANSA_SCRIPTS_PATH` 指向正确目录 | **本机 ANSA 装在 `D:` 盘**：`D:\Program Files (x86)\BETA_CAE_Systems\ansa_v25.1.4\scripts`（见下方"坑①"） |

---

## 3. 快速开始（三步）

### 步骤 1 — 启动 ANSA listener

> ⚠️ **重要**：见第 6 节"坑①"，`ANSA_SCRIPTS_PATH` 必须指向 **D 盘**真实安装路径，
> 写错（如写成 C 盘）会导致桥在启动时把导入错误缓存住，后续所有调用都连不上。

```bat
REM 方式 A（推荐，不动你正在用的 GUI ANSA）
D:\ansa-tcp-bridge\start_listener_only.bat

REM 方式 B（手动，等价）
"D:\Program Files (x86)\BETA_CAE_Systems\ansa_v25.1.4\ansa64.bat" -nolauncher -listenport 9999 -foregr -b
```

启动后 ANSA **没有 GUI 窗口**（这是对的）。它只会开一个被最小化到任务栏的**控制台窗口**，
最后一行通常是 `Code generation completed.`，然后就**安静地等命令**——这是健康状态，不是卡死，**别关它**。

确认端口已起：

```bat
netstat -an | findstr ":9999"
REM 应看到  TCP  127.0.0.1:9999  LISTENING
```

### 步骤 2 — 启动 MCP 桥

```bat
D:\ansa-tcp-bridge\run_mcp.bat
```

`run_mcp.bat` 内部等价于（注意 `ANSA_SCRIPTS_PATH` 是 D 盘）：

```bat
set "ANSA_SCRIPTS_PATH=D:\Program Files (x86)\BETA_CAE_Systems\ansa_v25.1.4\scripts"
set "ANSA_PORT=9999"
set "PYTHONPATH=D:\ansa-tcp-bridge"
"C:\Users\Admin\.workbuddy\binaries\python\envs\ansa-tcp\Scripts\python.exe" -m mcp_server.server
```

可用 CLI 参数（`mcp_server.server`）：

| 参数 | 环境变量 | 默认 | 说明 |
|---|---|---|---|
| `--ansa-scripts` | `ANSA_SCRIPTS_PATH` | （必填）ANSA scripts 目录 | |
| `--host` | `ANSA_HOST` | localhost | ANSA 主机 |
| `--port` | `ANSA_PORT` | 9999 | ANSA 端口 |
| `--transport` | `MCP_TRANSPORT` | stdio | `stdio` 或 `sse` |
| `--sse-port` | `MCP_SSE_PORT` | 8000 | SSE HTTP 端口 |

### 步骤 3 — 在客户端里调用

WorkBuddy 侧把 `ansa-tcp` 加进 MCP 配置（见第 5 节），然后直接调用 `ping_ansa`
验证连通性即可。

---

## 4. 启动 listener 的三种方式（含注意事项）

| 脚本 / 命令 | 行为 | 适用场景 |
|---|---|---|
| `ansa_listener.bat` | 先 `taskkill /F /T /IM ansa_win64.exe` 杀掉**所有** ANSA，再起 listener | ⚠️ 会误杀你正在用的 GUI ANSA，**不要**在有 GUI ANSA 时跑 |
| `start_listener_only.bat` | **只**起 listener，不杀任何已有 ANSA | ✅ 推荐：你开着 GUI ANSA 也想另起一个 listener 时 |
| 手动命令 | `ansa64.bat -nolauncher -listenport 9999 -foregr -b` | 想自己控制参数时 |

可选：给 `ansa_listener.bat` 传一个模型路径作参数，启动时自动打开
（如 `ansa_listener.bat "J:\path\to\model.ansa"`）。

停止 listener：`taskkill /F /IM ansa_win64.exe`

---

## 5. WorkBuddy MCP 客户端配置

编辑 `C:\Users\Admin\.workbuddy\mcp.json`，加入：

```json
{
  "mcpServers": {
    "ansa-tcp": {
      "command": "C:\\Users\\Admin\\.workbuddy\\binaries\\python\\envs\\ansa-tcp\\Scripts\\python.exe",
      "args": ["-m", "mcp_server.server"],
      "env": {
        "PYTHONPATH": "D:\\ansa-tcp-bridge",
        "ANSA_SCRIPTS_PATH": "D:\\Program Files (x86)\\BETA_CAE_Systems\\ansa_v25.1.4\\scripts",
        "ANSA_PORT": "9999"
      }
    }
  }
}
```

> 注意：WorkBuddy 客户端**不会**自动重启已退出的服务进程。若 listener 崩了，
> 需在客户端里"信任/重连"该连接器，或手动重启 listener 再确认 9999 端口恢复。

---

## 6. 两种调用方式

### 方式 A — 通过 MCP 工具（49 个，见第 7 节）

客户端直接调 `ping_ansa` / `open_model` / `mesh_shells` / `apply_connectors` 等。
好处是结构化、可被 AI 直接编排；缺点是工具集是固定的子集。

### 方式 B — 直接 Python 桥（call.py 模式，最强大）

绕过 MCP，自己写一段 Python，用 `bridge_client.AnsaBridge` 把**任意 ANSA 脚本**发到
ANSA 执行。这样可以调用 MCP 工具没有覆盖的 API（如 `connections.ReadConnections`、
`connections.RealizeConnections`、`base.GetEntityCardValues` 等），做复杂批量操作。

最小模板（`call.py`）：

```python
import sys, os
os.environ["ANSA_SCRIPTS_PATH"] = r"D:\Program Files (x86)\BETA_CAE_Systems\ansa_v25.1.4\scripts"
sys.path.insert(0, r"D:\ansa-tcp-bridge")
from mcp_server.bridge_client import AnsaBridge

bridge = AnsaBridge(host="localhost", port=9999)

# 要发给 ANSA 执行的脚本：必须定义 def main(): 并返回一个 dict
script = r'''
def main():
    import ansa
    from ansa import base
    faces = base.CollectEntities(0, None, "FACE", False)
    return {"n_faces": str(len(faces)), "ok": "true"}
'''

ret = bridge.run_script(script)   # 执行
print(ret)
```

运行：`ansa-tcp\Scripts\python.exe call.py`

要点：
- 发给 ANSA 的脚本里**函数名必须是 `main`**（除非你传 `function_name=`），
  且必须 `return` 一个 dict。
- 见下方"坑②"：返回 dict 的**值必须是字符串**，否则桥会报 `unsupported` 返回类型。
- 示例批量脚本见 `run_midsurface.py`（批量抽取中面）。

---

## 7. 工具清单（49 个）

**会话与文件 I/O（9）**
`ping_ansa` `open_model` `new_model` `save_model` `save_model_as`
`export_nastran` `export_lsdyna` `export_step` `run_python_script_in_ansa`

**实体查询与编辑（18）**
`count_entities` `list_entities` `get_entity` `set_entity_fields`
`create_entity` `delete_entities` `search_entities_by_name`
`get_bounding_box` `get_node_coordinates` `change_element_type`
`create_part` `create_set` `add_to_set` `get_model_summary`
`list_model_includes` `calc_element_mass` `calc_shell_area`
`calc_solid_volume`

**质量检查（9）**
`check_intersections` `check_penetrations` `check_free_nodes`
`run_quality_check` `count_failed_elements` `check_geometry`
`check_sharp_edges` `check_rigid_dependencies` `calc_mesh_quality`

**网格（5）**
`mesh_shells` `mesh_volume` `set_shell_mesh_params` `delete_mesh` `run_batch_mesh`

**连接（3）**
`apply_connectors` `check_connections` `list_connectors`
（点焊 / 螺栓 / 铆接 / 缝焊）

**视口可见性（5）**
`show_only` `show_also` `hide` `near` `neighb`

---

## 8. 踩坑与排错（实战经验，重点看）

| # | 现象 | 根因 / 解决 |
|---|---|---|
| **①** | 桥能启动但所有调用连不上，ANSA 进程日志报导入 `AnsaProcessModule` 失败 | `ANSA_SCRIPTS_PATH` 指向了**不存在的路径**（本机写成 C 盘 `C:\Program Files (x86)\BETA_CAE_Systems\...`，但 ANSA 装在 **D 盘**）。修正为 D 盘路径并**重启服务进程**即可（启动时的导入错误会被缓存）。 |
| **②** | 调用返回 `script_execution_details: 1` / `unsupported` 返回类型 | 你发给 ANSA 的脚本 `main()` 返回的 dict 里混入了**非字符串值**（int / tuple / list）。IAP 要求 `dict[str, str]`，在 ANSA 端用 `{k: str(v) for k,v in result.items()}` 包一遍即可。 |
| **③** | 脚本报 `script_execution_details: 0x03`（`script_not_loaded`） | 实体类型不能写 `constants.FACE`，ANSA 25 的 `ansa.constants` 没有实体类型属性。必须传**字符串**：`base.CollectEntities(deck, None, "FACE", False)`。另：`from ansa import ansa_class` 也会触发此错。 |
| **④** | `base.GetEntityCount` / `base.New` 不存在 | ANSA 25 已无这两个函数。计数用 `len(base.CollectEntities(...))`，清空库用 `base.Clear()`。 |
| **⑤** | listener 进程突然消失，9999 端口关闭 | ANSA listener 发生**访问违例**（野指针 / use-after-free），由 ANSA 自带 Breakpad 写 minidump 后退出。本机实测诱因：在大量**未成功 realize 的连接**上反复 `GroupConnectionsByConnectivity` / 读 `connectivity` 字段，把连接子系统内部状态拖到不一致。→ 先修连接连通性（补第二层板 / 修正缺失的 Part 引用）再查询；重划前先备份、分批（先 2 面 smoke test 再全量）。 |
| **⑥** | listener 崩溃后 MCP 工具一直 `Not connected` | MCP 客户端不会自动重启已退出的服务进程。需手动重开 listener 并确认 `netstat` 看到 9999 监听，再到客户端重连。 |
| **⑦** | 保存后残留 `.lock.<模型名>#.ansa#` 锁文件 | 进程在 `Save Completed` 之后异常退出，锁没清掉 → 那个 `.ansa` 文件可能被**截断/不完整**。用前务必在 ANSA 里打开验证一次并重新存盘清锁。 |

诊断命令速查：

```bat
netstat -an | findstr ":9999"     REM 看端口是否 LISTENING
tasklist | findstr "ansa_win64"   REM 看 ANSA 进程是否存活
```

---

## 9. 目录结构

```
D:\ansa-tcp-bridge\
├── README.md                 # 本文件
├── ansa_listener.bat         # 标准 listener 启动器（会先杀所有 ANSA！）
├── start_listener_only.bat   # 只起 listener，不杀已有 ANSA（推荐）
├── run_mcp.bat               # 启动 MCP 桥
├── run_midsurface.py         # 示例：批量抽取中面脚本
├── pyproject.toml            # 包定义（mcp[cli]>=1.0）
├── mcp_server\
│   ├── server.py             # FastMCP 入口，注册 49 个工具
│   ├── bridge_client.py      # AnsaBridge：IAP 连接 + run_script / run_file
│   ├── ansi_scripts.py       # 生成发给 ANSA 的 Python 片段
│   └── tools\                # 各类工具实现
│       ├── session.py  entities.py  checks.py
│       ├── mesh.py  connections.py  visibility.py
├── output\                   # 运行产物（生成的 .ansa 等）
└── diag_out\                 # 诊断输出
```

---

## 10. 典型工作流示例（本仓库实战）

以"打开模型 → 载入 3mm 网格标准 → 重划网格 → 导入连接 XML → 生成 FE 表示"为例：

1. `open_model` 打开 `initial.ansa`；
2. `set_shell_mesh_params` + `mesh_shells` 载入 `mesh_ftrd_3mm.ansa_mpar` / `mesh_3mm.ansa_qual` 并重划到 3mm；
3. 方式 B（`run_python_script_in_ansa` 或 call.py）调用 `connections.ReadConnections("XML", path)` 导入 `connections_to_insert.xml`；
4. 同样用方式 B 调用 `connections.RealizeConnections(...)` 生成 FE 表示；
5. 对未成功的连接先修连通性再二次 realize；
6. `save_model_as` 落盘（注意坑⑦，保存后确认无 `.lock` 残留）。

> 提示：ANSA 25 的 FE 点焊模式常为 `SpotweldPoint_RBE3-HEXA-RBE3`，且 `DoNotMove='y'`
> 时投影失败不允许微移，落在部件交界带（缺第二层板 / 引用了不存在的 Part）的连接会
> 无法生成 FE 表示——这是**数据固有边界问题**，与重划网格无关。

---

## License

MIT。ANSA 是 BETA CAE Systems International AG 的商业产品；本项目为独立的社区工具，
与 BETA CAE Systems 无关、未获其背书。
