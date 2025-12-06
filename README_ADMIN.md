# 以管理员权限运行 Python 脚本

## 方法1：使用批处理文件（推荐，最简单）

### 步骤：
1. 找到项目根目录下的 `run_as_admin.bat` 文件
2. **右键点击** `run_as_admin.bat`
3. 选择 **"以管理员身份运行"**
4. 脚本会自动激活虚拟环境并运行测试

### 优点：
- ✅ 最简单，一键运行
- ✅ 自动检查管理员权限
- ✅ 自动激活虚拟环境

---

## 方法2：使用 PowerShell 脚本

### 步骤：
1. 找到项目根目录下的 `run_as_admin.ps1` 文件
2. **右键点击** `run_as_admin.ps1`
3. 选择 **"使用 PowerShell 运行"**
4. 如果提示权限，点击"是"

### 优点：
- ✅ 自动请求管理员权限
- ✅ 更强大的脚本功能

---

## 方法3：手动以管理员权限运行终端

### Windows PowerShell：

1. **打开 PowerShell（管理员）**：
   - 按 `Win + X`
   - 选择 **"Windows PowerShell (管理员)"** 或 **"终端 (管理员)"**

2. **切换到项目目录**：
   ```powershell
   cd D:\workspace\yishe-ps
   ```

3. **激活虚拟环境**：
   ```powershell
   .venv\Scripts\Activate.ps1
   ```

4. **运行脚本**：
   ```powershell
   python src\test.py
   ```

### Windows CMD：

1. **打开 CMD（管理员）**：
   - 按 `Win + X`
   - 选择 **"命令提示符 (管理员)"** 或 **"终端 (管理员)"**

2. **切换到项目目录**：
   ```cmd
   cd /d D:\workspace\yishe-ps
   ```

3. **激活虚拟环境**：
   ```cmd
   .venv\Scripts\activate.bat
   ```

4. **运行脚本**：
   ```cmd
   python src\test.py
   ```

---

## 方法4：在代码中自动请求管理员权限（高级）

如果你想让 Python 脚本自动请求管理员权限，可以创建一个启动脚本：

### 创建 `run_with_elevation.py`：

```python
import sys
import ctypes
import os

def is_admin():
    """检查是否以管理员权限运行"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_as_admin():
    """以管理员权限重新运行脚本"""
    if is_admin():
        # 如果已经是管理员，直接运行主脚本
        import subprocess
        script_path = os.path.join(os.path.dirname(__file__), 'src', 'test.py')
        subprocess.run([sys.executable, script_path])
    else:
        # 请求管理员权限
        script_path = os.path.join(os.path.dirname(__file__), 'src', 'test.py')
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, script_path, None, 1
        )

if __name__ == "__main__":
    run_as_admin()
```

然后运行：
```bash
python run_with_elevation.py
```

---

## 验证是否以管理员权限运行

运行脚本后，你会看到权限检查输出：

```
======================================================================
🔐 权限检查
======================================================================
✅ 导出目录权限: 正常
✅ Photoshop 权限: 正常
======================================================================
```

如果看到这些 ✅，说明权限正常。

---

## 常见问题

### Q: 为什么需要管理员权限？
A: 某些操作（如保存 PSD 文件、写入某些目录）可能需要管理员权限，特别是当：
- PSD 文件在受保护的系统目录
- 导出目录需要管理员权限
- Photoshop 需要访问某些系统资源

### Q: 可以不用管理员权限吗？
A: 可以，但需要确保：
- 导出目录有写入权限
- PSD 文件所在目录有读取权限
- 使用用户目录作为导出目录（如 `Documents` 文件夹）

### Q: 如何修改导出目录？
A: 在 `src/test.py` 中修改 `config`：
```python
config = {
    'export_dir': r"C:\Users\你的用户名\Documents\ps_output",  # 使用用户目录
    # ...
}
```

---

## 推荐方法

**最简单**：使用方法1（`run_as_admin.bat`）
- 右键 → 以管理员身份运行 → 完成

**最灵活**：使用方法3（手动打开管理员终端）
- 可以执行任何命令，更灵活

