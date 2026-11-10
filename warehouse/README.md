# 仓流：智慧仓储与物流协同系统

软件工程选题 4 · 第一版学习与修改底稿。Java 后端、中文网页、文件型关系数据库、真实事务与事件处理。没有登录和权限，默认仅监听本机，不应直接暴露到互联网。

## 第一次运行（先演示，再学代码）
1. 在资源管理器打开这个 `warehouse` 文件夹，不要只复制某一个 Java 文件。
2. 双击 `启动演示.cmd`。窗口出现 `Started WarehouseApplication` 后表示启动成功。
3. 浏览器打开 http://127.0.0.1:8080 。看到“仓库工作台”和“仓库已连接”表示前后端连通。
4. 关闭服务时在运行窗口按 Ctrl+C。再次启动仍使用 `data/warehouse.mv.db`，库存不会丢失。
5. 若 8080 被占用，先关闭以前的启动窗口；或在本文件夹终端输入 `java -jar release/warehouse-1.0.0.jar --server.port=8081`，浏览器改为 8081。

打包的 release 是当前源码经过测试的可运行文件，不需要安装 MySQL、Node 或 Maven。需要 JDK 17～25，本次实际使用 25.0.1。不要双击 JAR；使用启动脚本才能看到错误日志。

## 演示路线
商品资料：新增 KB001 / 键盘 / 个 → 入库与库存：选择键盘、A01、100 → 确认库存 100 → 出库订单：键盘/A01/20 → 库存仍为100 → 点击确认出库 → 库存80、订单已出库 → 物流跟踪：查看轨迹、模拟运输中、模拟已签收。

也可在服务启动后运行 `演示数据.cmd`，自动执行完整流程并打印检查结果。每次使用不同商品编号，因此不会覆盖已有数据；它会新增测试数据，不用于清空数据库。页面刷新后能看到对应记录。异常测试可以再创建数量81的同货位订单，确认时应提示库存不足。

## 用 IDEA 修改
1. 打开 IDEA，选择 Open，选择本项目 `pom.xml`，按 Maven 项目打开并等待加载。
2. Project SDK 选择已安装的 JDK 25，Maven 运行 JDK 也选该 JDK。源码使用 Java 17 语法，便于组员使用17/21/25，但17、21尚未在本机复测。
3. 展开 `src/main/java/edu/team/warehouse/WarehouseApplication.java`，点击 main 方法旁的绿色三角运行。先停掉启动脚本运行的服务，避免端口冲突。
4. 修改网页在 `src/main/resources/static/`；修改后重新运行应用或重新打包。直接双击 index.html 不能正确调用接口。
5. 修改源码后，终端运行 `构建测试.cmd`。首次需要联网，脚本下载固定版本 Maven 到 `.tools`，运行测试并更新 release 中的 JAR。出现 BUILD SUCCESS 才使用新版本。
6. IDEA 的 Maven 面板也可执行 Lifecycle → test / package；测试数据在内存中，与演示数据库分离。

## 零基础阅读顺序
先看 `docs/01-需求与规划.md` 和页面 → `api/Requests.java`（请求数据）→ `api/ApiController.java`（网址对应方法）→ `catalog/CatalogService.java`（最简单的新增商品）→ `inventory/InventoryService.java`（入库加库存）→ `orders/OrderService.java`（出库规则与事务）→ `events/EventHandlers.java` → `logistics/LogisticsService.java` → `src/test/java/edu/team/warehouse/WarehouseTests.java`。
以上 Java 路径相对于 `src/main/java/edu/team/warehouse/`。

概念：接口是网页与后端交换数据的约定；数据库是保存商品、库存等表格的地方；事务把一组修改作为整体提交或撤销；Git记录源文件修改，不能代替数据库备份；IDEA是编辑和运行代码的软件。

## 交付导航
- `docs/01-需求与规划.md`：角色、故事地图、迭代、用例、名词短语及CRC。
- `docs/02-设计与数据库.md`：架构比较、事件与一致性、设计类、数据库字典。
- `docs/03-接口与实现.md`：接口、原型、核心代码讲解。
- `docs/04-测试报告.md`、`docs/evidence/`：测试设计、实际结果与机器原始报告。
- `docs/05-团队协作与报告模板.md`：五人建议分工、Git、互评和总结模板。
- `docs/diagrams/`：分模块用例、活动、领域、包、部署、鲁邦与序列图的 PlantUML 可编辑源文件。

尚未实现：拣选任务与盘点调整、登录权限、多仓库、真实快递/物联网、独立消息队列、云部署。H2 是关系数据库，但不是 MySQL；若老师要求指定 MySQL，应先统一团队环境，再修改数据源与建表语法并完整回归，不能宣称已兼容 MySQL。

指导书及两张截图已核对。所有内容是 AI 辅助初稿，个人总结、互评、真实组员提交和人工审查不能由本项目代填。
