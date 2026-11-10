# 小组协作从这里开始

## 先验收本次导入
由另一位成员查看合并请求的Files changed，核对项目目录和说明，并在自己电脑运行一次完整流程。检查通过后再合并到main。尚未复测就写“待验证”，不要照抄已有结果作为自己的测试记录。

## 每个人都做的事
1. 用自己的GitHub账号接受仓库协作邀请，Git使用本人真实姓名和邮箱。
2. 在IDEA选择从版本控制获取项目（Clone），地址为https://github.com/hoking-T/team.git；打开里面的warehouse/pom.xml。
3. 分工前先看warehouse/README.md，每人试运行，记录自己实际遇到的问题。
4. 在GitHub Issues新建一个有明确验收标准的任务，认领后再从最新main创建自己的分支。
5. 修改、验证、Commit、Push，再发起Pull request。提交说明写具体改动，不按数量凑记录。
6. 请另一名组员检查，按意见修订并重新验证，再合并。

## 建议认领表（还未指派真实成员）
|角色|入口|建议任务|验收方式|
|---|---|---|---|
|后端A|warehouse/src/main/java/edu/team/warehouse/catalog|商品名称查询|正常匹配、空条件、无结果；补测试|
|后端B|warehouse/src/main/java/edu/team/warehouse/orders|复核库存不足、重复及并发出库|独立复测，缺陷如实登记并修复|
|后端C|warehouse/src/main/java/edu/team/warehouse/events及logistics|复核物流状态与事件失败回滚|补遗漏测试或完善协议说明|
|前端|warehouse/src/main/resources/static|从使用体验发现并改进表单或提示|截图对比，实际操作验证|
|测试与报告|warehouse/src/test及warehouse/docs|核对模型与代码、组织人工验收|记录真实版本、日期、执行人和结果|

## 每个任务填写这些内容
问题或需求：……
负责人：真实姓名/账号
具体修改：……
验收步骤及期望结果：……
实际结果、截图、commit或PR链接：……
检查人及意见：……

## 注意
不提交data、target、.tools和密码；现有.gitignore已排除本机数据及主要缓存。修改源码后须重新构建测试，旧release中的JAR不会自动更新。不要伪造过去的迭代、测试或其他成员身份。报告中的个人总结200—400字、互评和AI使用记录仍需大家根据真实经历填写。
