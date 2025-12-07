# 自定义模式（Custom Mode）设计文档

## 设计目标
在现有的 `stretch`、`contain`、`cover` 三种模式基础上，增加 `custom` 模式，允许用户精确控制素材图在智能对象中的位置和尺寸。

## 数据结构

```json
{
    "resize_mode": "custom",
    "custom_options": {
        "position": {
            "x": 100,
            "y": 50,
            "unit": "px"
        },
        "size": {
            "width": 800,
            "height": 600,
            "unit": "px",
            "maintain_aspect_ratio": false,
            "aspect_ratio_base": "width"
        }
    }
}
```

## 字段说明

### `custom_options` 对象（必需，当 `resize_mode="custom"` 时）

#### `position` 对象
- **`x`** (float): x 坐标（相对于智能对象左上角）
- **`y`** (float): y 坐标（相对于智能对象左上角）
- **`unit`** (str): 单位，`"px"`（像素，默认）或 `"%"`（百分比，相对于智能对象尺寸）

#### `size` 对象
- **`width`** (float): 宽度
- **`height`** (float): 高度
- **`unit`** (str): 单位，`"px"`（像素，默认）或 `"%"`（百分比，相对于智能对象尺寸）
- **`maintain_aspect_ratio`** (bool, 默认 `false`): 是否保持宽高比
- **`aspect_ratio_base`** (str, 可选): 宽高比基准（仅当 `maintain_aspect_ratio=true` 时必需）
  - `"width"`: 以宽度为基准，高度自适应（超出部分会裁剪）
  - `"height"`: 以高度为基准，宽度自适应（超出部分会裁剪）

## 使用示例

### 示例 1：像素单位，不保持宽高比
```json
{
    "resize_mode": "custom",
    "custom_options": {
        "position": {
            "x": 100,
            "y": 50,
            "unit": "px"
        },
        "size": {
            "width": 800,
            "height": 600,
            "unit": "px",
            "maintain_aspect_ratio": false
        }
    }
}
```

### 示例 2：百分比单位
```json
{
    "resize_mode": "custom",
    "custom_options": {
        "position": {
            "x": 10,
            "y": 10,
            "unit": "%"
        },
        "size": {
            "width": 80,
            "height": 80,
            "unit": "%",
            "maintain_aspect_ratio": false
        }
    }
}
```

### 示例 3：保持宽高比（宽度基准）
```json
{
    "resize_mode": "custom",
    "custom_options": {
        "position": {
            "x": 0,
            "y": 0,
            "unit": "px"
        },
        "size": {
            "width": 800,
            "height": 600,
            "unit": "px",
            "maintain_aspect_ratio": true,
            "aspect_ratio_base": "width"
        }
    }
}
```
**说明**：使用输入的 `width` 值，根据原始图片宽高比计算 `height`。如果计算出的高度超出智能对象，会裁剪超出部分。

### 示例 4：保持宽高比（高度基准）
```json
{
    "resize_mode": "custom",
    "custom_options": {
        "position": {
            "x": 0,
            "y": 0,
            "unit": "px"
        },
        "size": {
            "width": 800,
            "height": 600,
            "unit": "px",
            "maintain_aspect_ratio": true,
            "aspect_ratio_base": "height"
        }
    }
}
```
**说明**：使用输入的 `height` 值，根据原始图片宽高比计算 `width`。如果计算出的宽度超出智能对象，会裁剪超出部分。

## 验证规则

1. **当 `resize_mode="custom"` 时**：
   - `custom_options` 必须提供
   - `custom_options.position` 必须提供
   - `custom_options.size` 必须提供
   - 当 `maintain_aspect_ratio=true` 时，`aspect_ratio_base` 必须提供

2. **位置和尺寸验证**：
   - `x`, `y`, `width`, `height` 必须 >= 0
   - 百分比值范围：0-100
   - 像素值可以超出智能对象边界（会自动裁剪）

3. **单位验证**：
   - `position.unit` 和 `size.unit` 必须是 `"px"` 或 `"%"`
   - 默认值为 `"px"`

## 与现有模式的对比

| 模式 | 位置控制 | 尺寸控制 | 宽高比 | 适用场景 |
|------|---------|---------|--------|---------|
| `stretch` | 自动（填满） | 自动（智能对象尺寸） | 不保持 | 需要填满，可接受变形 |
| `contain` | 自动（居中） | 自动（保持比例） | 保持 | 完整显示，不变形 |
| `cover` | 自动（居中） | 自动（保持比例） | 保持 | 填满区域，可接受裁剪 |
| `custom` | 手动指定 | 手动指定 | 可选 | 精确控制位置和尺寸 |

## 实现说明

- 百分比计算：相对于智能对象的尺寸（`x`/`width` 相对于宽度，`y`/`height` 相对于高度）
- 超出边界处理：如果素材图超出智能对象边界，会自动裁剪超出部分
- 保持宽高比：通过 `aspect_ratio_base` 参数指定以宽度或高度为基准，另一个维度自动计算
