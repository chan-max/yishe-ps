"""
API 客户端测试脚本
用于测试 PSD 智能对象替换 API 服务
"""

import requests
import json
from pathlib import Path

# API 服务地址
API_BASE_URL = "http://localhost:1595"


def test_health_check():
    """测试健康检查"""
    print("=" * 70)
    print("测试 1: 健康检查")
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
    print("测试 2: 处理单个 PSD 文件")
    print("=" * 70)
    
    # 修改为你的实际路径
    request_data = {
        "psd_path": r"D:\freepik\mouse-pad-mockup\534dd19e-7675-4eea-9c26-4a9a0ca701d5.psd",
        "image_path": r"D:\workspace\yishe-ps\examples\re.jpg",
        "export_dir": r"D:\workspace\yishe-ps\output",
        "output_filename": "api_test_result.png",
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


def test_process_batch():
    """测试批量处理"""
    print("\n" + "=" * 70)
    print("测试 3: 批量处理")
    print("=" * 70)
    
    # 修改为你的实际路径
    request_data = [
        {
            "psd_path": r"D:\freepik\mouse-pad-mockup\534dd19e-7675-4eea-9c26-4a9a0ca701d5.psd",
            "image_path": r"D:\workspace\yishe-ps\examples\re.jpg",
            "export_dir": r"D:\workspace\yishe-ps\output",
            "output_filename": "batch_1_result.png"
        },
        {
            "psd_path": r"D:\freepik\mouse-pad-mockup\534dd19e-7675-4eea-9c26-4a9a0ca701d5.psd",
            "image_path": r"D:\workspace\yishe-ps\examples\sq.jpg",
            "export_dir": r"D:\workspace\yishe-ps\output",
            "output_filename": "batch_2_result.png"
        }
    ]
    
    print(f"批量处理 {len(request_data)} 个文件...")
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/v1/process/batch",
            json=request_data,
            timeout=600  # 10分钟超时
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 批量处理完成!")
            print(f"   总数: {result['total']}")
            print(f"   成功: {result['succeeded']}")
            print(f"   失败: {result['failed']}")
            
            for item in result['results']:
                if item['success']:
                    print(f"   ✅ [{item['index']}] {item['export_path']}")
                else:
                    print(f"   ❌ [{item['index']}] {item['error']}")
            
            return result['failed'] == 0
        else:
            error_detail = response.json()
            print(f"❌ 请求失败 (状态码: {response.status_code})")
            print(f"   错误详情: {error_detail}")
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
    results = []
    
    # 测试单个处理
    results.append(("单个处理", test_process_single()))
    
    # 测试批量处理（可选，取消注释以启用）
    # results.append(("批量处理", test_process_batch()))
    
    # 显示测试结果
    print("\n" + "=" * 70)
    print("测试结果汇总")
    print("=" * 70)
    for name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{name}: {status}")
    
    success_count = sum(1 for _, s in results if s)
    print(f"\n总计: {success_count}/{len(results)} 通过")
    print("=" * 70)


if __name__ == "__main__":
    main()

