"""
贝叶斯更新引擎
基于 Beta-Bernoulli 共轭模型，支持多维度信念更新
"""

import logging
import math

logger = logging.getLogger(__name__)

DEFAULT_DIMENSIONS = [
    "financial_health",
    "brand_reputation",
    "competitive_position",
    "compliance_risk",
]

DIMENSION_LABELS = {
    "financial_health": "财务健康",
    "brand_reputation": "品牌声誉",
    "competitive_position": "竞争地位",
    "compliance_risk": "合规风险",
}

DIMENSION_LABELS_EN = {
    "financial_health": "Financial Health",
    "brand_reputation": "Brand Reputation",
    "competitive_position": "Competitive Position",
    "compliance_risk": "Compliance Risk",
}


def beta_mean(alpha: float, beta: float) -> float:
    if alpha + beta == 0:
        return 0.5
    return alpha / (alpha + beta)


def beta_variance(alpha: float, beta: float) -> float:
    s = alpha + beta
    if s == 0:
        return 0.083
    return (alpha * beta) / (s * s * (s + 1))


def beta_std(alpha: float, beta: float) -> float:
    return math.sqrt(beta_variance(alpha, beta))


def beta_credible_interval(alpha: float, beta: float, ci: float = 0.95):
    mean = beta_mean(alpha, beta)
    std = beta_std(alpha, beta)
    z = 1.96 if ci >= 0.95 else 1.645
    return max(0, mean - z * std), min(1, mean + z * std)


class BeliefEngine:
    def __init__(self, alpha: float = 2.0, beta: float = 2.0):
        self.alpha = alpha
        self.beta = beta

    def update(self, evidence_strength: float, evidence_positive: float, evidence_negative: float):
        alpha_new = self.alpha + evidence_positive * evidence_strength
        beta_new = self.beta + evidence_negative * evidence_strength
        return BeliefState(alpha=alpha_new, beta=beta_new)

    @staticmethod
    def default_prior() -> "BeliefState":
        return BeliefState(alpha=2.0, beta=2.0)


class BeliefState:
    def __init__(self, alpha: float, beta: float):
        self.alpha = alpha
        self.beta = beta
        self._mean = None
        self._variance = None
        self._std = None

    @property
    def mean(self) -> float:
        if self._mean is None:
            self._mean = beta_mean(self.alpha, self.beta)
        return self._mean

    @property
    def variance(self) -> float:
        if self._variance is None:
            self._variance = beta_variance(self.alpha, self.beta)
        return self._variance

    @property
    def std(self) -> float:
        if self._std is None:
            self._std = beta_std(self.alpha, self.beta)
        return self._std

    def credible_interval(self, ci: float = 0.95):
        return beta_credible_interval(self.alpha, self.beta, ci)

    def to_dict(self) -> dict:
        return {
            "alpha": round(self.alpha, 4),
            "beta": round(self.beta, 4),
            "mean": round(self.mean, 4),
            "variance": round(self.variance, 6),
            "std": round(self.std, 4),
        }
