"""Kelly Criterion fracionário com teto de risco."""

def kelly_fraction_stake(balance: float, payout: float, winrate: float,
                         fraction: float = 0.25, max_risk: float = 0.02,
                         min_amount: float = 1.0) -> tuple[float, float]:
    """Calcula stake pelo Kelly fracionário.
    b = payout (ex: 0.80 = 80%), p = winrate, q = 1-p
    f* = (b*p - q) / b
    stake = balance * f* * fraction, limitado a balance*max_risk.

    Retorna (stake, kelly_full).
    """
    if balance <= 0:
        return 0.0, 0.0
    if payout <= 0:
        payout = 0.80
    p = min(max(winrate, 0.0), 0.99)
    q = 1.0 - p
    kelly_full = (payout * p - q) / payout
    if kelly_full <= 0:
        return 0.0, round(kelly_full, 4)
    stake = balance * kelly_full * fraction
    cap = balance * max_risk
    stake = min(stake, cap)
    stake = max(stake, min_amount)
    return round(stake, 2), round(kelly_full, 4)


def empirical_winrate(history: list[bool], prior: float,
                      prior_weight: float = 20.0,
                      min_samples: int = 10) -> float:
    """Winrate bayesiano: mistura prior com empírico.
    p = (prior*weight + wins) / (weight + n).
    Com poucos trades domina o prior; com muitos, domina o empírico.
    min_samples mantido por compatibilidade (não corta mais).
    """
    n = len(history)
    if n == 0:
        return prior
    wins = sum(1 for w in history if w)
    w = max(prior_weight, 0.0)
    return (prior * w + wins) / (w + n)
