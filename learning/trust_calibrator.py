class TrustCalibrator:
    def __init__(self, reputation_engine):
        self._reputation_engine = reputation_engine

    def calibrate(self):
        scorecards = self._reputation_engine.get_all_scorecards()
        avg_violations = sum(s["policy_violations"] for s in scorecards) / len(scorecards) if scorecards else 0
        
        print(f"[LEARNING] Trust Calibration cycle. Avg violations: {avg_violations:.2f}")
        if avg_violations > 1.5:
            print("[LEARNING] Recommending stricter trust penalty modifiers.")
            return -0.15
        return -0.10
