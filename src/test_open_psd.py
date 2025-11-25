from photoshop import Session

with Session() as session:
    app = session.app
    doc = app.open("D:/workspace/yishe-ps/examples/test.psd")
    
    # 1. 打印文档基本信息
    print("=" * 60)
    print("文档基本信息")
    print("=" * 60)
    print(f"文档名称: {doc.name}")
    print(f"文档尺寸: {doc.width} x {doc.height} 像素")
    print(f"分辨率: {doc.resolution} DPI")
    print(f"颜色模式: {doc.mode}")
    print(f"图层总数: {len(doc.layers)}")
    print()
    
    # 2. 列出所有图层
    print("=" * 60)
    print("图层列表")
    print("=" * 60)
    if doc.layers:
        for i, layer in enumerate(doc.layers, 1):
            layer_type = type(layer).__name__
            visible = "可见" if layer.visible else "隐藏"
            print(f"{i}. {layer.name} ({layer_type}) - {visible}")
    else:
        print("没有找到图层")
    print()
    
    # 3. 访问图层组（如果有）
    print("=" * 60)
    print("图层组/画板")
    print("=" * 60)
    if hasattr(doc, 'layerSets') and doc.layerSets:
        for i, layer_set in enumerate(doc.layerSets, 1):
            print(f"{i}. {layer_set.name} (包含 {len(layer_set.layers)} 个图层)")
            if layer_set.layers:
                for j, sub_layer in enumerate(layer_set.layers[:3], 1):  # 只显示前3个
                    print(f"   - {sub_layer.name}")
                if len(layer_set.layers) > 3:
                    print(f"   ... 还有 {len(layer_set.layers) - 3} 个图层")
    else:
        print("没有找到图层组")
    print()
    
    # 4. 测试图层操作 - 切换第一个图层的可见性
    print("=" * 60)
    print("测试图层操作")
    print("=" * 60)
    if doc.layers:
        first_layer = doc.layers[0]
        print(f"当前第一个图层: {first_layer.name}")
        print(f"原始可见性: {first_layer.visible}")
        
        # 切换可见性
        first_layer.visible = not first_layer.visible
        print(f"切换后可见性: {first_layer.visible}")
        
        # 恢复原状
        first_layer.visible = not first_layer.visible
        print(f"恢复后可见性: {first_layer.visible}")
        
        # 设置活动图层
        doc.activeLayer = first_layer
        print(f"已设置活动图层为: {doc.activeLayer.name}")
    print()
    
    # 5. 测试文档保存（可选，取消注释以启用）
    # print("=" * 60)
    # print("测试保存文档")
    # print("=" * 60)
    # doc.save()
    # print("文档已保存")
    # print()
    
    print("=" * 60)
    print("测试完成！")
    print("=" * 60)
