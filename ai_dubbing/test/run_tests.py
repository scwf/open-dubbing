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
    # 发现所有测试文件
    test_loader = unittest.TestLoader()
    test_suite = test_loader.discover(os.path.dirname(__file__), pattern='test_*.py')
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # 返回退出代码
    sys.exit(0 if result.wasSuccessful() else 1)