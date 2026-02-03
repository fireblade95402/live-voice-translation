# Enhanced Translation Agent - Implementation Guide

This file contains code snippets to enhance instruction-following in your translation agent.
Add these methods and modifications to your `main.py` file.

## 1. Add Response Validation Method

Add this method to the `BasicVoiceAssistant` class:

```python
def _validate_translation_response(self, text: str) -> tuple[str, list[str]]:
    """
    Validate and clean agent response to ensure it's a pure translation.
    
    Returns:
        tuple: (cleaned_text, list_of_violations)
    """
    violations = []
    cleaned = text.strip()
    
    # Check for prohibited preambles
    preambles = [
        "the translation is",
        "that means",
        "in english",
        "in spanish",
        "in french",
        "in german",
        "here's the translation",
        "translating from",
        "i detected",
        "translation:",
    ]
    
    text_lower = cleaned.lower()
    
    for preamble in preambles:
        if preamble in text_lower:
            violations.append(f"Contains preamble: '{preamble}'")
            
            # Try to extract just the translation
            # Look for text after colon or quotation marks
            if ":" in cleaned:
                parts = cleaned.split(":", 1)
                if len(parts) > 1:
                    cleaned = parts[1].strip().strip('"\'')
            elif '"' in cleaned:
                # Extract text in quotes
                import re
                matches = re.findall(r'"([^"]+)"', cleaned)
                if matches:
                    cleaned = matches[0]
    
    # Check for meta-commentary
    meta_phrases = [
        "i will translate",
        "i am translating",
        "this is",
        "as a translator",
        "translation assistant",
    ]
    
    for phrase in meta_phrases:
        if phrase in text_lower:
            violations.append(f"Contains meta-commentary: '{phrase}'")
    
    # Check length (translations shouldn't be excessively long)
    if len(cleaned) > 500:
        violations.append(f"Response too long ({len(cleaned)} chars) - possible explanation instead of translation")
    
    return cleaned, violations


def _check_instruction_compliance(self, text: str) -> dict:
    """
    Check if response complies with translation instructions.
    
    Returns:
        dict with 'compliant' bool and 'issues' list
    """
    issues = []
    
    # Pattern checks
    patterns_to_avoid = [
        (r"(?i)the translation (is|would be|for)", "Contains explanation phrase"),
        (r"(?i)(in english|in spanish|in french)", "Mentions language explicitly"),
        (r"(?i)(that means|which means)", "Contains 'means' explanation"),
        (r"(?i)(i (will|am|can|should) translate)", "Refers to translation process"),
        (r"[.!?]\s+[A-Z].*[.!?].*[.!?]", "Multiple sentences (likely explanation)"),
    ]
    
    import re
    for pattern, description in patterns_to_avoid:
        if re.search(pattern, text):
            issues.append(description)
    
    return {
        "compliant": len(issues) == 0,
        "issues": issues
    }
```

## 2. Add Periodic Instruction Reminders

Add these attributes to `BasicVoiceAssistant.__init__`:

```python
def __init__(self, ...):
    # ... existing code ...
    self._conversation_turns = 0
    self._reminder_interval = 5  # Remind every 5 turns
    self._violations_count = 0
```

Add this method:

```python
async def _maybe_send_reminder(self):
    """Send periodic reminder to agent to stay focused on translation."""
    self._conversation_turns += 1
    
    # More frequent reminders if violations are common
    interval = 3 if self._violations_count > 3 else self._reminder_interval
    
    if self._conversation_turns >= interval:
        self._conversation_turns = 0
        
        logger.info("Sending instruction reminder to agent")
        
        conn = self.connection
        assert conn is not None
        
        # Inject system reminder as hidden message
        reminder_text = (
            "[SYSTEM REMINDER: Output ONLY the translation. "
            "No preambles, no explanations, no meta-commentary. "
            "If input is English, output in other language. "
            "If input is other language, output in English.]"
        )
        
        # Note: Depending on your SDK version, you may need to adjust this
        # Some versions support system messages, others require user messages
        reminder = UserMessageItem(content=[InputTextContentPart(text=reminder_text)])
        
        try:
            await conn.conversation.item.create(item=reminder)
            # Don't create response - just add to context
        except Exception as e:
            logger.warning(f"Failed to inject reminder: {e}")
```

## 3. Enhanced Event Handler with Validation

Modify the `_handle_event` method where assistant responses are processed:

```python
# In _handle_event method, modify the RESPONSE_AUDIO_TRANSCRIPT_DONE section:

elif event.type == ServerEventType.RESPONSE_AUDIO_TRANSCRIPT_DONE:
    text = getattr(event, "text", None) or self._assistant_transcript
    if text:
        # Validate response
        cleaned_text, violations = self._validate_translation_response(text)
        compliance = self._check_instruction_compliance(cleaned_text)
        
        if violations or not compliance["compliant"]:
            # Log violations
            self._violations_count += 1
            logger.warning(
                f"Agent response violations detected: "
                f"{violations + compliance['issues']}"
            )
            logger.warning(f"Original: {text}")
            logger.warning(f"Cleaned: {cleaned_text}")
            
            # Emit warning event
            await self._emit("compliance_warning", {
                "violations": violations + compliance["issues"],
                "original": text,
                "cleaned": cleaned_text
            })
            
            # Use cleaned version
            text = cleaned_text
        
        await self._emit("assistant_done", {"text": text})
        
        # Maybe send reminder if violations are accumulating
        if self._violations_count > 0 and self._violations_count % 3 == 0:
            await self._maybe_send_reminder()
    
    self._assistant_transcript = ""
```

## 4. Enhanced Language Detection with Confirmation

Add this method:

```python
async def _handle_language_detection(self, user_text: str):
    """
    Handle language detection and enforce confirmation workflow.
    """
    detected = self._maybe_detect_language(user_text)
    
    if detected and not self._detected_language:
        self._detected_language = detected
        
        logger.info(f"Detected language: {detected}")
        await self._emit("language", {"language": detected})
        
        # Force agent to confirm the language pair
        conn = self.connection
        assert conn is not None
        
        confirmation_prompt = (
            f"[SYSTEM: Non-English language detected: {detected}. "
            f"Respond with EXACTLY: 'I will translate between {detected} and English.' "
            f"Then wait for user input. Do NOT add anything else.]"
        )
        
        confirmation_msg = UserMessageItem(
            content=[InputTextContentPart(text=confirmation_prompt)]
        )
        
        try:
            await conn.conversation.item.create(item=confirmation_msg)
            await conn.response.create()
        except Exception as e:
            logger.error(f"Failed to send confirmation prompt: {e}")
```

Then call it from the transcription completed handler:

```python
elif event.type == ServerEventType.CONVERSATION_ITEM_INPUT_AUDIO_TRANSCRIPTION_COMPLETED:
    text = getattr(event, "transcript", None) or self._user_transcript
    if text:
        await self._emit("transcript_done", {"text": text})
        
        # Handle language detection with forced confirmation
        await self._handle_language_detection(text)
    
    self._user_transcript = ""
```

## 5. Add Temperature Control (if supported)

Modify `_setup_session` to add temperature parameter:

```python
async def _setup_session(self):
    """Configure the VoiceLive session for audio conversation."""
    logger.info("Setting up voice conversation session...")

    # ... existing voice_config and turn_detection_config code ...

    # Create session configuration with stricter parameters
    session_config = RequestSession(
        modalities=[Modality.TEXT, Modality.AUDIO],
        instructions=self.instructions,
        voice=voice_config,
        input_audio_format=InputAudioFormat.PCM16,
        output_audio_format=OutputAudioFormat.PCM16,
        turn_detection=turn_detection_config,
        input_audio_echo_cancellation=AudioEchoCancellation(),
        input_audio_noise_reduction=AudioNoiseReduction(type="azure_deep_noise_suppression"),
        # Add these parameters for better instruction following:
        # NOTE: Check your SDK documentation - parameter names may vary
        # temperature=0.6,  # Lower = more deterministic
        # max_response_output_tokens=150,  # Limit verbosity
    )

    # ... rest of existing code ...
```

## 6. Usage Example

After implementing these enhancements, your agent will:

1. ✅ Validate every response for compliance
2. ✅ Clean responses that contain preambles
3. ✅ Log violations for debugging
4. ✅ Send periodic reminders to stay focused
5. ✅ Enforce language confirmation workflow
6. ✅ Emit compliance warnings via events

Monitor the logs and compliance_warning events to see where the agent struggles,
then refine your instructions accordingly.

## Testing the Improvements

```python
# In server.py or main.py, add logging for violations:

async def _send(self, event_type: str, payload: dict):
    if event_type == "compliance_warning":
        print(f"⚠️  Compliance Warning: {payload['violations']}")
        print(f"   Original: {payload['original']}")
        print(f"   Cleaned:  {payload['cleaned']}")
    
    # ... existing event handling ...
```

This will help you identify patterns in instruction violations and refine your prompts.
