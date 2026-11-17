# Script to animated PPT

给 Codex 一份讲稿，制作具有原生点击入场动画的 PPTX。

包括讲稿拆分、视觉与完整素材设计、点击节点安排、无第三方 Python 依赖的动画注入工具，以及实际播放验收要求。风格按每次任务决定，不附带私人讲稿或特定角色素材。

v0.2 加入统一页面配置、运行环境与字体检测、原生组合自动创建、每次点击后的静态预览和讲稿提示。制作新文本/图片演示时，AI 只需设计 `scene.json`，无需为每份讲稿重写页面生成脚本。

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
node --test tests/preview.test.mjs
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

## 配置驱动的拼贴示例（v0.2）

[页面配置](examples/collage/scene.json) · [原生组合动画 PPT](examples/collage/output/Walking_Collage_Animated_v02.pptx) · [点击与讲稿指南](examples/collage/preview/click-guide.md) · [验证范围](examples/collage/validation.md)

克隆或下载本仓库后，用浏览器打开 `examples/collage/preview/index.html`，可以逐步查看每次点击后的画面和对应讲稿。GitHub 文件页只展示 HTML 源码，需要下载到本地打开。预览是静态累计状态，不代表真实飞入过程或软件兼容性。

在当前 Codex 提供的 Node/Python 环境中，设置 `RUNTIME_NODE` 和 `RUNTIME_NODE_MODULES` 后：

```sh
python skills/script-to-animated-ppt/scripts/scene.py doctor --font "Microsoft YaHei"
python skills/script-to-animated-ppt/scripts/scene.py validate examples/collage/scene.json
python skills/script-to-animated-ppt/scripts/scene.py build examples/collage/scene.json examples/collage/build/my-revision
```

输出目录必须是新路径。命令生成可编辑页面、原生动画组、PPTX、离线点击预览和讲稿指南。修改文字、素材、位置或点击顺序后，改配置并生成新版本即可。工具当前支持文本/PNG/JPEG 布局；表格、图表、复杂模板仍由 AI 使用相应创作工具处理。

三个新素材由图像生成工具创作，人物为虚构插画，街景为合成示意图，均有[生成提示记录](examples/collage/assets/sources.md)。公开示例不含私人讲稿、原项目人物图或账号数据。

![拼贴示例第一页](examples/collage/preview/previews/p1-final.png)
