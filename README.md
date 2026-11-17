# Script to animated PPT

给 Codex 一份讲稿，制作具有原生点击入场动画的 PPTX。

包括讲稿拆分、视觉与完整素材设计、点击节点安排、无第三方 Python 依赖的动画注入工具，以及实际播放验收要求。风格按每次任务决定，不附带私人讲稿或特定角色素材。

## 安装

把 `skills/script-to-animated-ppt` 整个目录复制到 Codex 的 skills 目录（通常是 `~/.codex/skills/`）。重新打开会话后可用 `$script-to-animated-ppt` 调用。也可用 Codex skill-installer 从本仓库的该目录安装。

可以把这句话直接发给 Codex：

> 请安装 https://github.com/Leosadfsd/animated-ppt-skill 仓库里的 skills/script-to-animated-ppt，安装后告诉我如何调用。

## 使用

> 使用 $script-to-animated-ppt，按附件讲稿制作动画 PPT。讲述约 5 分钟，共 6 页，风格参考附件，在 WPS 放映，一次点击推进一个讲述节点。保留讲稿结尾。

需要 Codex 能读讲稿、创作 PPTX 并执行 Python 3.10+。可使用 Codex 环境中的 Presentations 能力完成布局与渲染。动画工具只用 Python 标准库，不依赖本项目原机器路径。只有聊天能力、不能执行文件工具的 AI 无法独立运行此工作流。

动画生成和真实播放是两层验证。缺少本地 WPS/PowerPoint 控制时，AI 必须明确标注播放尚未验证，不能把 XML 检查当成实播通过。

## 本地开发

```sh
python -m unittest discover -s tests -v
python skills/script-to-animated-ppt/scripts/animate.py --help
```

示例仅用原创通用讲稿，不包含原项目素材。发布前运行测试并在目标软件检查实际播放。完整视觉设计仍由 Codex 执行，本工具不会通过规则自动理解任意讲稿。

## 示例与复现

- [示例讲稿](examples/walking/manuscript.md)
- [分镜和点击指南](examples/walking/storyboard.md)
- [可播放示例 PPTX](examples/walking/output/Walking_Animated_Demo.pptx)
- [播放验证范围](examples/walking/validation.md)

在有 `@oai/artifact-tool` 的 Codex 环境中，设置 `RUNTIME_NODE_MODULES` 为该环境提供的 node_modules 路径，再运行：

```sh
node examples/walking/build.mjs
python skills/script-to-animated-ppt/scripts/animate.py inspect examples/walking/build/draft.pptx
python skills/script-to-animated-ppt/scripts/animate.py apply examples/walking/build/draft.pptx examples/walking/build/motion.json examples/walking/build/animated.pptx
```

不同环境的 Node/Python 可执行文件位置不同，请使用 Codex 当前提供的运行环境。已有示例无需重建即可打开。复现生成的 build 目录不入库。

![示例第一页](examples/walking/previews/slide-1.png)
