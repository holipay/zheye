"""
数据迁移脚本：为关键词分配 group_id
配对中英文关键词，使同一概念的关键词共享 group_id
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from models.base import async_session
from models.keyword import Keyword
from sqlalchemy import select, update, func


async def migrate():
    async with async_session() as session:
        try:
            # 获取所有关键词，按 category 和 id 排序
            result = await session.execute(
                select(Keyword)
                .order_by(Keyword.category, Keyword.id)
            )
            all_keywords = result.scalars().all()
            
            # 按 category 分组
            from collections import defaultdict
            by_category = defaultdict(list)
            for kw in all_keywords:
                by_category[kw.category].append(kw)
            
            # 获取当前最大 group_id
            max_group = (await session.execute(select(func.max(Keyword.group_id)))).scalar() or 0
            next_group_id = max_group + 1
            
            updates = []
            
            for category, keywords in by_category.items():
                # 分离中英文
                en_kws = [k for k in keywords if k.lang == 'en']
                zh_kws = [k for k in keywords if k.lang == 'zh']
                
                # 策略：按 ID 顺序配对相邻的中英文关键词
                # 因为数据是按 (id, id+1) 配对存储的
                paired_en = set()
                paired_zh = set()
                
                # 尝试按 ID 相邻配对
                for en_kw in en_kws:
                    for zh_kw in zh_kws:
                        if zh_kw.id in paired_zh:
                            continue
                        # ID 相差 1，且在同一 category，很可能是配对
                        if abs(en_kw.id - zh_kw.id) == 1:
                            updates.append((en_kw.id, next_group_id))
                            updates.append((zh_kw.id, next_group_id))
                            paired_en.add(en_kw.id)
                            paired_zh.add(zh_kw.id)
                            next_group_id += 1
                            break
                
                # 未配对的英文关键词，独立分配 group_id
                for en_kw in en_kws:
                    if en_kw.id not in paired_en:
                        updates.append((en_kw.id, next_group_id))
                        next_group_id += 1
                
                # 未配对的中文关键词，独立分配 group_id
                for zh_kw in zh_kws:
                    if zh_kw.id not in paired_zh:
                        updates.append((zh_kw.id, next_group_id))
                        next_group_id += 1
            
            # 批量更新
            print(f"准备更新 {len(updates)} 个关键词的 group_id...")
            
            for kw_id, group_id in updates:
                await session.execute(
                    update(Keyword)
                    .where(Keyword.id == kw_id)
                    .values(group_id=group_id)
                )
            
            await session.commit()
            print("迁移完成！")
            
            # 验证结果
            result = await session.execute(
                select(Keyword.group_id, func.count(Keyword.id))
                .group_by(Keyword.group_id)
                .having(func.count(Keyword.id) > 1)
            )
            pairs = result.all()
            print(f"配对的关键词组数: {len(pairs)}")
            
            # 显示几个配对示例
            print("\n配对示例:")
            for group_id, count in pairs[:5]:
                result = await session.execute(
                    select(Keyword.term, Keyword.lang)
                    .where(Keyword.group_id == group_id)
                )
                terms = result.all()
                print(f"  group_id={group_id}: {', '.join([f'{t.lang}:{t.term}' for t in terms])}")
        except Exception as e:
            await session.rollback()
            print(f"迁移失败: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(migrate())
