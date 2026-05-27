# Workflows: Stage 4 - Karpathy Development

Writing clean, readable, AI-friendly, and maintainable production candidates based on Andrej Karpathy's coding philosophies.

## Ã°Å¸â€ºÂ Ã¯Â¸ Step-by-Step Execution Plan

### Step 1: Enforce Explicit Over Clever
1. Avoid dense, magic abstractions (e.g., heavily nested list comprehensions, complex metaclasses, or indirect dynamic imports).
2. Unroll loops when it improves readability. Write straightforward, predictable logic.
3. Example:
   ```python
   # DO NOT DO THIS (Implicit / Clever):
   process = lambda data: {k: [x.upper() for x in v if x] for k, v in data.items() if k.startswith('usr_')}

   # DO THIS (Explicit / Clear):
   def process_user_data(data):
       processed_records = {}
       for key, values in data.items():
           if not key.startswith('usr_'):
               continue
           cleaned_values = []
           for val in values:
               if val:
                   cleaned_values.append(val.upper())
           processed_records[key] = cleaned_values
       return processed_records
   ```

### Step 2: Readability Over Abstraction
1. Prioritize code that a junior engineer (or a fresh LLM instance) can understand in one reading.
2. Avoid early optimizations that complicate structure. Keep variables explicitly named.

### Step 3: Local Reasoning & Single-Focus
1. Write files and functions such that a reader can reason about their behavior locally without hopping across multiple modules.
2. A single function should fully fit on a screen (and inside a small model context window).

### Step 4: Debuggability & Observability
1. Never swallow errors silent. Use robust logging.
2. Structure error exceptions to capture exact parameter states at the time of failure.

### Step 5: Structure AI-Friendly Code
1. Use clear type hinting.
2. Add detailed docstrings explaining input constraints and output formats.
3. Write modular hooks that future agents can easily test or extend without having to refactor the entire file.

---

## Ã°Å¸â€â€™ Transition Gate to Stage 5
You **CANNOT** proceed to Stage 5 until:
- [ ] Code is formatted and reviewed against Karpathy readability guidelines.
- [ ] Complex abstractions are refactored into explicit, readable equivalents.
- [ ] Telemetry, exception formatting, and type signatures are verified.
