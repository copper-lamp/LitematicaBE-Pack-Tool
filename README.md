# LitematicaBE Pack Tool

从 Java 版原版资源包一键生成基岩版 LitematicaBE 投影材质包。

## 简介

LitematicaBE Pack Tool 是一款带有简洁 GUI 的资源包生成工具，用于将 Java 版 Minecraft 原版资源包中的方块贴图转换为基岩版 LitematicaBE 插件所需的粒子材质包。

生成的材质包包含所有原版方块的 *正常* 与 *错误* 两种投影粒子，支持在基岩版中使用 `/particle` 指令调用，用于建筑投影预览和方块放置校验。

## 功能特点

- 自动裁剪多面贴图（如草方块侧面），只保留顶部一面
- 支持分辨率缩放（1x / 0.5x / 0.25x）
- 用户可自定义粒子持续时间、粒子大小
- 为每个方块生成 normal（白色）和 error（红色）两种粒子
- 生成符合基岩版格式的 `manifest.json`
- 简洁直观的 GUI 界面，一键生成为 `.mcpack` 文件

## 环境要求

- Python 3.7+
- Pillow（Python 图像处理库）

## 快速开始

```bash
# 1. 安装依赖
pip install Pillow

# 2. 运行工具
python generate_pack.py
```

## 使用说明

1. **提取 Java 版原版纹理**  
   使用压缩软件打开 `.minecraft/versions/<版本>/<版本>.jar`，解压其中的 `assets/minecraft/textures` 目录。

2. **运行工具**  
   执行 `python generate_pack.py` 打开 GUI 界面。

3. **配置参数**

   | 参数 | 说明 | 默认值 |
   |------|------|--------|
   | 原始资源目录 | 解压后的 textures 文件夹路径 | — |
   | 粒子持续时间 | 粒子存活时间（秒），需与插件 config.json 中的 `particleRespawn.lifetime` 保持一致 | 45 |
   | 分辨率缩放 | 贴图缩放比例 | 1x |
   | 粒子大小 | 粒子渲染尺寸 | 1.00 |

4. **生成材质包**  
   点击「生成资源包」按钮，等待完成后即可获得 `.mcpack` 文件。

5. **安装材质包**  
   将生成的 `.mcpack` 文件导入 Minecraft 基岩版。

## 文件结构

```
LitematicaBE_packtool/
├── generate_pack.py      # 主程序
├── pack_icon.png         # 材质包图标
├── README.md
└── textures/             # 示例纹理（仅供测试，正式使用请从 Java 版提取）
    └── block/
        └── *.png
```

## 许可证

本项目基于 MIT 许可证开源。详见 [LICENSE](LICENSE) 文件。

Copyright (c) 2025 LitematicaBE
