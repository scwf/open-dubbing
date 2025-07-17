"""
策略注册与工厂

此模块负责动态发现、注册所有可用的时间同步策略，并提供一个工厂函数
来实例化选定的策略。
"""
from __future__ import annotations
from typing import Dict, Type, Any
import inspect

from ai_dubbing.src.strategies.base_strategy import TimeSyncStrategy
from ai_dubbing.src.tts_engines.base_engine import BaseTTSEngine

# 策略注册表
_strategy_registry: Dict[str, Type[TimeSyncStrategy]] = {}

def _register_strategies():
    """自动发现并注册所有策略类"""
    from . import basic_strategy, stretch_strategy
    
    # 将所有策略模块集中管理
    strategy_modules = [
        basic_strategy, 
        stretch_strategy
    ]
    
    for module in strategy_modules:
        for name, obj in inspect.getmembers(module):
            # 筛选出继承自TimeSyncStrategy的策略类
            if inspect.isclass(obj) and issubclass(obj, TimeSyncStrategy) and obj is not TimeSyncStrategy:
                # 调用静态的 name() 方法获取策略的正确名称
                strategy_name = obj.name()
                _strategy_registry[strategy_name] = obj
                
_register_strategies()


def get_strategy(name: str, tts_engine: 'BaseTTSEngine', **kwargs) -> 'TimeSyncStrategy':
    """
    策略工厂函数

    Args:
        name: 策略名称
        tts_engine: TTS引擎实例
        **kwargs: 策略特定的其他参数

    Returns:
        策略实例
    
    Raises:
        ValueError: 如果找不到指定的策略
    """
    strategy_class = _strategy_registry.get(name)
    if not strategy_class:
        raise ValueError(f"未知策略: '{name}'. 可用策略: {list_available_strategies()}")

    # 实例化策略，并注入TTS引擎和其它参数
    return strategy_class(tts_engine=tts_engine, **kwargs)

def list_available_strategies() -> list[str]:
    """返回所有可用策略的名称列表"""
    return sorted(list(_strategy_registry.keys()))

def get_strategy_description(name: str) -> str:
    """获取指定策略的描述"""
    strategy_class = _strategy_registry.get(name)
    if not strategy_class:
        return "未知策略"
    
    # 直接调用静态方法获取描述
    return strategy_class.description() 