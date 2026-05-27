class QuotaExceededException(Exception):
    """Raised when an agent exhausts an allocated resource quota."""
    pass


class QuotaManager:
    """Enforces per-agent resource quotas preventing individual agents from monopolising the runtime.

    Quotas mirror OS resource accounting:
        | OS Concept        | ACDLC QuotaManager         |
        | Process limits    | max_concurrent_tasks        |
        | Memory limits     | daily_token_budget          |
        | Retry budgets     | max_retry_budget            |

    Consumption is tracked in-memory and resets on process restart (persistent
    quota databases are a v1.8+ concern once multi-tenant persistence lands).
    """

    DEFAULT_QUOTAS = {
        "daily_token_budget": 500000,
        "max_concurrent_tasks": 8,
        "max_retry_budget": 25
    }

    def __init__(self):
        self._quotas = {}       # agent_id -> quota config dict
        self._consumption = {}  # agent_id -> current usage dict

    # ------------------------------------------------------------------ #
    #  Quota Configuration                                                 #
    # ------------------------------------------------------------------ #

    def set_quota(self, agent_id, daily_token_budget=None,
                  max_concurrent_tasks=None, max_retry_budget=None):
        """Configures or overrides quota for an agent. Uses defaults for omitted fields."""
        self._quotas[agent_id] = {
            "agent_id": agent_id,
            "daily_token_budget": daily_token_budget or self.DEFAULT_QUOTAS["daily_token_budget"],
            "max_concurrent_tasks": max_concurrent_tasks or self.DEFAULT_QUOTAS["max_concurrent_tasks"],
            "max_retry_budget": max_retry_budget or self.DEFAULT_QUOTAS["max_retry_budget"]
        }
        self._consumption[agent_id] = {
            "tokens": 0,
            "concurrent_tasks": 0,
            "retries": 0
        }
        print(f"[QUOTA] Quota configured for agent '{agent_id}': "
              f"tokens={self._quotas[agent_id]['daily_token_budget']:,}, "
              f"concurrency={self._quotas[agent_id]['max_concurrent_tasks']}, "
              f"retries={self._quotas[agent_id]['max_retry_budget']}")

    # ------------------------------------------------------------------ #
    #  Token Quota                                                         #
    # ------------------------------------------------------------------ #

    def consume_tokens(self, agent_id, tokens):
        """Records token consumption. Raises QuotaExceededException if budget exhausted."""
        self._ensure_agent(agent_id)
        projected = self._consumption[agent_id]["tokens"] + tokens
        budget = self._quotas[agent_id]["daily_token_budget"]

        if projected > budget:
            raise QuotaExceededException(
                f"Agent '{agent_id}' exceeded daily token budget "
                f"({projected:,} / {budget:,} tokens)."
            )
        self._consumption[agent_id]["tokens"] = projected

    # ------------------------------------------------------------------ #
    #  Concurrency Quota                                                   #
    # ------------------------------------------------------------------ #

    def check_concurrency(self, agent_id):
        """Returns True if the agent has a free task slot."""
        self._ensure_agent(agent_id)
        return self._consumption[agent_id]["concurrent_tasks"] < \
               self._quotas[agent_id]["max_concurrent_tasks"]

    def acquire_task_slot(self, agent_id):
        """Reserves a concurrent task slot. Raises QuotaExceededException if saturated."""
        if not self.check_concurrency(agent_id):
            limit = self._quotas[agent_id]["max_concurrent_tasks"]
            raise QuotaExceededException(
                f"Agent '{agent_id}' exceeded max concurrent tasks ({limit})."
            )
        self._consumption[agent_id]["concurrent_tasks"] += 1

    def release_task_slot(self, agent_id):
        """Releases a concurrent task slot after task completion."""
        self._ensure_agent(agent_id)
        self._consumption[agent_id]["concurrent_tasks"] = max(
            0, self._consumption[agent_id]["concurrent_tasks"] - 1
        )

    # ------------------------------------------------------------------ #
    #  Retry Quota                                                         #
    # ------------------------------------------------------------------ #

    def consume_retry(self, agent_id):
        """Records a retry consumption. Raises QuotaExceededException if budget exhausted."""
        self._ensure_agent(agent_id)
        projected = self._consumption[agent_id]["retries"] + 1
        budget = self._quotas[agent_id]["max_retry_budget"]

        if projected > budget:
            raise QuotaExceededException(
                f"Agent '{agent_id}' exceeded retry budget ({projected} / {budget})."
            )
        self._consumption[agent_id]["retries"] = projected

    # ------------------------------------------------------------------ #
    #  Usage Reporting                                                     #
    # ------------------------------------------------------------------ #

    def get_usage(self, agent_id):
        """Returns current consumption dict with quota limits for an agent."""
        self._ensure_agent(agent_id)
        return {
            "agent_id": agent_id,
            "tokens_consumed": self._consumption[agent_id]["tokens"],
            "concurrent_tasks": self._consumption[agent_id]["concurrent_tasks"],
            "retries_used": self._consumption[agent_id]["retries"],
            "quotas": self._quotas.get(agent_id, {})
        }

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    def _ensure_agent(self, agent_id):
        """Auto-initialises quota for an agent if not yet configured."""
        if agent_id not in self._quotas:
            self.set_quota(agent_id)
