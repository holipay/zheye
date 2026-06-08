"""
TF-IDF 语义去重模块
使用 TF-IDF + 余弦相似度进行语义去重

优势：
1. 支持中英文（使用字符 n-gram）
2. 内存占用小（稀疏矩阵）
3. 速度快（矩阵运算）
4. 无额外依赖（scikit-learn）
"""

import logging
import numpy as np
from typing import Optional
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


class TFIDFDeduplicator:
    """
    TF-IDF 语义去重器
    
    使用字符 n-gram 构建 TF-IDF 向量，计算余弦相似度
    """
    
    def __init__(self, threshold: float = 0.8, max_features: int = 10000):
        """
        初始化 TF-IDF 去重器
        
        Args:
            threshold: 相似度阈值（0-1）
            max_features: 最大特征数
        """
        self.threshold = threshold
        self.max_features = max_features
        
        # 使用字符 n-gram（支持中英文）
        # ngram_range=(2, 4) 表示使用 2-gram 到 4-gram
        self.vectorizer = TfidfVectorizer(
            analyzer='char_wb',
            ngram_range=(2, 4),
            max_features=max_features,
            dtype=np.float32,
        )
        
        # 存储已有标题的 TF-IDF 矩阵
        self._tfidf_matrix: Optional[np.ndarray] = None
        self._titles: list[str] = []
        self._is_fitted = False
    
    def fit(self, titles: list[str]) -> None:
        """
        使用已有标题构建 TF-IDF 矩阵
        
        Args:
            titles: 已有标题列表
        """
        if not titles:
            self._tfidf_matrix = None
            self._titles = []
            self._is_fitted = False
            return
        
        try:
            self._titles = list(titles)
            self._tfidf_matrix = self.vectorizer.fit_transform(titles)
            self._is_fitted = True
            logger.debug(f"TF-IDF 矩阵构建完成: {len(titles)} 条标题, {self._tfidf_matrix.shape[1]} 个特征")
        except Exception as e:
            logger.warning(f"TF-IDF 矩阵构建失败: {e}")
            self._tfidf_matrix = None
            self._titles = []
            self._is_fitted = False
    
    def is_duplicate(self, title: str) -> bool:
        """
        检查标题是否与已有标题重复
        
        Args:
            title: 待检查的标题
            
        Returns:
            是否重复
        """
        if not self._is_fitted or not title:
            return False
        
        try:
            # 将新标题转换为 TF-IDF 向量
            title_vector = self.vectorizer.transform([title])
            
            # 计算与所有已有标题的余弦相似度
            similarities = cosine_similarity(title_vector, self._tfidf_matrix)[0]
            
            # 检查是否有超过阈值的相似度
            max_sim = np.max(similarities)
            if max_sim >= self.threshold:
                logger.debug(f"标题重复: '{title[:50]}...' -> 最大相似度: {max_sim:.3f}")
                return True
            
            return False
            
        except Exception as e:
            logger.warning(f"TF-IDF 去重检查失败: {e}")
            return False
    
    def add_title(self, title: str) -> None:
        """
        添加新标题到已有标题列表
        
        Args:
            title: 新标题
        """
        if not title:
            return
        
        self._titles.append(title)
        
        # 重新构建 TF-IDF 矩阵（简单实现，可优化为增量更新）
        if len(self._titles) > 0:
            try:
                self._tfidf_matrix = self.vectorizer.transform(self._titles)
            except Exception as e:
                logger.warning(f"TF-IDF 矩阵更新失败: {e}")
    
    def get_max_similarity(self, title: str) -> tuple[float, Optional[str]]:
        """
        获取标题与已有标题的最大相似度
        
        Args:
            title: 待检查的标题
            
        Returns:
            (最大相似度, 最相似的标题)
        """
        if not self._is_fitted or not title:
            return 0.0, None
        
        try:
            title_vector = self.vectorizer.transform([title])
            similarities = cosine_similarity(title_vector, self._tfidf_matrix)[0]
            
            max_idx = np.argmax(similarities)
            max_sim = similarities[max_idx]
            
            return float(max_sim), self._titles[max_idx]
            
        except Exception as e:
            logger.warning(f"TF-IDF 相似度计算失败: {e}")
            return 0.0, None
    
    def clear(self) -> None:
        """清空已有标题和矩阵"""
        self._tfidf_matrix = None
        self._titles = []
        self._is_fitted = False


# 全局实例
_deduplicator: Optional[TFIDFDeduplicator] = None
