# Episode

Episode 是一个运行在本地电脑浏览器中的 PDF 编辑与 PDF 转图片工具。它使用 Flask 提供本地服务，前端使用原生 HTML/CSS/JavaScript 实现页面预览、拖拽排序、页面旋转、统一页面大小、输出路径定位和 PDF 转图片等操作。

项目默认只在本机 `127.0.0.1` 运行，不会主动把你的 PDF、图片或导出文件上传到外部服务器。

## 从 GitHub 下载并运行

下面的步骤适合第一次在另一台 Windows 电脑上运行 Episode。

### 1. 安装 Python

先安装 Python 3.10 或更高版本：

- 下载地址：https://www.python.org/downloads/
- 安装时建议勾选 `Add python.exe to PATH`

安装完成后打开 PowerShell，检查 Python 是否可用：

```powershell
python --version
```

### 2. 下载项目

如果电脑已经安装 Git，可以执行：

```powershell
git clone https://github.com/LeuroPrince/Episode.git
cd Episode
```

如果没有安装 Git，也可以在 GitHub 仓库页面点击：

```text
Code -> Download ZIP
```

下载后解压 ZIP，并进入解压后的 Episode 文件夹。

### 3. 安装依赖

在项目文件夹中运行：

```powershell
python -m pip install -r requirements.txt
```

依赖包括：

- Flask：提供本地网页服务
- PyMuPDF：读取、渲染、编辑和导出 PDF
- Pillow：处理图片文件
- Werkzeug：处理上传文件名与 Web 工具函数

### 4. 启动 Episode

推荐在 Windows 上双击：

```text
launch_episode.cmd
```

脚本会启动 Flask 服务并打开浏览器。为避免杀毒软件误判，启动脚本不会隐藏后台进程，也不会自动监控文件或静默安装依赖。它会打开一个可见的命令行窗口运行本地服务，关闭该窗口即可停止 Episode。

也可以打开本地离线启动页：

```text
Episode.html
```

这个 HTML 文件不依赖互联网，会检测本机 `127.0.0.1:7865` 服务是否可访问，并提供进入 Episode 的按钮。因为浏览器安全限制，纯 HTML 文件不能自动启动本地 Python 服务；如果检测到服务未启动，请先双击 `launch_episode.cmd`。

也可以手动启动：

```powershell
python app.py
```

然后在浏览器打开：

```text
http://127.0.0.1:7865
```

## 主要功能

### PDF 编辑

Episode 可以把多个 PDF 和图片整理成一个新的 PDF 文件。

支持的操作包括：

- 导入一个或多个 PDF 文件。
- 导入 PNG、JPG、JPEG、BMP、TIFF、WEBP 等图片，并作为 PDF 页面加入项目。
- 将多个 PDF 和图片合并导出为一个新的 PDF。
- 拖拽页面卡片调整页面顺序。
- 一次选择多个页面，并把选中的页面作为一组拖拽移动。
- 删除不需要的页面。
- 在每一页下方单独进行左转或右转。
- 导出时尽量保留来源 PDF 的书签结构，并把书签页码映射到新的页面顺序。

### 预览区

中间的页面预览区会显示当前项目里的所有页面缩略图。

预览区支持：

- 上传 PDF 或图片后自动生成页面缩略图。
- 页面左转或右转后，缩略图立即按照新的方向刷新。
- 使用统一页面大小后，预览区会按统一后的页面画布重新显示。
- 多选页面时，被选中的页面会高亮显示。
- 拖拽排序时，页面会插入到鼠标选中的两个页面之间，而不是只能移动到每行首尾。

### 页面朝向调整

每个页面卡片下方都有独立的方向按钮：

- `左转`：将当前页面逆时针旋转 90 度。
- `右转`：将当前页面顺时针旋转 90 度。

这些操作只影响对应页面，不会批量修改其他页面。

### 一键统一页面大小

`一键统一页面大小` 位于 PDF 编辑区域的页面工具中。

该功能用于把当前项目里的所有页面放入同一种页面画布：

- 自动选择当前项目中最常见的页面尺寸作为统一尺寸。
- 导出 PDF 时，所有页面都会使用统一画布。
- 页面内容会等比例缩放并居中显示。
- 不会裁切页面内容。
- 操作完成后会显示目标页面尺寸提示。
- 预览区会同步刷新，直接看到统一尺寸后的显示效果。

### 输出路径区

保存 PDF 后，左侧操作区会显示输出入口：

- `下载已保存文件`：通过浏览器下载刚导出的 PDF。
- `定位到输出 PDF`：调用 Windows 文件资源管理器，并尽量直接选中导出的 PDF 文件。

导出的文件默认保存在：

```text
workspace\exports
```

在本地开发目录中，对应路径通常是：

```text
Episode\workspace\exports
```

### PDF 转图片

PDF 转图片功能位于独立的工具区域，和 PDF 编辑区域分开。

支持的操作包括：

- 选择一个 PDF 文件。
- 选择后在工具内显示 PDF 预览。
- 点击 `转换为 PNG` 后，把 PDF 每一页导出为 PNG 图片。
- 转换后的图片会保存到 `workspace\exports` 下的独立文件夹中。
- 转换完成后可以点击路径按钮打开图片输出文件夹。

### 图片合并 PDF

图片合并 PDF 功能位于转换工具区域中，用于把多张图片直接保存为一个 PDF。

支持的操作包括：

- 一次选择多张图片文件。
- 按当前选择顺序生成 PDF 页面。
- 可在保存前填写合并后的 PDF 文件名。
- 点击 `合并并保存 PDF` 后，文件会保存到 `workspace\exports`。
- 合并完成后可以下载 PDF，也可以点击路径按钮在 Windows 文件资源管理器中定位到输出文件。

### 历史项目侧边栏

右侧历史项目栏会显示当前服务运行期间创建或编辑过的项目。

可以用于：

- 点击历史项目恢复到当前工作区。
- 查看项目名称、页数和最后更新时间。
- 在处理多个 PDF 任务时快速切换上下文。

注意：当前历史记录保存在运行内存中，重启服务后会重新开始。

## 项目结构

```text
Episode/
  Episode.html            本地离线启动页
  app.py                  Flask 后端服务
  launch_episode.cmd      Windows 双击启动入口
  launch_pdfeditor.cmd    旧名称兼容入口
  requirements.txt        Python 依赖
  templates/
    index.html            主页面模板
  static/
    app.js                前端交互逻辑
    styles.css            页面样式
  workspace/
    uploads/              运行时上传文件目录
    exports/              运行时导出文件目录
```

## 常见问题

### 浏览器打不开 `http://127.0.0.1:7865`

可以先确认服务是否已经启动：

```powershell
python app.py
```

如果提示端口被占用，说明可能已有一个 Episode 服务正在运行。可以直接刷新浏览器，或关闭旧的 Python 进程后重新启动。

### 安装依赖失败

可以先升级 pip：

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 点击输出路径只打开文件夹，没有选中文件

Episode 会使用 Windows 的 `explorer.exe /n,/select` 请求选中具体文件。少数系统状态下资源管理器可能复用已有窗口，但导出的 PDF 仍然位于 `workspace\exports` 中。

## 注意事项

- Episode 是本地工具，不会主动上传文件到外部服务器。
- `workspace` 是本地运行目录，导入的 PDF、图片、导出的 PDF 和转换后的图片都只保存在本地电脑。
- GitHub 仓库只公开工具源码；`.gitignore` 会忽略 `workspace` 下的运行文件，只保留 `uploads` 和 `exports` 两个空目录占位文件。
- PDF 编辑、统一页面大小、PDF 转图片和图片合并 PDF 都会生成新文件，不会自动覆盖原始上传文件。
- 处理大量高清 PDF 或图片时，转换和预览可能需要等待一段时间。
