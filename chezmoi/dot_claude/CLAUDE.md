# Tool Usage Guidelines

## Parallel Tool Execution

**IMPORTANT**: When you invoke multiple tools in a single message, they execute in parallel, not sequentially.

### Sleep Commands

When using `sleep` to wait for something (like a background process to complete), you MUST call it in isolation:

**Correct** ✓

```
Message 1: <invoke Bash sleep 30>
Message 2: <invoke BashOutput to check results>
```

**Incorrect** ✗

```
Single message: <invoke Bash sleep 30> AND <invoke BashOutput>
# These run in parallel - the sleep doesn't delay the BashOutput call!
```
