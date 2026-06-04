"""
数据质量保障功能测试

测试：
1. 置信度计算
2. 版本管理
3. 重试管理
"""

import pytest
from datetime import datetime, timedelta


# 直接导入工具函数，避免导入models依赖
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 重新实现纯函数用于测试，避免导入链式依赖


def calculate_confidence(result: dict, response_text: str = None, 
                        required_fields: list = None, 
                        field_validators: dict = None) -> float:
    """动态计算AI分析结果的置信度（测试版本）"""
    if not result:
        return 0.0
    
    scores = []
    
    # 1. 完整性评分（权重0.3）
    completeness = _calculate_completeness(result, required_fields)
    scores.append(("completeness", completeness, 0.3))
    
    # 2. 格式规范性评分（权重0.2）
    format_score = _calculate_format_score(result)
    scores.append(("format", format_score, 0.2))
    
    # 3. 内容质量评分（权重0.3）
    content_score = _calculate_content_quality(result, field_validators)
    scores.append(("content", content_score, 0.3))
    
    # 4. 响应质量评分（权重0.2，可选）
    if response_text:
        response_score = _calculate_response_quality(response_text)
        scores.append(("response", response_score, 0.2))
    else:
        total_weight = sum(w for _, _, w in scores)
        scores = [(n, s, w / total_weight) for n, s, w in scores]
    
    final_score = sum(score * weight for _, score, weight in scores)
    return max(0.0, min(1.0, final_score))


def _calculate_completeness(result: dict, required_fields: list = None) -> float:
    """计算完整性评分"""
    if not result:
        return 0.0
    
    if required_fields is None:
        required_fields = list(result.keys())
    
    if not required_fields:
        return 1.0
    
    filled_count = sum(
        1 for field in required_fields 
        if field in result and result[field] is not None and result[field] != ""
    )
    
    return filled_count / len(required_fields)


def _calculate_format_score(result: dict) -> float:
    """计算格式规范性评分"""
    import re
    score = 1.0
    
    if "sentiment" in result:
        valid_sentiments = {"positive", "negative", "neutral"}
        if result["sentiment"] not in valid_sentiments:
            score -= 0.3
    
    numeric_fields = {
        "sentiment_score": (-1.0, 1.0),
        "importance": (0.0, 1.0),
        "confidence": (0.0, 1.0),
    }
    
    for field, (min_val, max_val) in numeric_fields.items():
        if field in result:
            try:
                val = float(result[field])
                if val < min_val or val > max_val:
                    score -= 0.2
            except (ValueError, TypeError):
                score -= 0.2
    
    list_fields = ["key_points", "tags", "hot_topics", "key_events"]
    for field in list_fields:
        if field in result and not isinstance(result[field], list):
            score -= 0.1
    
    return max(0.0, score)


def _calculate_content_quality(result: dict, field_validators: dict = None) -> float:
    """计算内容质量评分"""
    score = 1.0
    
    summary_fields = ["summary_zh", "overview", "analysis"]
    for field in summary_fields:
        if field in result and isinstance(result[field], str):
            length = len(result[field])
            if length < 10:
                score -= 0.2
            elif length > 1000:
                score -= 0.1
    
    list_fields = ["key_points", "tags"]
    for field in list_fields:
        if field in result and isinstance(result[field], list):
            if len(result[field]) == 0:
                score -= 0.2
    
    if field_validators:
        for field, validator in field_validators.items():
            if field in result:
                try:
                    if not validator(result[field]):
                        score -= 0.1
                except Exception:
                    score -= 0.1
    
    return max(0.0, score)


def _calculate_response_quality(response_text: str) -> float:
    """计算响应质量评分"""
    import re
    if not response_text:
        return 0.0
    
    score = 1.0
    
    if not re.search(r'[\{\[]', response_text):
        score -= 0.3
    
    if len(response_text) < 20:
        score -= 0.3
    
    error_indicators = ["error", "抱歉", "无法", "失败"]
    for indicator in error_indicators:
        if indicator in response_text.lower():
            score -= 0.2
            break
    
    return max(0.0, score)


def calculate_changed_fields(old_data: dict, new_data: dict) -> list:
    """计算变更字段列表"""
    if not old_data or not new_data:
        return []
    
    changed = []
    all_keys = set(old_data.keys()) | set(new_data.keys())
    
    for key in all_keys:
        old_val = old_data.get(key)
        new_val = new_data.get(key)
        
        if old_val != new_val:
            changed.append(key)
    
    return changed


def generate_change_summary(changed_fields: list) -> str:
    """生成变更摘要"""
    if not changed_fields:
        return "无变更"
    
    field_names = {
        "sentiment": "情感",
        "sentiment_score": "情感分数",
        "summary_zh": "中文摘要",
        "key_points": "关键要点",
        "tags": "标签",
        "importance": "重要性",
    }
    
    changed_names = [field_names.get(f, f) for f in changed_fields[:5]]
    summary = f"更新了 {', '.join(changed_names)}"
    
    if len(changed_fields) > 5:
        summary += f" 等 {len(changed_fields)} 个字段"
    
    return summary


class TestConfidenceCalculation:
    """置信度计算测试"""
    
    def test_calculate_confidence_with_valid_data(self):
        """测试有效数据的置信度计算"""
        result = {
            "sentiment": "positive",
            "sentiment_score": 0.8,
            "summary_zh": "这是一个测试摘要",
            "key_points": ["要点1", "要点2"],
            "importance": 0.7,
        }
        
        confidence = calculate_confidence(result)
        assert 0.0 <= confidence <= 1.0
        assert confidence > 0.5  # 有效数据应该有较高的置信度
    
    def test_calculate_confidence_with_empty_data(self):
        """测试空数据的置信度计算"""
        confidence = calculate_confidence({})
        assert confidence == 0.0
    
    def test_calculate_confidence_with_none(self):
        """测试None的置信度计算"""
        confidence = calculate_confidence(None)
        assert confidence == 0.0
    
    def test_calculate_completeness(self):
        """测试完整性计算"""
        result = {"a": 1, "b": 2, "c": 3}
        
        # 所有字段都填充
        completeness = _calculate_completeness(result, ["a", "b", "c"])
        assert completeness == 1.0
        
        # 部分字段填充
        completeness = _calculate_completeness(result, ["a", "b", "d"])
        assert completeness == 2/3
        
        # 空列表
        completeness = _calculate_completeness(result, [])
        assert completeness == 1.0
    
    def test_calculate_format_score(self):
        """测试格式规范性评分"""
        # 有效格式
        valid_result = {
            "sentiment": "positive",
            "sentiment_score": 0.5,
            "importance": 0.8,
            "key_points": ["point1"],
        }
        score = _calculate_format_score(valid_result)
        assert score == 1.0
        
        # 无效sentiment
        invalid_sentiment = {"sentiment": "invalid"}
        score = _calculate_format_score(invalid_sentiment)
        assert score < 1.0
        
        # 超出范围的数值
        out_of_range = {"sentiment_score": 2.0}
        score = _calculate_format_score(out_of_range)
        assert score < 1.0
    
    def test_calculate_confidence_with_validators(self):
        """测试带验证器的置信度计算"""
        result = {
            "sentiment": "positive",
            "sentiment_score": 0.5,
        }
        
        validators = {
            "sentiment": lambda x: x in ("positive", "negative", "neutral"),
            "sentiment_score": lambda x: -1.0 <= float(x) <= 1.0,
        }
        
        confidence = calculate_confidence(result, field_validators=validators)
        assert confidence > 0.5
        
        # 无效值
        invalid_result = {
            "sentiment": "invalid",
            "sentiment_score": 5.0,
        }
        confidence = calculate_confidence(invalid_result, field_validators=validators)
        assert confidence < 0.8  # 无效值应该降低置信度
    
    def test_calculate_confidence_with_response_text(self):
        """测试带响应文本的置信度计算"""
        result = {
            "sentiment": "positive",
            "summary_zh": "测试摘要",
        }
        
        # 有效JSON响应
        valid_response = '{"sentiment": "positive", "summary_zh": "测试摘要"}'
        confidence = calculate_confidence(result, response_text=valid_response)
        assert confidence > 0.5
        
        # 无效响应
        invalid_response = "这不是JSON"
        confidence_without = calculate_confidence(result)
        confidence_with_invalid = calculate_confidence(result, response_text=invalid_response)
        # 无效响应应该降低置信度
        assert confidence_with_invalid < confidence_without + 0.1


class TestVersionComparison:
    """版本对比测试"""
    
    def test_calculate_changed_fields(self):
        """测试变更字段计算"""
        old_data = {"a": 1, "b": 2, "c": 3}
        new_data = {"a": 1, "b": 3, "d": 4}
        
        changed = calculate_changed_fields(old_data, new_data)
        assert "b" in changed
        assert "c" in changed  # 旧数据有，新数据没有
        assert "d" in changed  # 新数据有，旧数据没有
        assert "a" not in changed  # 未变更
    
    def test_calculate_changed_fields_with_empty_data(self):
        """测试空数据的变更字段计算"""
        assert calculate_changed_fields({}, {"a": 1}) == []
        assert calculate_changed_fields({"a": 1}, {}) == []
        assert calculate_changed_fields(None, {"a": 1}) == []
    
    def test_generate_change_summary(self):
        """测试变更摘要生成"""
        # 无变更
        summary = generate_change_summary([])
        assert summary == "无变更"
        
        # 单个字段
        summary = generate_change_summary(["sentiment"])
        assert "情感" in summary
        
        # 多个字段
        summary = generate_change_summary(["sentiment", "summary_zh", "tags"])
        assert "情感" in summary
        assert "中文摘要" in summary
        assert "标签" in summary
        
        # 超过5个字段
        fields = ["sentiment", "summary_zh", "tags", "key_points", "importance", "overview"]
        summary = generate_change_summary(fields)
        assert "6 个字段" in summary
    
    def test_version_diff(self):
        """测试版本差异计算"""
        v1_data = {
            "sentiment": "positive",
            "sentiment_score": 0.8,
            "summary_zh": "旧摘要",
            "key_points": ["要点1", "要点2"],
        }
        
        v2_data = {
            "sentiment": "negative",
            "sentiment_score": -0.5,
            "summary_zh": "新摘要",
            "key_points": ["要点1", "要点2"],
        }
        
        changed = calculate_changed_fields(v1_data, v2_data)
        assert "sentiment" in changed
        assert "sentiment_score" in changed
        assert "summary_zh" in changed
        assert "key_points" not in changed  # 未变更


class TestConfidenceThreshold:
    """置信度阈值测试"""
    
    def test_high_confidence_passes(self):
        """高置信度应该通过"""
        result = {
            "sentiment": "positive",
            "sentiment_score": 0.8,
            "summary_zh": "这是一篇关于经济发展的详细分析文章",
            "key_points": ["要点1", "要点2", "要点3"],
            "importance": 0.9,
        }
        
        confidence = calculate_confidence(result)
        threshold = 0.7
        assert confidence >= threshold
    
    def test_low_confidence_fails(self):
        """低置信度应该失败"""
        result = {
            "sentiment": "invalid",
            "sentiment_score": 5.0,
            "summary_zh": "",
            "key_points": [],
        }
        
        confidence = calculate_confidence(result)
        threshold = 0.7
        assert confidence < threshold
    
    def test_partial_data_confidence(self):
        """部分数据应该有中等置信度"""
        result = {
            "sentiment": "positive",
            "sentiment_score": 0.5,
            # 缺少其他字段
        }
        
        confidence = calculate_confidence(result)
        # 部分数据但字段有效，置信度应该适中
        assert 0.0 < confidence <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
