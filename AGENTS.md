# AGENTS.md — 项目约定

> 本文件供所有 agent 工具（Trae / Cursor / Claude Code / Copilot 等）自动识别。
> Trae 下另有自动加载的副本：`.trae/rules/project-rules.md`，两份内容保持一致。

## 学习总结写作规约

1. **位置**：每章的学习总结写在对应章节目录下，即 `Chapter-XX/README.md`
2. **根 README 定位**：根目录 `README.md` 只做两件事——项目说明 + 各章学习总结的路径索引引导，不展开任何章节正文
3. **内容风格**：总结尽量精简，把重点讲明白即可，不堆砌、不照搬全书

## 执行流程（接到学习总结任务时）

1. 读取对应章节的学习资料
2. 结合 `Chapter-XX/` 目录下的练习代码
3. 写入或更新 `Chapter-XX/README.md`
4. 在根 `README.md` 的章节索引表中更新该行的链接与状态
5. 不要把章节正文写进根 `README.md`
