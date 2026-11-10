# 验证脚本
最主要的可移植自动化回归是Maven test中的15个测试，不需要Python。
verify-http.py为本次真实HTTP检查脚本整理版，需要Python3标准库；在项目根目录、服务已启动时运行。使用新编号添加数据，结果保存docs/evidence，不清空数据库。
verify-browser.py需要另装Python playwright和本机Edge（默认Windows常见路径）；用于复现浏览器点击流程，非启动必需依赖。运行前先读脚本，路径不同需改Edge路径。截图会覆盖该目录的同名截图，应自行备份已有证据。
构建脚本在普通Windows终端/IDEA使用；首次下载Maven与依赖需联网。预打包release不需要下载依赖。此次沙箱验证采用临时盘符映射修复Java路径解析，未要求用户修改系统权限。
