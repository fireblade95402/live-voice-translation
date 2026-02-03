# How to Improve AI Agent Instruction Following

## Overview
This document outlines strategies to make your AI translation agent follow instructions more reliably.

## 1. Instruction Design Best Practices

### ✅ Use Clear, Structured Instructions
- **Break rules into numbered sections** (RULE 1, RULE 2, etc.)
- **Use explicit constraints** (ONLY, NEVER, ALWAYS)
- **Provide concrete examples** showing correct behavior
- **Use formatting** (ALL CAPS, bullet points) to emphasize critical points

### ✅ Be Specific About What NOT to Do
LLMs often need negative examples:
```
❌ BAD: "Be helpful"
✅ GOOD: "Do NOT add commentary. Do NOT say 'the translation is...'. ONLY output the translated text."
```

### ✅ Provide Examples in Instructions
```
EXAMPLE:
User (Spanish): "Hola"
You: "Hello"
[NOT: "That means Hello in English"]
```

## 2. Temperature and Model Parameters

### Recommended Settings for Translation Tasks:
```python
# Lower temperature = more deterministic, follows rules better
temperature=0.6  # Default is usually 0.8-1.0

# Adjust these if available in your API:
top_p=0.9        # Nucleus sampling
frequency_penalty=0.3  # Reduce repetition
presence_penalty=0.1   # Encourage staying on topic
```

### How to Add Temperature Control:
Update your session configuration in `_setup_session()`:

```python
session_config = RequestSession(
    modalities=[Modality.TEXT, Modality.AUDIO],
    instructions=self.instructions,
    voice=voice_config,
    input_audio_format=InputAudioFormat.PCM16,
    output_audio_format=OutputAudioFormat.PCM16,
    turn_detection=turn_detection_config,
    input_audio_echo_cancellation=AudioEchoCancellation(),
    input_audio_noise_reduction=AudioNoiseReduction(type="azure_deep_noise_suppression"),
    # Add these if supported by your SDK version:
    temperature=0.6,
    max_response_output_tokens=150,  # Limit verbosity
)
```

## 3. Runtime Enforcement Strategies

### A) Post-Processing Filter
Add validation to check agent responses before playback:

```python
def _validate_translation_response(self, text: str, user_input: str) -> str:
    """Filter out non-translation content from agent response."""
    
    # Remove common preambles
    blocklist = [
        "the translation is",
        "that means",
        "in english",
        "in spanish", 
        "i detected",
        "here's the translation",
        "translating from",
    ]
    
    text_lower = text.lower()
    for phrase in blocklist:
        if phrase in text_lower:
            # Extract just the translation (heuristic)
            parts = text.split(":")
            if len(parts) > 1:
                text = parts[-1].strip()
                break
    
    return text.strip()
```

### B) Conversation Memory Management
Keep context focused on translation task:

```python
class BasicVoiceAssistant:
    def __init__(self, ...):
        # ... existing code ...
        self._conversation_turns = 0
        self._max_turns_before_reminder = 5
    
    async def _maybe_inject_reminder(self):
        """Periodically remind agent of its role."""
        self._conversation_turns += 1
        
        if self._conversation_turns >= self._max_turns_before_reminder:
            self._conversation_turns = 0
            
            # Inject system reminder
            reminder = UserMessageItem(content=[
                InputTextContentPart(
                    text="[SYSTEM REMINDER: You are a translator. Output ONLY translations, no commentary.]"
                )
            ])
            await self.connection.conversation.item.create(item=reminder)
```

### C) Language State Tracking
Enforce translation direction based on detected language:

```python
class BasicVoiceAssistant:
    def __init__(self, ...):
        # ... existing code ...
        self._confirmed_languages = {"en": True}  # English always available
        self._other_language = None
        self._confirmation_pending = False
    
    async def _handle_detected_language(self, text: str):
        """Manage language detection and confirmation."""
        detected = self._maybe_detect_language(text)
        
        if detected and not self._other_language and not self._confirmation_pending:
            self._confirmation_pending = True
            self._other_language = detected
            
            # Force confirmation message
            confirmation = UserMessageItem(content=[
                InputTextContentPart(
                    text=f"[SYSTEM: Language detected: {detected}. Respond with: 'I will translate between {detected} and English. Please proceed.']"
                )
            ])
            await self.connection.conversation.item.create(item=confirmation)
            await self.connection.response.create()
```

## 4. Prompt Engineering Techniques

### A) Role Reinforcement
Start instructions with identity:
```
You are a TRANSLATION TOOL, not a conversational AI.
Your ONLY function is converting text between two languages.
```

### B) Output Constraints
Explicitly limit response format:
```
OUTPUT FORMAT:
- Single sentence translation only
- No preamble (e.g., "The translation is...")
- No explanation
- No additional context
- Maximum 2 sentences if original was compound
```

### C) Chain-of-Thought Suppression
For deterministic tasks like translation, disable reasoning:
```
Do NOT explain your translation process.
Do NOT show intermediate steps.
IMMEDIATELY output the translation.
```

## 5. Testing and Iteration

### Create Test Cases
```python
# test_translation_compliance.py
test_cases = [
    {
        "input": "Hola, ¿cómo estás?",
        "expected_format": "^[A-Z][^:]*[.?!]$",  # Starts with capital, no colons
        "should_not_contain": ["translation is", "that means"]
    },
    {
        "input": "I am doing well",
        "expected_format": "^[A-Z][^:]*[.?!]$",
        "should_not_contain": ["in spanish", "here's"]
    }
]
```

### Monitor Violations
Track when agent breaks rules:
```python
async def _emit(self, event_type: str, payload: dict) -> None:
    if event_type == "assistant_done":
        text = payload.get("text", "")
        violations = self._check_instruction_violations(text)
        if violations:
            logger.warning(f"Instruction violations detected: {violations}")
            await self._event_callback("compliance_warning", {"violations": violations})
    
    # ... existing emit code ...

def _check_instruction_violations(self, text: str) -> list:
    violations = []
    blocklist = ["the translation is", "that means", "in english", "here's the translation"]
    
    for phrase in blocklist:
        if phrase in text.lower():
            violations.append(f"Contains prohibited phrase: '{phrase}'")
    
    return violations
```

## 6. Model Selection

### Consider Model Capabilities
- **GPT-4 Realtime**: Better at following complex instructions
- **GPT-3.5 Realtime**: Faster but may drift from instructions more
- **Fine-tuned models**: Best compliance if you have training data

### Model-Specific Tips
For Azure OpenAI Realtime:
- Use `gpt-4-realtime-preview` for better instruction adherence
- Use stricter turn detection (higher threshold) to reduce interruptions

## 7. Implementation Checklist

- [ ] Restructure instructions with clear RULES
- [ ] Add negative examples (what NOT to do)
- [ ] Lower temperature to 0.6-0.7
- [ ] Add max token limit (150-200 for translations)
- [ ] Implement response validation/filtering
- [ ] Add periodic instruction reminders every 5-10 turns
- [ ] Track language state and enforce translation direction
- [ ] Log compliance violations for analysis
- [ ] Test with diverse input scenarios
- [ ] Iterate based on violation patterns

## 8. Alternative Approaches

### A) Dual-Model Architecture
```
1. Transcription → User input
2. Translation Model (deterministic) → Pure translation
3. TTS → Audio output
```
This removes conversational AI entirely for higher reliability.

### B) Constrained Decoding
If SDK supports it, use logit bias to block certain tokens:
```python
# Pseudocode - check if your SDK supports this
logit_bias = {
    "translation": -10,  # Reduce probability of word "translation"
    "means": -10,
    "that": -5,
}
```

## Summary
The key to better instruction following is:
1. **Crystal-clear instructions** with examples
2. **Lower temperature** for deterministic behavior  
3. **Runtime enforcement** through validation
4. **Periodic reminders** to maintain context
5. **Continuous monitoring** to identify drift patterns

Start with instructions first, then add runtime enforcement as needed.
