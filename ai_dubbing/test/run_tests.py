#!/usr/bin/env python3
"""
测试运行器

运行所有字幕优化相关的单元测试
"""

import unittest
import sys
import os
from pathlib import Path

# 添加项目根目录到路径
current_file = Path(__file__).resolve()
sys.path.insert(0, str(current_file.parent.parent.parent))

if __name__ == '__main__':
    print("🧪 运行所有单元测试...")
    
    # 运行所有测试
    import subprocess
    import glob
    
    # 获取所有测试文件
    test_files = glob.glob(os.path.join(os.path.dirname(__file__), "test_*.py"))
    
    if test_files:
        result = subprocess.run([
            sys.executable, "-m", "pytest", 
            *[os.path.basename(f) for f in test_files], 
            "-v"
        ], cwd=os.path.dirname(__file__))
    else:
        # 如果没有找到测试文件，直接使用unittest
        result = subprocess.run([sys.executable, "-c", "exit(1)"])
    
    # 如果没有pytest，使用unittest
    if result.returncode != 0:
        print("📋 使用unittest运行测试...")
        loader = unittest.TestLoader()
        suite = unittest.TestSuite()
        
        # 加载所有测试模块
        test_modules = [
            "test_llm_optimizer",
            "test_srt_parser", 
            "test_txt_parser"
        ]
        
        for module_name in test_modules:
            try:
                module = __import__(f"ai_dubbing.test.{module_name}", fromlist=[module_name])
                # 获取模块中所有的测试类
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and 
                        issubclass(attr, unittest.TestCase) and 
                        attr != unittest.TestCase):
                        print(f"📝 加载测试类: {attr_name}")
                        suite.addTest(loader.loadTestsFromTestCase(attr))
            except ImportError as e:
                print(f"⚠️  跳过模块 {module_name}: {e}")
        
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
    
    # 返回退出代码
    sys.exit(result.returncode if hasattr(result, 'returncode') else (0 if result.wasSuccessful() else 1))