"""
API 客户端测试脚本
用于测试 PSD 智能对象替换 API 服务
"""

import requests
import json

# API 服务地址
API_BASE_URL = "http://localhost:1595"


def test_health_check():
    """测试健康检查"""
    print("=" * 70)
    print("健康检查")
    print("=" * 70)
    
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        response.raise_for_status()
        result = response.json()
        print(f"✅ 服务状态: {result['status']}")
        print(f"   版本: {result['version']}")
        print(f"   时间: {result['timestamp']}")
        return True
    except Exception as e:
        print(f"❌ 健康检查失败: {e}")
        return False


def test_process_single():
    """测试单个文件处理"""
    print("\n" + "=" * 70)
    print("处理单个 PSD 文件")
    print("=" * 70)
    
    # 修改为你的实际路径
    request_data = {
        "psd_path": r"D:\freepik\mouse-pad-mockup\534dd19e-7675-4eea-9c26-4a9a0ca701d5.psd",
        "image_path": r"D:\workspace\yishe-ps\examples\re.jpg",
        "export_dir": r"D:\workspace\yishe-ps\output",
        # "smart_object_name": "图片",  # 可选：指定智能对象名称，不指定则使用第一个找到的
        "output_filename": "result.png",
        "tile_size": 512,
        "verbose": True
    }
    
    print(f"请求数据:")
    print(json.dumps(request_data, indent=2, ensure_ascii=False))
    print()
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/v1/process",
            json=request_data,
            timeout=300  # 5分钟超时
        )
        
        if response.status_code == 200:
            result = response.json()
            if result["success"]:
                print(f"✅ 处理成功!")
                print(f"   导出路径: {result['data']['export_path']}")
                print(f"   文件大小: {result['data']['file_size_mb']} MB")
                return True
            else:
                print(f"❌ 处理失败: {result['message']}")
                return False
        else:
            error_detail = response.json()
            print(f"❌ 请求失败 (状态码: {response.status_code})")
            print(f"   错误详情: {error_detail}")
            return False
            
    except requests.exceptions.Timeout:
        print(f"❌ 请求超时（处理时间过长）")
        return False
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("PSD 智能对象替换 API 客户端测试")
    print("=" * 70)
    print(f"\nAPI 服务地址: {API_BASE_URL}")
    print("确保 API 服务已启动: python start_api_server.py")
    print("=" * 70)
    
    # 检查服务是否运行
    if not test_health_check():
        print("\n❌ 服务未运行或无法访问")
        print("请先启动服务: python start_api_server.py")
        return
    
    # 运行测试
    success = test_process_single()
    
    # 显示测试结果
    print("\n" + "=" * 70)
    print("测试结果")
    print("=" * 70)
    status = "✅ 通过" if success else "❌ 失败"
    print(f"处理结果: {status}")
    print("=" * 70)


if __name__ == "__main__":
    main()

