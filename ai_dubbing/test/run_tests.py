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
    print("🧪 运行LLM字幕优化器测试...")
    
    # 运行新测试
    import subprocess
    result = subprocess.run([
        sys.executable, "-m", "pytest", 
        "test_llm_optimizer.py", 
        "-v"
    ], cwd=os.path.dirname(__file__))
    
    # 如果没有pytest，使用unittest
    if result.returncode != 0:
        print("📋 使用unittest运行测试...")
        loader = unittest.TestLoader()
        suite = unittest.TestSuite()
        
        # 加载LLM测试
        from ai_dubbing.test.test_llm_optimizer import TestLLMContextOptimizer
        from ai_dubbing.test.test_llm_optimizer import TestLLMIntegration
        
        suite.addTest(loader.loadTestsFromTestCase(TestLLMContextOptimizer))
        suite.addTest(loader.loadTestsFromTestCase(TestLLMIntegration))
        
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
    
    # 返回退出代码
    sys.exit(result.returncode if hasattr(result, 'returncode') else (0 if result.wasSuccessful() else 1))