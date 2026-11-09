"""百分位计算，runner / report / htmlreport 共用一份实现。

之前这套公式在三个文件里各写了一遍，口径容易走偏（比如有一处用了 round，另一处没有）。
"""


def percentile(values, ratio):
    """返回 values 的 ratio 分位值（最近秩法）。空列表返回 0。"""
    if not values:
        return 0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(round(ratio * (len(ordered) - 1))))
    return ordered[idx]


def p95(values):
    """95% 的请求耗时低于该值。"""
    return percentile(values, 0.95)
