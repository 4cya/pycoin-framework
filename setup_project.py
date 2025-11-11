#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PyCoin Trading Framework - 项目初始化脚本
"""

import shutil
from pathlib import Path


def main():
    """初始化项目配置"""
    
    print("🚀 PyCoin Trading Framework - 项目初始化")
    print("=" * 50)
    
    # 配置文件映射
    files = [
        ("config/app.example.yaml", "config/app.yaml"),
        ("secrets/accounts.example.yaml", "secrets/accounts.yaml")
    ]
    
    created = 0
    
    # 复制配置文件
    for source, target in files:
        source_path = Path(source)
        target_path = Path(target)
        
        if not source_path.exists():
            print(f"⚠️  模板文件不存在: {source}")
            continue
        
        if target_path.exists():
            print(f"📄 文件已存在，跳过: {target}")
            continue
        
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target_path)
            print(f"✅ 已创建: {target}")
            created += 1
        except Exception as e:
            print(f"❌ 创建失败 {target}: {e}")
    
    # 日志和数据目录会在程序运行时自动创建
    
    print(f"\n✅ 初始化完成! 已创建 {created} 个配置文件")
    print("\n📝 下一步:")
    print("1. 编辑 secrets/accounts.yaml 填入API密钥")
    print("2. 开始开发您的交易程序")


if __name__ == "__main__":
    main()
