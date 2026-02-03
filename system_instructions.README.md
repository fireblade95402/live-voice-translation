# System Instructions

This file contains the system prompt/instructions for the AI translation agent.

## Why This File Exists

- **Version Control**: Instructions should be tracked in git, unlike secrets in `.env`
- **Collaboration**: Team members can review and improve instructions together
- **Testing**: Easy to test different instruction variations
- **Documentation**: Instructions serve as documentation for agent behavior

## How It's Used

The agent loads these instructions at startup via the `load_instructions()` function in `main.py`.

Configuration in `.env`:
```
AZURE_VOICELIVE_INSTRUCTIONS_FILE="system_instructions.txt"
```

## Modifying Instructions

1. Edit this file with your improved instructions
2. Restart the server: `uvicorn server:app --reload`
3. Test the changes
4. Commit to git if improvements are confirmed

## Testing Changes

After modifying instructions:
```bash
# Restart server
# Then test with various translations to verify behavior
```

## Best Practices

- Use clear, structured format (RULE 1, RULE 2, etc.)
- Include specific DON'Ts (what to avoid)
- Provide concrete examples
- Keep instructions focused on the core task (translation)
- See `INSTRUCTION_IMPROVEMENTS.md` for detailed guidance

## Fallback

If this file is missing or unreadable, the system falls back to:
1. `AZURE_VOICELIVE_INSTRUCTIONS` environment variable (if set)
2. Default generic assistant instructions
